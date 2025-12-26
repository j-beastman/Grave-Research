
import asyncio
import logging
from datetime import datetime

from kalshi_client import KalshiClient
from news_matcher import (
    fetch_all_news, match_news_to_market
)
from database import (
    AsyncSessionLocal, 
    upsert_series, upsert_event, upsert_market, upsert_article, 
    link_article_to_events, 
    upsert_markets_bulk
)
from database import retention

from embeddings import EmbeddingService

logger = logging.getLogger(__name__)

async def ingest_kalshi_data():
    """
    Main ingestion loop:
    1. Fetch events
    2. Fetch markets
    3. Sync to DB
    4. Fetch & Sync News
    """
    embed_service = EmbeddingService.get_instance()
    
    async with AsyncSessionLocal() as session:
        client = KalshiClient()
        try:
            # 1. Fetch & Upsert Series/Events
            logger.info("Fetching events...")
            events = await client.get_all_events(max_events=200)
            now = datetime.utcnow()
            
            # Extract unique series and map a category to them (from any event in that series)
            series_map = {} # ticker -> category
            for e in events:
                s_ticker = e.get("series_ticker")
                if s_ticker and s_ticker not in series_map:
                    series_map[s_ticker] = e.get("category")
            
            for ticker, category in series_map.items():
                await upsert_series(session, {
                    "ticker": ticker, 
                    "category": category,
                    "created_at": now, 
                    "updated_at": now
                })
            await session.commit()
            logger.info(f"Upserted {len(series_map)} series.")

            db_events = []
            for e in events:
                db_events.append({
                    "event_ticker": e["event_ticker"],
                    "series_ticker": e.get("series_ticker"),
                    "title": e.get("title"),
                    "category": e.get("category"),
                    "status": e.get("status"),
                    "created_at": now,
                    "updated_at": now
                })
            
            for e_data in db_events:
                await upsert_event(session, e_data)
            await session.commit()
            logger.info(f"Upserted {len(db_events)} events.")

            # 2. Fetch & Upsert Markets
            logger.info("Fetching markets...")
            markets = await client.get_all_open_markets(max_markets=300)
            
            # Upsert missing parent events first
            market_event_tickers = set(m.get("event_ticker") for m in markets if m.get("event_ticker"))
            logger.info(f"Checking {len(market_event_tickers)} event tickers from markets...")
            for ticker in market_event_tickers:
                try:
                    await upsert_event(session, {
                        "event_ticker": ticker, 
                        "title": f"Event {ticker}",
                        "created_at": now,
                        "updated_at": now
                    })
                except Exception as e:
                    logger.warning(f"Lazy event upsert failed for {ticker}: {e}")
            await session.commit()
            logger.info("Manual event upsert complete.")
            
            # Upsert markets
            db_markets = []
            snapshots = []
            now = datetime.utcnow()
            
            # Batch embedding generation for markets
            market_texts = [m["title"] for m in markets]
            logger.info(f"Generating embeddings for {len(markets)} markets...")
            market_embeddings = embed_service.generate(market_texts)
            
            for idx, m in enumerate(markets):
                if not m.get("event_ticker"):
                    logger.warning(f"Market {m['ticker']} has no event_ticker, skipping.")
                    continue
                
                # Strip timezone from ISO strings for naive TIMESTAMP columns
                def parse_dt(iso_str):
                    if not iso_str: return None
                    return datetime.fromisoformat(iso_str.replace('Z', '+00:00')).replace(tzinfo=None)
                    
                db_markets.append({
                    "market_ticker": m["ticker"],
                    "event_ticker": m["event_ticker"],
                    "title": m["title"],
                    "subtitle": m.get("subtitle", m.get("yes_sub_title")),
                    "yes_sub_title": m.get("yes_sub_title"),
                    "no_sub_title": m.get("no_sub_title"),
                    "market_type": m.get("market_type"),
                    "status": m["status"],
                    "open_time": parse_dt(m.get("open_time")),
                    "close_time": parse_dt(m.get("close_time")),
                    "expiration_time": parse_dt(m.get("expiration_time")),
                    "created_at": now,
                    "updated_at": now,
                    "embedding": market_embeddings[idx],
                    # Prices (flattened)
                    "yes_ask": m.get("yes_ask"),
                    "no_ask": m.get("no_ask"),
                    "yes_bid": m.get("yes_bid"),
                    "no_bid": m.get("no_bid"),
                    "last_price": m.get("last_price"),
                    "volume": m.get("volume"),
                    "open_interest": m.get("open_interest")
                })
                
            if db_markets:
                logger.info(f"Attempting bulk upsert for {len(db_markets)} markets...")
                try:
                    await upsert_markets_bulk(session, db_markets)
                    await session.commit()
                    logger.info(f"Successfully upserted markets.")
                except Exception as e:
                    logger.error(f"Bulk market upsert failed: {e}")
                    # Try item by item
                    await session.rollback()
                    logger.info("Retrying markets one-by-one...")
                    for m_data in db_markets:
                        try:
                            await upsert_market(session, m_data)
                            await session.commit()
                        except Exception as m_e:
                            logger.error(f"Failed to upsert market {m_data['market_ticker']}: {m_e}")
                            await session.rollback()

            # 3. News Ingestion
            logger.info("Fetching news...")
            news_items = await fetch_all_news()
            
            # Generate embeddings for news
            news_texts = [item.title for item in news_items]
            logger.info(f"Generating embeddings for {len(news_items)} articles...")
            news_embeddings = embed_service.generate(news_texts)
            
            for idx, item in enumerate(news_items):
                # Ensure published_at is naive if it's aware
                pub_at = item.published
                if pub_at and pub_at.tzinfo:
                    pub_at = pub_at.replace(tzinfo=None)

                # Upsert article
                article = await upsert_article(session, {
                    "url": item.link,
                    "title": item.title,
                    "summary": item.summary,
                    "source": item.source,
                    "published_at": pub_at or now,
                    "fetched_at": now,
                    "embedding": news_embeddings[idx]
                })
                
            await session.commit()
            
            # 4. Retention Cleanup
            stats = await retention.cleanup_stale_data(session)
            logger.info(f"Cleanup stats: {stats}")

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            await session.rollback()
        finally:
            await client.close()

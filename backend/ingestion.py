
import asyncio
import logging
from datetime import datetime

from sqlalchemy import text
from kalshi_client import KalshiClient, categorize_market
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
    print("\nStarting ingestion process...")
    embed_service = EmbeddingService.get_instance()
    
    async with AsyncSessionLocal() as session:
        client = KalshiClient()
        try:
            # 1. Fetch & Upsert Series/Events
            print("Fetching all open events from Kalshi...")
            logger.info("Fetching all open events from Kalshi...")
            events = await client.get_all_events(max_events=5000)
            
            # Identify new events by comparing with DB
            existing_event_tickers = await session.execute(text("SELECT event_ticker FROM events"))
            existing_event_tickers = set(r[0] for r in existing_event_tickers.all())
            
            new_events = [e for e in events if e["event_ticker"] not in existing_event_tickers]
            print(f"Fetched {len(events)} events. {len(new_events)} are new.")
            logger.info(f"Fetched {len(events)} events. {len(new_events)} are new.")
            if new_events:
                logger.info(f"New event tickers: {[e['event_ticker'] for e in new_events[:10]]}{'...' if len(new_events) > 10 else ''}")
            
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
                # Use updated categorization logic
                e_category = categorize_market({"category": e.get("category"), "title": e.get("title")})
                db_events.append({
                    "event_ticker": e["event_ticker"],
                    "series_ticker": e.get("series_ticker"),
                    "title": e.get("title"),
                    "category": e_category,
                    "status": e.get("status"),
                    "created_at": now,
                    "updated_at": now
                })
            
            
            for e_data in db_events:
                await upsert_event(session, e_data)
            await session.commit()
            logger.info(f"Successfully synchronized {len(db_events)} events to database.")

            # 2. Fetch & Upsert Markets
            logger.info("Fetching all open markets from Kalshi...")
            markets = await client.get_all_open_markets(max_markets=5000)
            
            # Identify new markets
            existing_market_tickers = await session.execute(text("SELECT market_ticker FROM markets"))
            existing_market_tickers = set(r[0] for r in existing_market_tickers.all())
            
            # Filter to only include active markets
            active_markets = [m for m in markets if m.get("status") == "active"]
            print(f"Fetched {len(markets)} markets. {len(active_markets)} are active.")
            
            new_markets = [m for m in active_markets if m["ticker"] not in existing_market_tickers]
            print(f"{len(new_markets)} are new.")
            
            # Use only active markets for the rest of the ingestion
            markets = active_markets
            
            # Upsert missing parent events first
            market_event_tickers = set(m.get("event_ticker") for m in markets if m.get("event_ticker"))
            
            # Identify tickers we haven't already processed in this run
            processed_tickers = set(e["event_ticker"] for e in events)
            missing_tickers = market_event_tickers - processed_tickers
            
            if missing_tickers:
                logger.info(f"Found {len(missing_tickers)} events missing from initial fetch. Fetching details...")
                for ticker in missing_tickers:
                    try:
                        event_data = await client.get_event(ticker)
                        event = event_data.get("event")
                        if event:
                            # Must upsert series first to satisfy FK
                            if event.get("series_ticker"):
                                await upsert_series(session, {
                                    "ticker": event["series_ticker"],
                                    "category": event.get("category"),
                                    "created_at": now,
                                    "updated_at": now
                                })
                            
                            e_category = categorize_market({"category": event.get("category"), "title": event.get("title")})
                            await upsert_event(session, {
                                "event_ticker": event["event_ticker"], 
                                "series_ticker": event.get("series_ticker"),
                                "title": event.get("title"),
                                "category": e_category,
                                "created_at": now,
                                "updated_at": now
                            })
                        else:
                            await upsert_event(session, {
                                "event_ticker": ticker, 
                                "title": f"Event {ticker}",
                                "created_at": now,
                                "updated_at": now
                            })
                        await session.commit()
                    except Exception as e:
                        await session.rollback()
                        try:
                             await upsert_event(session, {
                                "event_ticker": ticker, 
                                "title": f"Event {ticker}",
                                "created_at": now,
                                "updated_at": now
                            })
                             await session.commit()
                        except:
                            await session.rollback()
            
            await session.commit()
            logger.info("Manual event upsert complete.")
            
            # Upsert markets
            db_markets = []
            now = datetime.utcnow()
            
            # Batch embedding generation for markets
            market_texts = [m["title"] for m in markets]
            logger.info(f"Generating embeddings for {len(markets)} markets...")
            print(f"Generating embeddings for {len(markets)} markets (this may take a moment)...")
            market_embeddings = embed_service.generate(market_texts)
            print("Market embeddings generated.")
            
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
                print(f"Syncing {len(db_markets)} markets to database...")
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
                        except:
                            await session.rollback()
                print("Markets synchronized.")

            # 2b. Aggregate market data to events and compute heat scores
            print("Updating event heat scores...")
            logger.info("Computing event-level heat scores...")
            event_aggregates = {}
            for m in db_markets:
                event_ticker = m.get("event_ticker")
                if not event_ticker: continue
                if event_ticker not in event_aggregates:
                    event_aggregates[event_ticker] = {"volume": 0, "open_interest": 0}
                event_aggregates[event_ticker]["volume"] += m.get("volume") or 0
                event_aggregates[event_ticker]["open_interest"] += m.get("open_interest") or 0
            
            # Calculate heat score for each event and update
            for event_ticker, agg in event_aggregates.items():
                volume = agg["volume"]
                oi = agg["open_interest"]
                # Heat formula: volume_score + oi_score (simplified event-level)
                volume_score = volume / 10000
                oi_score = oi / 5000  
                heat_score = volume_score + oi_score
                
                await upsert_event(session, {
                    "event_ticker": event_ticker,
                    "total_volume": volume,
                    "total_open_interest": oi,
                    "heat_score": round(heat_score, 2),
                    "updated_at": now
                })
            await session.commit()
            logger.info(f"Updated heat scores for {len(event_aggregates)} events.")
            logger.info("Fetching news...")
            news_items = await fetch_all_news()
            
            # Generate embeddings for news
            news_texts = [item.title for item in news_items]
            print(f"Generating embeddings for {len(news_items)} news articles...")
            logger.info(f"Generating embeddings for {len(news_items)} articles...")
            news_embeddings = embed_service.generate(news_texts)
            
            upserted_articles = []
            for idx, item in enumerate(news_items):
                pub_at = item.published
                if pub_at and pub_at.tzinfo:
                    pub_at = pub_at.replace(tzinfo=None)

                article = await upsert_article(session, {
                    "url": item.link,
                    "title": item.title,
                    "summary": item.summary,
                    "source": item.source,
                    "published_at": pub_at or now,
                    "fetched_at": now,
                    "embedding": news_embeddings[idx]
                })
                if article:
                    upserted_articles.append(article)
                
            await session.commit()
            print(f"Synchronized {len(upserted_articles)} news articles.")
            
            # Link news to events via vector search
            print("Linking news to events via vector search...")
            logger.info("Linking news to events...")
            from news_matcher import match_articles_to_events
            await match_articles_to_events(session, upserted_articles)
            print("News linking complete.")
            logger.info("News linking complete.")

            # 4. Retention Cleanup
            stats = await retention.cleanup_stale_data(session)
            print(f"Cleanup complete. Removed {stats.get('deleted_count', 0)} stale records.")
            logger.info(f"Cleanup complete. Removed {stats.get('deleted_count', 0)} stale records.")

        except Exception as e:
            print(f"Ingestion failed: {e}")
            logger.error(f"Ingestion failed: {e}")
            await session.rollback()
        finally:
            await client.close()

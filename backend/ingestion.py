
import asyncio
import logging
from datetime import datetime

from kalshi_client import KalshiClient
from news_matcher import fetch_all_news, match_news_to_market
from database import (
    AsyncSessionLocal, 
    upsert_event, upsert_market, upsert_article, 
    link_article_to_events, record_snapshots_bulk,
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
            
            # 2. Fetch Markets
            logger.info("Fetching markets...")
            markets = await client.get_all_open_markets(max_markets=1000)
            
            # Upsert markets
            db_markets = []
            snapshots = []
            now = datetime.utcnow()
            
            # Batch embedding generation for markets?
            # Creating list of texts
            market_texts = [m["title"] for m in markets]
            # Generate all at once
            logger.info(f"Generating embeddings for {len(markets)} markets...")
            market_embeddings = embed_service.generate(market_texts)
            
            for idx, m in enumerate(markets):
                db_markets.append({
                    "ticker": m["ticker"],
                    "event_ticker": m["event_ticker"],
                    "title": m["title"],
                    "subtitle": m["subtitle"],
                    "yes_sub_title": m.get("yes_sub_title"),
                    "no_sub_title": m.get("no_sub_title"),
                    "market_type": m.get("market_type"),
                    "status": m["status"],
                    "open_time": datetime.fromisoformat(m["open_time"].replace('Z', '+00:00')) if m.get("open_time") else None,
                    "close_time": datetime.fromisoformat(m["close_time"].replace('Z', '+00:00')) if m.get("close_time") else None,
                    "expiration_time": datetime.fromisoformat(m["expiration_time"].replace('Z', '+00:00')) if m.get("expiration_time") else None,
                    "updated_at": now,
                    "embedding": market_embeddings[idx] # Add embedding
                })
                
                # Snapshot data (same as before)
                snapshots.append({
                    "market_ticker": m["ticker"],
                    "timestamp": now,
                    "yes_bid": m.get("yes_bid"),
                    "yes_ask": m.get("yes_ask"),
                    "no_bid": m.get("no_bid"),
                    "no_ask": m.get("no_ask"),
                    "last_price": m.get("last_price"),
                    "volume": m.get("volume"),
                    "volume_24h": m.get("volume_24h"),
                    "open_interest": m.get("open_interest")
                })

            if db_markets:
                await upsert_markets_bulk(session, db_markets)
                await record_snapshots_bulk(session, snapshots)
                await session.commit()
                logger.info(f"Upserted {len(db_markets)} markets and snapshots.")

            # 3. News Ingestion
            logger.info("Fetching news...")
            news_items = await fetch_all_news()
            
            # Generate embeddings for news
            news_texts = [item.title for item in news_items]
            logger.info(f"Generating embeddings for {len(news_items)} articles...")
            news_embeddings = embed_service.generate(news_texts)
            
            for idx, item in enumerate(news_items):
                # Upsert article
                article = await upsert_article(session, {
                    "url": item.link,
                    "title": item.title,
                    "summary": item.summary,
                    "source": item.source,
                    "published_at": item.published,
                    "fetched_at": now,
                    "embedding": news_embeddings[idx] # Add embedding
                })
                
                # Match to markets/events?
                # Using existing match logic on the python objects might be heavy.
                # For now, let's store the article. 
                # Linking logic: We can try to match against the *events* we just fetched.
                # Simplistic keyword matching for now to populate links
                # (Ideally we reuse news_matcher logic but adapted for DB objects)
                pass 
                
            await session.commit()
            
            # 4. Retention Cleanup
            stats = await retention.cleanup_stale_data(session)
            logger.info(f"Cleanup stats: {stats}")

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            await session.rollback()
        finally:
            await client.close()

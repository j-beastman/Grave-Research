
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models import Base, Series, Event, Market, MarketSnapshot, NewsArticle, ArticleEventLink
from .connection import engine

async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        
        # Create the generated column and index for search if needed via raw SQL?
        # SQLAlchemy create_all should handle the Generated column if defined in model.
        # But we need to ensure the text search configuration is correct.
        # For now, create_all is sufficient for standard columns.

async def upsert_series(session: AsyncSession, series_data: dict) -> Series:
    stmt = pg_insert(Series).values(**series_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=['ticker'],
        set_={k: v for k, v in series_data.items() if k != 'ticker'}
    ).returning(Series)
    result = await session.execute(stmt)
    return result.scalar_one()

async def get_series(session: AsyncSession, ticker: str) -> Optional[Series]:
    return await session.get(Series, ticker)

async def upsert_event(session: AsyncSession, event_data: dict) -> Event:
    stmt = pg_insert(Event).values(**event_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=['event_ticker'],
        set_={k: v for k, v in event_data.items() if k != 'event_ticker'}
    ).returning(Event)
    result = await session.execute(stmt)
    return result.scalar_one()

async def get_event(session: AsyncSession, event_ticker: str) -> Optional[Event]:
    stmt = select(Event).where(Event.event_ticker == event_ticker)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_events_by_series(session: AsyncSession, series_ticker: str) -> List[Event]:
    stmt = select(Event).where(Event.series_ticker == series_ticker)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def upsert_market(session: AsyncSession, market_data: dict) -> Market:
    # Filter out fields that might not matching model (like 'open_interest' which is in snapshot, not market table in prompt schema?)
    # Wait, prompt schema for Market Table: created_at, updated_at, etc.
    # NO open_interest in Market Table spec! It's in Snapshot.
    # So we must clean market_data before inserting.
    valid_keys = Market.__table__.columns.keys()
    clean_data = {k: v for k, v in market_data.items() if k in valid_keys}
    
    stmt = pg_insert(Market).values(**clean_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=['ticker'],
        set_={k: v for k, v in clean_data.items() if k != 'ticker'}
    ).returning(Market)
    result = await session.execute(stmt)
    return result.scalar_one()

async def upsert_markets_bulk(session: AsyncSession, markets: List[dict]) -> int:
    valid_keys = Market.__table__.columns.keys()
    count = 0
    for m in markets:
        clean_data = {k: v for k, v in m.items() if k in valid_keys}
        market = Market(**clean_data)
        await session.merge(market)
        count += 1
    return count

async def get_market(session: AsyncSession, ticker: str) -> Optional[Market]:
    return await session.get(Market, ticker)

async def get_markets_by_event(session: AsyncSession, event_ticker: str) -> List[Market]:
    stmt = select(Market).where(Market.event_ticker == event_ticker)
    result = await session.execute(stmt)
    return list(result.scalars().all())

# Snapshot Operations
async def record_snapshot(session: AsyncSession, market_ticker: str, snapshot_data: dict) -> MarketSnapshot:
    data = snapshot_data.copy()
    data['market_ticker'] = market_ticker
    # Ensure timestamp
    if 'timestamp' not in data:
        data['timestamp'] = datetime.utcnow()
        
    snapshot = MarketSnapshot(**data)
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot

async def record_snapshots_bulk(session: AsyncSession, snapshots: List[dict]) -> int:
    count = 0
    now = datetime.utcnow()
    for s in snapshots:
        if 'timestamp' not in s:
            s['timestamp'] = now
        snapshot = MarketSnapshot(**s)
        session.add(snapshot)
        count += 1
    return count

async def get_market_history(
    session: AsyncSession,
    market_ticker: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    interval: str = "1h"
) -> List[MarketSnapshot]:
    stmt = select(MarketSnapshot).where(MarketSnapshot.market_ticker == market_ticker)
    
    if start_time:
        stmt = stmt.where(MarketSnapshot.timestamp >= start_time)
    if end_time:
        stmt = stmt.where(MarketSnapshot.timestamp <= end_time)
        
    stmt = stmt.order_by(MarketSnapshot.timestamp.asc())
    
    # Downsampling logic could go here (e.g. using date_trunc in SQL)
    # For now returning raw rows as per schema simplicity, but 'interval' arg implies aggregation.
    # In a real app we'd use time_bucket (TimescaleDB) or date_trunc.
    
    result = await session.execute(stmt)
    return list(result.scalars().all())

# News Operations
async def upsert_article(session: AsyncSession, article_data: dict) -> NewsArticle:
    stmt = pg_insert(NewsArticle).values(**article_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=['url'],
        set_={k: v for k, v in article_data.items() if k != 'url'}
    ).returning(NewsArticle)
    result = await session.execute(stmt)
    return result.scalar_one()

async def link_article_to_events(
    session: AsyncSession,
    article_id: UUID,
    event_tickers: List[str],
    relevance_scores: Optional[List[float]] = None
) -> int:
    if not event_tickers:
        return 0
        
    links = []
    for idx, ticker in enumerate(event_tickers):
        score = relevance_scores[idx] if relevance_scores and idx < len(relevance_scores) else None
        links.append({
            "article_id": article_id,
            "event_ticker": ticker,
            "relevance_score": score
        })
        
    stmt = pg_insert(ArticleEventLink).values(links)
    stmt = stmt.on_conflict_do_nothing()
    result = await session.execute(stmt)
    return result.rowcount

async def get_articles_for_event(
    session: AsyncSession,
    event_ticker: str,
    limit: int = 20
) -> List[NewsArticle]:
    stmt = (
        select(NewsArticle)
        .join(ArticleEventLink)
        .where(ArticleEventLink.event_ticker == event_ticker)
        .order_by(ArticleEventLink.relevance_score.desc(), NewsArticle.published_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_recent_articles(
    session: AsyncSession,
    hours: int = 24,
    source: Optional[str] = None
) -> List[NewsArticle]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = select(NewsArticle).where(NewsArticle.fetched_at >= cutoff)
    
    if source:
        stmt = stmt.where(NewsArticle.source == source)
        
    stmt = stmt.order_by(NewsArticle.published_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())
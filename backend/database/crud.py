
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .models import Base, Series, Event, Market, NewsArticle, ArticleEventLink
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
        index_elements=['market_ticker'],
        set_={k: v for k, v in clean_data.items() if k != 'market_ticker'}
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

async def get_all_markets(session: AsyncSession, status: Optional[str] = None, limit: int = 500) -> List[Market]:
    """Get all markets, optionally filtered by status."""
    stmt = select(Market)
    if status:
        stmt = stmt.where(Market.status == status)
    stmt = stmt.order_by(Market.updated_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_all_articles(session: AsyncSession, limit: int = 100) -> List[NewsArticle]:
    """Get all recent news articles."""
    stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_active_markets(
    session: AsyncSession, 
    limit: int = 300,
    category: Optional[str] = None,
    max_duration_days: Optional[int] = None
) -> List[dict]:
    """
    Get active markets with optional filtering.
    
    Args:
        limit: Max rows
        category: Filter by category (Economy, Politics, etc.)
        max_duration_days: If set, only show markets expiring within X days of opening (short-term)
    """
    # Base query joined with Event and Series
    # We use COALESCE to get the effective category for filtering
    effective_category = func.coalesce(Series.category, Event.category)
    
    stmt = (
        select(Market, Event.category, Series.category)
        .join(Event, Market.event_ticker == Event.event_ticker)
        .outerjoin(Series, Event.series_ticker == Series.ticker)
    )
    
    # Apply Filters
    if category:
        # Case-insensitive match? Our categories are capitalized (Politics, Economy). 
        # Let's match exactly for performance or ILIKE if needed. 
        # The frontend sends "Politics", "Economy".
        stmt = stmt.where(effective_category == category)
        
    if max_duration_days:
        # Filter markets where valid lifespan <= X days
        # duration = expiration - open
        # Postgres interval comparison
        stmt = stmt.where(
            (Market.expiration_time - Market.open_time) <= timedelta(days=max_duration_days)
        )
        
    stmt = stmt.order_by(Market.updated_at.desc()).limit(limit)

    markets_result = await session.execute(stmt)
    rows = markets_result.all()
    
    result = []
    for row in rows:
        market = row[0]
        event_category = row[1]
        series_category = row[2]
        
        # Prefer series category, then event category
        final_category = series_category or event_category
        
        market_dict = {
            "market_ticker": market.market_ticker,
            "event_ticker": market.event_ticker,
            "title": market.title,
            "subtitle": market.subtitle or market.yes_sub_title,
            "category": final_category,
            "status": market.status,
            "close_time": market.close_time.isoformat() if market.close_time else None,
            "yes_price": market.yes_ask if market.yes_ask is not None else 50,
            "no_price": market.no_ask if market.no_ask is not None else 50,
            "volume": market.volume or 0,
            "open_interest": market.open_interest or 0,
            # Pass original ask/bids if needed
            "yes_ask": market.yes_ask,
            "no_ask": market.no_ask,
            "yes_bid": market.yes_bid,
            "no_bid": market.no_bid,
        }
        result.append(market_dict)
    
    return result


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


async def get_hot_events(
    session: AsyncSession, 
    limit: int = 20,
    category: Optional[str] = None,
) -> List[dict]:
    """
    Get hot events sorted by heat_score, with their markets nested.
    This is the new event-centric API for the hot markets page.
    """
    from sqlalchemy.orm import selectinload
    
    # Build base query
    stmt = (
        select(Event)
        .options(
            selectinload(Event.markets),
            selectinload(Event.article_links).selectinload(ArticleEventLink.article)
        )
        .outerjoin(Series, Event.series_ticker == Series.ticker)
    )
    
    # Apply category filter
    if category:
        effective_category = func.coalesce(Series.category, Event.category)
        stmt = stmt.where(effective_category == category)
    
    # Order by pre-computed heat score
    stmt = stmt.order_by(Event.heat_score.desc()).limit(limit)
    
    result = await session.execute(stmt)
    events = result.scalars().unique().all()
    
    # Format response
    hot_events = []
    for event in events:
        # Sort markets by likelihood (yes_ask price) descending
        sorted_markets = sorted(
            event.markets, 
            key=lambda m: m.yes_ask if m.yes_ask is not None else 0, 
            reverse=True
        )

        markets_list = []
        for market in sorted_markets:
            markets_list.append({
                "market_ticker": market.market_ticker,
                "title": market.title,
                "subtitle": market.subtitle or market.yes_sub_title,
                "yes_price": market.yes_ask if market.yes_ask is not None else 50,
                "no_price": market.no_ask if market.no_ask is not None else 50,
                "volume": market.volume or 0,
                "open_interest": market.open_interest or 0,
                "close_time": market.close_time.isoformat() if market.close_time else None,
            })
        
        # Format linked news
        related_news = []
        if event.article_links:
            # Sort by relevance or date? Let's do date for now (newest first)
            sorted_links = sorted(
                event.article_links, 
                key=lambda l: l.article.published_at if l.article.published_at else datetime.min, 
                reverse=True
            )
            
            for link in sorted_links[:3]: # Limit to top 3 articles
                art = link.article
                related_news.append({
                    "title": art.title,
                    "source": art.source,
                    "link": art.url,
                    "published": art.published_at.isoformat() if art.published_at else None,
                    "relevance_score": link.relevance_score
                })

        hot_events.append({
            "event_ticker": event.event_ticker,
            "title": event.title or event.event_ticker,
            "category": event.category or "Other",
            "heat_score": event.heat_score or 0,
            "total_volume": event.total_volume or 0,
            "total_open_interest": event.total_open_interest or 0,
            "markets": markets_list,
            "related_news": related_news
        })
    
    return hot_events
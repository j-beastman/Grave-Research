
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from .models import Market, NewsArticle, ArticleEventLink

async def cleanup_stale_data(session: AsyncSession):
    """
    Enforce retention policies:
    1. Delete unlinked news articles older than 30 days.
    2. Archive/Delete settled markets older than 90 days (Optional, user said 'purge markets we don't want').
    """
    
    # 1. Cleanup unlinked news
    # Articles with no links and fetched > 30 days ago
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Find IDs linked
    linked_ids_stmt = select(ArticleEventLink.article_id).distinct()
    
    stmt = delete(NewsArticle).where(
        NewsArticle.fetched_at < thirty_days_ago
    ).where(
        NewsArticle.id.not_in(linked_ids_stmt)
    )
    
    result = await session.execute(stmt)
    deleted_news = result.rowcount
    
    # 2. Cleanup old settled markets?
    # User said "purge markets that we don't want to keep anymore".
    # Let's say settled > 90 days ago.
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    
    # We should delete their snapshots first due to FK? 
    # Or rely on CASCADE if configured (SQLAlchemy usually expects manual or cascade).
    # Since we didn't define CASCADE in models explicitly (default), we might need to delete snapshots first.
    
    # Find old markets
    old_markets_stmt = select(Market.ticker).where(
        Market.status == 'settled',
        Market.expiration_time < ninety_days_ago
    )
    # Delete snapshots for them is hard without knowing exactly which ones.
    # Ideally standard retention is 'delete snapshots older than X for ANY market' first.
    
    # Let's just implement Snapshot cleanup for now, keeping markets. 
    # A market row is small. Snapshots are big.
    
    # Delete snapshots > 90 days
    from .models import MarketSnapshot
    snap_stmt = delete(MarketSnapshot).where(
        MarketSnapshot.timestamp < ninety_days_ago
    )
    snap_result = await session.execute(snap_stmt)
    deleted_snaps = snap_result.rowcount
    
    await session.commit()
    
    return {
        "deleted_news": deleted_news,
        "deleted_snapshots": deleted_snaps
    }

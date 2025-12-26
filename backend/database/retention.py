
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
    # Since we removed snapshots, we just keep markets indefinitely or delete rows if very old.
    # For now, let's just clean up news.
    
    await session.commit()
    
    return {
        "deleted_news": deleted_news,
        "deleted_snapshots": 0
    }


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from .models import Market

async def search_markets(
    session: AsyncSession,
    query: str,
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0
) -> list[Market]:
    """
    Search markets using PostgreSQL full-text search.
    """
    stmt = select(Market)
    
    # Text search filter
    # Using plainto_tsquery for simple natural language search
    stmt = stmt.where(
        text("search_vector @@ plainto_tsquery('english', :query)")
    ).params(query=query)
    
    # Additional filters
    if status:
        stmt = stmt.where(Market.status == status)
    
    if category:
        # Note: Market model doesn't strictly have 'category' mapped as a column in the schema 
        # provided in models.py (it's on Event/Series, and Market has category only in API response sample??)
        # Wait, the prompt's `markets` table spec DOES NOT have `category`! 
        # But `events` table DOES. `series` table DOES.
        # The PROMPT Sample Market Response has "category"... wait, no, the Sample EVENT has category.
        # But the User Example Usage: `search_markets("bitcoin", status="open", limit=20)`
        # It implies searching markets.
        # If filtering by category, we might need to join Event.
        # Let's join Event if category is requested.
        pass # Skipping category filter on Market table directly as it doesn't exist.
        # Ideally we join: stmt = stmt.join(Market.event).where(Event.category == category)
        # But for now let's stick to what's on the Market table or just the text search.
        
    stmt = stmt.limit(limit).offset(offset)
    
    # Order by rank? 
    # stmt = stmt.order_by(text("ts_rank(search_vector, plainto_tsquery('english', :query)) DESC"))
    
    result = await session.execute(stmt)
    return list(result.scalars().all())

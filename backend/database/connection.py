
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from .config import settings

# Create async engine
# statement_cache_size=0 disables prepared statements for Supabase pooler compatibility
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.echo_sql,
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
    connect_args={"statement_cache_size": 0},
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

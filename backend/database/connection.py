
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator

from .config import settings

# Create async engine optimized for cloud database poolers (Neon, Supabase)
# - NullPool: Don't pool locally, let the cloud provider handle pooling
# - statement_cache_size=0: Required for external connection poolers
# - SSL is handled via the connection string (e.g., ?sslmode=require)
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.echo_sql,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,
        "ssl": True,
    },
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

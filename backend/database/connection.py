
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import ssl

from .config import settings

# Create async engine optimized for Supabase/cloud poolers
# - NullPool: Don't pool locally, let Supabase handle pooling
# - statement_cache_size=0: Required for external connection poolers
# - ssl=require: Required for Supabase connections
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.echo_sql,
    poolclass=NullPool,  # Disable local pooling for serverless
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "ssl": "require",
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

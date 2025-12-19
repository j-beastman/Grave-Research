
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from .config import settings

# Create async engine
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.echo_sql,
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
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

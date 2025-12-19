
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
import uuid

from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text, Float, JSON, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import text

class Base(DeclarativeBase):
    pass

class Series(Base):
    __tablename__ = "series"

    ticker: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    frequency: Mapped[Optional[str]] = mapped_column(String(50))
    tags: Mapped[Optional[dict]] = mapped_column(JSONB)
    settlement_sources: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    events: Mapped[List["Event"]] = relationship(back_populates="series")

class Event(Base):
    __tablename__ = "events"

    event_ticker: Mapped[str] = mapped_column(String(50), primary_key=True)
    series_ticker: Mapped[Optional[str]] = mapped_column(ForeignKey("series.ticker"))
    title: Mapped[Optional[str]] = mapped_column(String(500))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    series: Mapped[Optional["Series"]] = relationship(back_populates="events")
    markets: Mapped[List["Market"]] = relationship(back_populates="event")
    article_links: Mapped[List["ArticleEventLink"]] = relationship(back_populates="event")

class Market(Base):
    __tablename__ = "markets"

    ticker: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_ticker: Mapped[str] = mapped_column(ForeignKey("events.event_ticker"))
    title: Mapped[Optional[str]] = mapped_column(String(500))
    subtitle: Mapped[Optional[str]] = mapped_column(String(500))
    yes_sub_title: Mapped[Optional[str]] = mapped_column(String(255))
    no_sub_title: Mapped[Optional[str]] = mapped_column(String(255))
    market_type: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[Optional[str]] = mapped_column(String(20))
    result: Mapped[Optional[str]] = mapped_column(String(10))
    
    open_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    close_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expiration_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Generated column for search (using raw SQL DDL later or manually updated? 
    # SQLAlchemy supports Computed columns in newer versions, but specific PG TSVECTOR support is via TypeEngine.
    # The prompt asked for `ALTER TABLE ... GENERATED ALWAYS`, so we might need a migration or raw SQL execution in init_db.
    # We will declare it here if possible or just omit from ORM and manage via DB.
    # For simplicity, we'll define a placeholder if needed, but the prompt's search implementation implies using `search_vector`.
    # Let's try to verify if we need to map it. Usually not needed for insert, only for search query.)
    search_vector = mapped_column(TSVECTOR)

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="markets")
    snapshots: Mapped[List["MarketSnapshot"]] = relationship(back_populates="market")

    __table_args__ = (
        Index("idx_markets_search", "search_vector", postgresql_using="gin"),
    )

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_ticker: Mapped[str] = mapped_column(ForeignKey("markets.ticker"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    yes_bid: Mapped[Optional[int]] = mapped_column(Integer)
    yes_ask: Mapped[Optional[int]] = mapped_column(Integer)
    no_bid: Mapped[Optional[int]] = mapped_column(Integer)
    no_ask: Mapped[Optional[int]] = mapped_column(Integer)
    last_price: Mapped[Optional[int]] = mapped_column(Integer)
    
    volume: Mapped[Optional[int]] = mapped_column(Integer)
    volume_24h: Mapped[Optional[int]] = mapped_column(Integer)
    open_interest: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    market: Mapped["Market"] = relationship(back_populates="snapshots")

    __table_args__ = (
        Index("idx_snapshot_market_time", "market_ticker", "timestamp"),
    )

class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))

    # Relationships
    event_links: Mapped[List["ArticleEventLink"]] = relationship(back_populates="article")

class ArticleEventLink(Base):
    __tablename__ = "article_event_links"

    article_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news_articles.id"), primary_key=True)
    event_ticker: Mapped[str] = mapped_column(ForeignKey("events.event_ticker"), primary_key=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    article: Mapped["NewsArticle"] = relationship(back_populates="event_links")
    event: Mapped["Event"] = relationship(back_populates="article_links")

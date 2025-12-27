
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import String, DateTime, ForeignKey, Integer, Float, Text, Index, Computed
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TSVECTOR, JSONB
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    pass

class Series(Base):
    __tablename__ = "series"

    ticker: Mapped[str] = mapped_column(String(50), primary_key=True)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    
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
    
    # Pre-computed aggregates (updated during ingestion)
    heat_score: Mapped[Optional[float]] = mapped_column(Float, default=0)
    total_volume: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    total_open_interest: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    series: Mapped[Optional["Series"]] = relationship(back_populates="events")
    markets: Mapped[List["Market"]] = relationship(back_populates="event")
    article_links: Mapped[List["ArticleEventLink"]] = relationship(back_populates="event")

class Market(Base):
    __tablename__ = "markets"

    market_ticker: Mapped[str] = mapped_column(String(50), primary_key=True)
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
    
    # Generated column for search
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', title || ' ' || coalesce(subtitle, ''))",
            persisted=True
        )
    )
    
    # Vector embedding
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))

    # Price Data (Flattened from obsolete snapshots)
    yes_ask: Mapped[Optional[int]] = mapped_column(Integer)
    no_ask: Mapped[Optional[int]] = mapped_column(Integer)
    yes_bid: Mapped[Optional[int]] = mapped_column(Integer)
    no_bid: Mapped[Optional[int]] = mapped_column(Integer)
    last_price: Mapped[Optional[int]] = mapped_column(Integer)
    volume: Mapped[Optional[int]] = mapped_column(Integer)
    open_interest: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="markets")

    __table_args__ = (
        Index("idx_markets_search", "search_vector", postgresql_using="gin"),
        Index("idx_markets_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_l2_ops"}),
    )

class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    url: Mapped[str] = mapped_column(String(512), unique=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    published_at: Mapped[datetime] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))

    __table_args__ = (
        Index("idx_news_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_l2_ops"}),
    )

class ArticleEventLink(Base):
    __tablename__ = "article_event_links"

    article_id: Mapped[UUID] = mapped_column(ForeignKey("news_articles.id"), primary_key=True)
    event_ticker: Mapped[str] = mapped_column(ForeignKey("events.event_ticker"), primary_key=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    matched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    event: Mapped["Event"] = relationship(back_populates="article_links")
    article: Mapped["NewsArticle"] = relationship()

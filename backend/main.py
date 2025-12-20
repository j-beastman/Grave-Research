"""
Kalshi News Tracker API
Aggregates Kalshi prediction markets and matches them with relevant news.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv
import os

from kalshi_client import KalshiClient, calculate_market_heat, categorize_market
from news_matcher import fetch_all_news, match_news_to_market, group_markets_by_topic, NewsArticle

load_dotenv()

from contextlib import asynccontextmanager
from database import init_db
from ingestion import ingest_kalshi_data
import asyncio

async def background_ingestion_loop():
    """Run ingestion every 10 minutes."""
    while True:
        try:
            print("Starting background ingestion...")
            await ingest_kalshi_data()
            print("Ingestion complete.")
        except Exception as e:
            print(f"Ingestion error: {e}")
        
        await asyncio.sleep(600)  # 10 minutes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    try:
        print("Initializing database tables...")
        await init_db()
        print("Database initialized successfully.")
        
        # Start ingestion task
        asyncio.create_task(background_ingestion_loop())
        
    except Exception as e:
        print(f"WARNING: Database initialization failed: {e}")
        print("Running in stateless mode (no persistence).")
    
    yield

app = FastAPI(
    title="Kalshi News Tracker",
    description="Track prediction market activity alongside relevant news",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache for market and news data
cache = {
    "markets": None,
    "news": None,
    "topics": None,
    "last_updated": None,
}
CACHE_TTL = timedelta(minutes=5)


class TopicSummary(BaseModel):
    name: str
    market_count: int
    total_volume: int
    total_heat: float
    top_markets: list[dict]


class MarketWithNews(BaseModel):
    ticker: str
    title: str
    subtitle: Optional[str]
    category: str
    yes_price: int
    volume: int
    open_interest: int
    heat_score: float
    close_time: Optional[str]
    related_news: list[dict]


async def refresh_cache():
    """Refresh cached data from Kalshi and news sources."""
    api_key = os.getenv("KALSHI_API_KEY")
    client = KalshiClient(api_key=api_key)
    try:
        # Fetch markets
        markets = await client.get_all_open_markets(max_markets=300)
        
        # Add heat scores and categories
        raw_markets = markets
        markets = []
        
        # Deduplicate by title, keeping highest heat score
        markets_by_title = {}
        
        for market in raw_markets:
            market["heat_score"] = calculate_market_heat(market)
            market["category"] = categorize_market(market)
            
            # Use yes_sub_title as subtitle if subtitle is missing (common in multi-outcome markets)
            if not market.get("subtitle") and market.get("yes_sub_title"):
                market["subtitle"] = market.get("yes_sub_title")
            
            title = market.get("title")
            if title not in markets_by_title:
                markets_by_title[title] = market
            else:
                # Keep the "hottest" variant (e.g. most active candidate)
                if market["heat_score"] > markets_by_title[title]["heat_score"]:
                    markets_by_title[title] = market
        
        markets = list(markets_by_title.values())
        
        # Fetch news
        news = await fetch_all_news()
        
        # Group by topic
        topics = group_markets_by_topic(markets)
        
        # Update cache
        cache["markets"] = markets
        cache["news"] = news
        cache["topics"] = topics
        cache["last_updated"] = datetime.now()
        
    finally:
        await client.close()


async def get_cached_data():
    """Get cached data, refreshing if stale."""
    if (
        cache["last_updated"] is None
        or datetime.now() - cache["last_updated"] > CACHE_TTL
    ):
        await refresh_cache()
    return cache


@app.get("/")
async def root():
    return {
        "name": "Kalshi News Tracker API",
        "version": "1.0.0",
        "endpoints": [
            "/topics - Get all topics ranked by activity",
            "/markets - Get all markets with news matches",
            "/markets/{ticker} - Get a specific market with related news",
            "/hot - Get the hottest markets right now",
        ]
    }


@app.get("/topics")
async def get_topics():
    """
    Get all topics/categories ranked by total market activity.
    Returns aggregated heat scores and top markets per topic.
    """
    data = await get_cached_data()
    topics = data["topics"]
    
    result = []
    for name, topic_data in topics.items():
        result.append({
            "name": name,
            "market_count": len(topic_data["markets"]),
            "total_volume": topic_data["total_volume"],
            "total_heat": round(topic_data["total_heat"], 2),
            "top_markets": [
                {
                    "ticker": m["ticker"],
                    "title": m["title"],
                    "yes_price": m.get("yes_price", 50),
                    "volume": m.get("volume", 0),
                    "heat_score": round(m["heat_score"], 2),
                }
                for m in topic_data["markets"][:5]  # Top 5 per topic
            ],
        })
    
    # Sort by total heat
    result.sort(key=lambda t: t["total_heat"], reverse=True)
    return {"topics": result, "last_updated": cache["last_updated"].isoformat()}


@app.get("/markets")
async def get_markets(
    category: Optional[str] = None,
    limit: int = 50,
    min_heat: float = 0,
):
    """
    Get markets sorted by heat score, optionally filtered by category.
    Includes matched news articles for each market.
    """
    data = await get_cached_data()
    markets = data["markets"]
    news = data["news"]
    
    # Filter by category if specified
    if category:
        markets = [m for m in markets if m.get("category", "").lower() == category.lower()]
    
    # Filter by minimum heat
    markets = [m for m in markets if m.get("heat_score", 0) >= min_heat]
    
    # Sort by heat and limit
    markets = sorted(markets, key=lambda m: m.get("heat_score", 0), reverse=True)[:limit]
    
    # Add news matches
    result = []
    for market in markets:
        related_news = match_news_to_market(market, news, max_matches=3)
        result.append({
            "ticker": market["ticker"],
            "title": market["title"],
            "subtitle": market.get("subtitle"),
            "category": market.get("category"),
            "yes_price": market.get("yes_price", 50),
            "no_price": market.get("no_price", 50),
            "volume": market.get("volume", 0),
            "open_interest": market.get("open_interest", 0),
            "heat_score": round(market.get("heat_score", 0), 2),
            "close_time": market.get("close_time"),
            "related_news": related_news,
        })
    
    return {
        "markets": result,
        "count": len(result),
        "last_updated": cache["last_updated"].isoformat(),
    }


@app.get("/markets/{ticker}")
async def get_market(ticker: str):
    """
    Get a specific market with detailed news matches.
    """
    data = await get_cached_data()
    markets = data["markets"]
    news = data["news"]
    
    # Find the market
    market = next((m for m in markets if m["ticker"] == ticker), None)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Get more news matches for single market view
    related_news = match_news_to_market(market, news, max_matches=10)
    
    return {
        "ticker": market["ticker"],
        "title": market["title"],
        "subtitle": market.get("subtitle"),
        "category": market.get("category"),
        "yes_price": market.get("yes_price", 50),
        "no_price": market.get("no_price", 50),
        "volume": market.get("volume", 0),
        "open_interest": market.get("open_interest", 0),
        "heat_score": round(market.get("heat_score", 0), 2),
        "close_time": market.get("close_time"),
        "rules": market.get("rules"),
        "related_news": related_news,
    }


@app.get("/hot")
async def get_hot_markets(limit: int = 20):
    """
    Get the hottest markets right now - highest activity + most news coverage.
    """
    data = await get_cached_data()
    markets = data["markets"]
    news = data["news"]
    
    # Score markets by heat + news relevance
    scored_markets = []
    for market in markets:
        related_news = match_news_to_market(market, news, max_matches=5)
        news_score = sum(n["relevance_score"] for n in related_news)
        
        combined_score = market.get("heat_score", 0) + (news_score * 2)
        
        scored_markets.append({
            "ticker": market["ticker"],
            "event_ticker": market.get("event_ticker"),
            "title": market["title"],
            "category": market.get("category"),
            "yes_price": market.get("yes_price", 50),
            "volume": market.get("volume", 0),
            "open_interest": market.get("open_interest", 0),
            "heat_score": round(market.get("heat_score", 0), 2),
            "news_score": round(news_score, 2),
            "combined_score": round(combined_score, 2),
            "related_news": related_news[:3],
            "close_time": market.get("close_time"),
        })
    
    # Sort by combined score
    scored_markets.sort(key=lambda m: m["combined_score"], reverse=True)
    
    return {
        "hot_markets": scored_markets[:limit],
        "last_updated": cache["last_updated"].isoformat(),
    }


@app.post("/refresh")
async def force_refresh():
    """Force a cache refresh."""
    await refresh_cache()
    return {"status": "refreshed", "timestamp": cache["last_updated"].isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""
Kalshi API Client - Fetches public market data from Kalshi's API.
No authentication required for market data endpoints.
"""

import httpx
from typing import Optional
from datetime import datetime

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def get_markets(
        self,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None,
        series_ticker: Optional[str] = None,
    ) -> dict:
        """
        Fetch markets from Kalshi.
        
        Args:
            status: Filter by market status ('open', 'closed', 'settled')
            limit: Number of results (max 200)
            cursor: Pagination cursor
            series_ticker: Filter by series
        """
        params = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker

        response = await self.client.get(f"{BASE_URL}/markets", params=params)
        response.raise_for_status()
        return response.json()

    async def get_all_open_markets(self, max_markets: int = 500) -> list:
        """Fetch all open markets with pagination."""
        all_markets = []
        cursor = None

        while len(all_markets) < max_markets:
            data = await self.get_markets(status="open", limit=200, cursor=cursor)
            markets = data.get("markets", [])
            if not markets:
                break
            all_markets.extend(markets)
            cursor = data.get("cursor")
            if not cursor:
                break

        return all_markets[:max_markets]

    async def get_event(self, event_ticker: str) -> dict:
        """Fetch details for a specific event."""
        response = await self.client.get(f"{BASE_URL}/events/{event_ticker}")
        response.raise_for_status()
        return response.json()

    async def get_series(self, series_ticker: str) -> dict:
        """Fetch details for a specific series."""
        response = await self.client.get(f"{BASE_URL}/series/{series_ticker}")
        response.raise_for_status()
        return response.json()

    async def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        """Fetch orderbook for a market."""
        response = await self.client.get(
            f"{BASE_URL}/markets/{ticker}/orderbook",
            params={"depth": depth}
        )
        response.raise_for_status()
        return response.json()


def calculate_market_heat(market: dict) -> float:
    """
    Calculate a 'heat score' for a market based on activity metrics.
    Higher score = more newsworthy/active.
    
    Factors:
    - Volume (total contracts traded)
    - Open interest
    - Recent price movement
    - Liquidity
    """
    volume = market.get("volume", 0) or 0
    open_interest = market.get("open_interest", 0) or 0
    yes_price = market.get("yes_price", 50) or 50
    
    # Volume is the primary signal
    volume_score = min(volume / 10000, 10)  # Cap at 10
    
    # Open interest shows sustained attention
    oi_score = min(open_interest / 5000, 5)  # Cap at 5
    
    # Markets near 50/50 are more "active" debates
    price_uncertainty = 1 - abs(yes_price - 50) / 50
    uncertainty_score = price_uncertainty * 3
    
    return volume_score + oi_score + uncertainty_score


def categorize_market(market: dict) -> str:
    """
    Categorize a market based on its category field and title keywords.
    """
    category = market.get("category", "").lower()
    title = market.get("title", "").lower()
    
    # Map Kalshi categories to our simplified categories
    category_map = {
        "politics": "Politics",
        "economics": "Economy",
        "financial": "Economy",
        "fed": "Economy",
        "climate": "Climate",
        "weather": "Weather",
        "sports": "Sports",
        "entertainment": "Entertainment",
        "tech": "Technology",
        "science": "Science",
        "crypto": "Crypto",
        "world": "World",
    }
    
    # Check category field first
    for key, value in category_map.items():
        if key in category:
            return value
    
    # Fall back to title keyword matching
    title_keywords = {
        "Politics": ["trump", "biden", "election", "congress", "senate", "president", "governor", "vote"],
        "Economy": ["fed", "inflation", "gdp", "unemployment", "rate", "recession", "jobs", "cpi"],
        "Weather": ["temperature", "hurricane", "rain", "snow", "weather", "storm"],
        "Sports": ["nfl", "nba", "mlb", "super bowl", "championship", "game", "match"],
        "Technology": ["ai", "openai", "google", "apple", "microsoft", "tech"],
        "Crypto": ["bitcoin", "ethereum", "crypto", "btc", "eth"],
        "Entertainment": ["oscar", "emmy", "movie", "film", "grammy", "album"],
    }
    
    for cat, keywords in title_keywords.items():
        if any(kw in title for kw in keywords):
            return cat
    
    return "Other"

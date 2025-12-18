"""
Kalshi API Client - Fetches market data from Kalshi's API.
Supports public market data endpoints.
"""

import httpx
import os
import time
import json
import logging
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KALSHI_API_KEY")
        
        # Base headers
        headers = {"Content-Type": "application/json"}
        self.client = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def close(self):
        await self.client.aclose()

    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None, 
        json_data: Optional[Dict] = None
    ) -> Any:
        """Make request to Kalshi API"""
        url = f"{BASE_URL}{endpoint}"
        
        # Prepare headers
        headers = {}
        # Add API key if available (helpful for rate limits)
        if self.api_key:
            headers["KALSHI-ACCESS-KEY"] = self.api_key

        try:
            response = await self.client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {endpoint}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"API request failed for {endpoint}: {e}")
            raise

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

        return await self._request("GET", "/markets", params=params)

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

    async def get_market(self, ticker: str) -> dict:
        """Get detailed information about a specific market"""
        response = await self._request("GET", f"/markets/{ticker}")
        return response.get("market", {})

    async def get_event(self, event_ticker: str) -> dict:
        """Fetch details for a specific event."""
        return await self._request("GET", f"/events/{event_ticker}")

    async def get_series(self, series_ticker: str) -> dict:
        """Fetch details for a specific series."""
        return await self._request("GET", f"/series/{series_ticker}")

    async def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        """Fetch orderbook for a market"""
        try:
            response = await self._request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth})
            
            # Helper to format orderbook
            formatted = {"yes": [], "no": []}
            
            # Handle variable response structure
            orderbook = response.get("orderbook", response) if isinstance(response, dict) else response
            if not isinstance(orderbook, dict):
                return formatted
                
            for side in ["yes", "no"]:
                data = orderbook.get(side, [])
                if isinstance(data, list):
                    for level in data:
                        if isinstance(level, dict):
                            formatted[side].append({
                                "price": level.get("price", 0),
                                "size": level.get("size", 0)
                            })
            return formatted
        except Exception as e:
            logger.error(f"Error parsing orderbook/fetching for {ticker}: {e}")
            return {"yes": [], "no": []}

    async def get_trades(self, ticker: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for a specific market"""
        try:
            response = await self._request("GET", f"/markets/{ticker}/trades", params={"limit": limit})
            trades = response.get("trades", [])
            
            formatted_trades = []
            for trade in trades:
                formatted_trades.append({
                    "trade_id": trade.get("trade_id", ""),
                    "ticker": ticker,
                    "price": trade.get("yes_price", 0),
                    "count": trade.get("count", 0),
                    "yes_price": trade.get("yes_price", 0),
                    "no_price": trade.get("no_price", 0),
                    "taker_side": trade.get("taker_side", ""),
                    "timestamp": trade.get("created_time", ""),
                    "created_time": trade.get("created_time", "")
                })
            return formatted_trades
        except Exception:
            return []

    async def get_market_history(self, ticker: str, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[Dict]:
        """Get historical price data"""
        params = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
            
        try:
            response = await self._request("GET", f"/markets/{ticker}/history", params=params)
            return response.get("history", [])
        except Exception:
            return []

    async def search_markets(self, query: str, limit: int = 20) -> List[Dict]:
        """Search markets by title or ticker"""
        params = {"query": query, "limit": limit}
        try:
            response = await self._request("GET", "/markets/search", params=params)
            return response.get("markets", [])
        except Exception:
            return []


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

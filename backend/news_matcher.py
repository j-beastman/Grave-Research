"""
News fetching and matching module.
Fetches news from RSS feeds and matches them to Kalshi markets.
"""

import feedparser
import re
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class NewsArticle:
    title: str
    link: str
    source: str
    published: Optional[datetime]
    summary: str


# Major news RSS feeds organized by category
NEWS_FEEDS = {
    "general": [
        ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
        ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
        ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ],
    "politics": [
        ("Politico", "https://www.politico.com/rss/politicopicks.xml"),
        ("The Hill", "https://thehill.com/feed/"),
    ],
    "economy": [
        ("WSJ Markets", "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain"),
        ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
    ],
    "technology": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ],
    "sports": [
        ("ESPN", "https://www.espn.com/espn/rss/news"),
    ],
}


def extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text."""
    # Remove common words and extract significant terms
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "can", "need",
        "this", "that", "these", "those", "it", "its", "as", "if", "when",
        "than", "so", "no", "not", "only", "very", "just", "also", "into",
        "over", "such", "through", "after", "before", "between", "under",
        "again", "there", "about", "out", "up", "down", "more", "most", "other",
        "some", "any", "all", "both", "each", "few", "many", "much", "own",
        "same", "new", "first", "last", "long", "great", "little", "own",
        "market", "markets", "price", "prices", "higher", "lower", "yes", "no",
    }
    
    # Clean and tokenize
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    
    # Filter and return
    keywords = {w for w in words if len(w) > 2 and w not in stop_words}
    return keywords


def calculate_relevance_score(market_keywords: set, article_keywords: set) -> float:
    """
    Calculate how relevant an article is to a market.
    Returns a score from 0 to 1.
    """
    if not market_keywords or not article_keywords:
        return 0.0
    
    # Jaccard-like similarity with boost for exact matches
    intersection = market_keywords & article_keywords
    if not intersection:
        return 0.0
    
    # Weight by number of matches and proportion
    match_count = len(intersection)
    proportion = match_count / min(len(market_keywords), len(article_keywords))
    
    # Boost for multiple matches
    score = proportion * (1 + 0.1 * match_count)
    return min(score, 1.0)


async def fetch_news_from_feed(feed_url: str, source_name: str) -> list[NewsArticle]:
    """Fetch news articles from a single RSS feed."""
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        
        for entry in feed.entries[:20]:  # Limit to 20 per feed
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except:
                    pass
            
            summary = ""
            if hasattr(entry, 'summary'):
                summary = re.sub(r'<[^>]+>', '', entry.summary)[:300]
            
            articles.append(NewsArticle(
                title=entry.get('title', ''),
                link=entry.get('link', ''),
                source=source_name,
                published=published,
                summary=summary,
            ))
        
        return articles
    except Exception as e:
        print(f"Error fetching {source_name}: {e}")
        return []


async def fetch_all_news() -> list[NewsArticle]:
    """Fetch news from all configured RSS feeds."""
    all_articles = []
    
    for category, feeds in NEWS_FEEDS.items():
        for source_name, feed_url in feeds:
            articles = await fetch_news_from_feed(feed_url, source_name)
            all_articles.extend(articles)
    
    # Sort by published date (newest first)
    all_articles.sort(
        key=lambda a: a.published or datetime.min,
        reverse=True
    )
    
    return all_articles


def match_news_to_market(market: dict, articles: list[NewsArticle], max_matches: int = 5) -> list[dict]:
    """
    Find news articles that are relevant to a given market.
    Returns a list of matched articles with relevance scores.
    """
    market_text = f"{market.get('title', '')} {market.get('subtitle', '')} {market.get('category', '')}"
    market_keywords = extract_keywords(market_text)
    
    matches = []
    for article in articles:
        article_text = f"{article.title} {article.summary}"
        article_keywords = extract_keywords(article_text)
        
        score = calculate_relevance_score(market_keywords, article_keywords)
        
        if score > 0.15:  # Minimum relevance threshold
            matches.append({
                "title": article.title,
                "link": article.link,
                "source": article.source,
                "published": article.published.isoformat() if article.published else None,
                "relevance_score": round(score, 3),
            })
    
    # Sort by relevance and return top matches
    matches.sort(key=lambda x: x["relevance_score"], reverse=True)
    return matches[:max_matches]


def group_markets_by_topic(markets: list[dict]) -> dict[str, list[dict]]:
    """
    Group markets by detected topic/category.
    Also calculates aggregate heat for each topic.
    """
    from kalshi_client import categorize_market, calculate_market_heat
    
    topics = {}
    
    for market in markets:
        category = categorize_market(market)
        heat = calculate_market_heat(market)
        
        if category not in topics:
            topics[category] = {
                "markets": [],
                "total_heat": 0,
                "total_volume": 0,
            }
        
        market_data = {
            **market,
            "heat_score": heat,
            "category": category,
        }
        
        topics[category]["markets"].append(market_data)
        topics[category]["total_heat"] += heat
        topics[category]["total_volume"] += market.get("volume", 0) or 0
    
    # Sort markets within each topic by heat
    for topic in topics.values():
        topic["markets"].sort(key=lambda m: m["heat_score"], reverse=True)
    
    return topics

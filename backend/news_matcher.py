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
# Major news RSS feeds organized by category
NEWS_FEEDS = {
    "general": [
        ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
        ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
        ("NPR", "https://feeds.npr.org/1001/rss.xml"),
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("CNN", "http://rss.cnn.com/rss/cnn_topstories.rss"),
        ("NYT", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    ],
    "politics": [
        ("Politico", "https://www.politico.com/rss/politicopicks.xml"),
        ("The Hill", "https://thehill.com/feed/"),
        ("RealClearPolitics", "https://www.realclearpolitics.com/index.xml"),
        ("CNN Politics", "http://rss.cnn.com/rss/cnn_allpolitics.rss"),
        ("Fox News Politics", "https://moxie.foxnews.com/google-publisher/politics.xml"),
    ],
    "economy": [
        ("WSJ Markets", "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain"),
        ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
        ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
        ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/"),
    ],
    "technology": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Wired", "https://www.wired.com/feed/rss"),
        ("Engadget", "https://www.engadget.com/rss.xml"),
    ],
    "science": [
        ("ScienceDaily", "https://www.sciencedaily.com/rss/top_news.xml"),
        ("NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    ],
    "crypto": [
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ],
    "sports": [
        ("ESPN", "https://www.espn.com/espn/rss/news"),
        ("CBS Sports", "https://www.cbssports.com/rss/headlines/"),
    ],
    "entertainment": [
        ("Variety", "https://variety.com/feed/"),
        ("Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
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
        "year", "years", "today", "yesterday", "tomorrow", "week", "month",
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
        
        for entry in feed.entries[:50]:  # Limit to 50 per feed (Increased from 20)
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


def match_news_to_market(market: dict, articles: list, max_matches: int = 5) -> list[dict]:
    """
    Find news articles that are relevant to a given market.
    Returns a list of matched articles with relevance scores.
    Accepts articles as either NewsArticle objects or dicts.
    """
    market_text = f"{market.get('title', '')} {market.get('subtitle', '')} {market.get('category', '')}"
    market_keywords = extract_keywords(market_text)
    
    matches = []
    for article in articles:
        # Handle both NewsArticle objects and dicts
        if isinstance(article, dict):
            title = article.get("title", "")
            summary = article.get("summary", "")
            link = article.get("link", "")
            source = article.get("source", "")
            published = article.get("published")
        else:
            title = article.title
            summary = article.summary
            link = article.link
            source = article.source
            published = article.published.isoformat() if article.published else None
        
        article_text = f"{title} {summary}"
        article_keywords = extract_keywords(article_text)
        
        score = calculate_relevance_score(market_keywords, article_keywords)
        
        if score > 0.15:  # Minimum relevance threshold
            matches.append({
                "title": title,
                "link": link,
                "source": source,
                "published": published if isinstance(published, str) else (published.isoformat() if published else None),
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


async def match_articles_to_events(session, articles: list):
    """
    Match a list of news articles to events using vector similarity.
    Strategy: 
    1. For each article, search for closest Markets using embedding.
    2. Aggregate market matches to their parent Event.
    3. Create ArticleEventLink records.
    """
    from database import Market, ArticleEventLink
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    if not articles:
        return

    # Process articles that have embeddings
    for article in articles:
        # Check for embedding being set and not empty (handle list or numpy array)
        if hasattr(article, 'embedding') and article.embedding is not None and len(article.embedding) > 0:
            pass
        else:
            continue
            
        # Vector search: Find top 3 closest markets
        # Note: pgvector <-> operator is L2 distance. Smaller is better.
        stmt = select(Market).order_by(
            Market.embedding.l2_distance(article.embedding)
        ).limit(3)
        
        result = await session.execute(stmt)
        closest_markets = result.scalars().all()
        
        # Aggregate to events
        event_scores = {}
        for market in closest_markets:
            if not market.event_ticker:
                continue
            
            # Simple link: if article is close to a market, it's relevant to the event
            event_scores[market.event_ticker] = 1.0 
            
        # Create/Update links
        for event_ticker, score in event_scores.items():
            link_stmt = insert(ArticleEventLink).values(
                article_id=article.id,
                event_ticker=event_ticker,
                relevance_score=score
            ).on_conflict_do_nothing()
            
            await session.execute(link_stmt)
            
    await session.commit()

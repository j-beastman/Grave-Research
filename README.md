# Kalshi Pulse

**Prediction markets meet the news cycle.** Track what stories are generating the most attention on Kalshi prediction markets, and see relevant news coverage alongside market activity.

![Kalshi Pulse](https://via.placeholder.com/800x400/0a0a0f/22d3ee?text=Kalshi+Pulse)

## Features

- **Hot Markets** - See the most active markets ranked by trading volume + news coverage
- **Topic Browsing** - Explore markets organized by category (Politics, Economy, Tech, Sports, etc.)
- **News Matching** - Automatically links relevant news articles to each market
- **Heat Scores** - Custom metric combining volume, open interest, and price uncertainty
- **Real-time Data** - Pulls live data from Kalshi's public API

## Architecture

```
┌─────────────────────────────────────────┐
│         React Frontend (Vite)           │
│  • Market cards with news               │
│  • Topic-based browsing                 │
│  • Heat score visualization             │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         Python Backend (FastAPI)        │
│  • Aggregates Kalshi markets            │
│  • Fetches news from RSS feeds          │
│  • Matches news to markets (NLP)        │
│  • Caches results (5 min TTL)           │
└─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  [Kalshi API]            [News RSS Feeds]
  (public, no auth)       (Reuters, AP, etc.)
```

## Quick Start

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
# Or with uvicorn for hot reload:
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. You can explore endpoints at `http://localhost:8000/docs`.

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /topics` | All topics ranked by aggregate market activity |
| `GET /markets` | All markets with news matches, sorted by heat |
| `GET /markets/{ticker}` | Single market with detailed news matches |
| `GET /hot` | Top markets by combined heat + news score |
| `POST /refresh` | Force a cache refresh |

### Example Response

```json
{
  "hot_markets": [
    {
      "ticker": "FED-DEC-25",
      "title": "Fed cuts rates at December meeting",
      "category": "Economy",
      "yes_price": 78,
      "volume": 320000,
      "heat_score": 11.2,
      "combined_score": 18.4,
      "related_news": [
        {
          "title": "Fed officials signal openness to rate cuts",
          "source": "Reuters",
          "relevance_score": 0.82
        }
      ]
    }
  ]
}
```

## How It Works

### Heat Score Calculation

Markets are ranked by a "heat score" that combines:

- **Volume** (contracts traded) - primary signal
- **Open Interest** (outstanding positions) - sustained attention
- **Price Uncertainty** (proximity to 50%) - active debate

### News Matching

News articles are matched to markets using keyword extraction and relevance scoring:

1. Extract significant keywords from market titles
2. Extract keywords from news headlines + summaries
3. Calculate Jaccard-like similarity
4. Filter by relevance threshold (>0.15)

### Data Sources

- **Markets**: Kalshi public API (no auth required)
- **News**: RSS feeds from Reuters, AP, Politico, CNBC, TechCrunch, ESPN, etc.

## Configuration

### Adding News Sources

Edit `news_matcher.py` to add more RSS feeds:

```python
NEWS_FEEDS = {
    "general": [
        ("Source Name", "https://feed-url.com/rss"),
    ],
    # ...
}
```

### Adjusting Categories

Edit `kalshi_client.py` to modify category detection:

```python
category_map = {
    "keyword": "Category Name",
    # ...
}
```

## Deployment

### Backend (Python)

Recommended: Deploy to Railway, Render, or Fly.io

```bash
# Procfile for Heroku/Railway
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Frontend (React)

Recommended: Deploy to Vercel or Netlify

```bash
npm run build
# Deploy the `dist` folder
```

Update `API_BASE` in `App.jsx` to point to your deployed backend.

## Future Ideas

- [ ] WebSocket for real-time price updates
- [ ] Historical price charts
- [ ] Email alerts for big market moves
- [ ] More sophisticated NLP for news matching
- [ ] User accounts to save favorite markets
- [ ] Mobile app

## License

MIT

---

Built with ❤️ for prediction market enthusiasts

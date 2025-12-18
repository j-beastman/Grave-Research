import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

// Mock data for demo when API isn't available
const MOCK_DATA = {
  topics: [
    {
      name: 'Politics', market_count: 45, total_volume: 2500000, total_heat: 89.5, top_markets: [
        { ticker: 'PRES-2028-DEM', title: 'Democratic nominee for 2028 presidential election', yes_price: 34, volume: 450000, heat_score: 12.4 },
        { ticker: 'SENATE-GA', title: 'Republicans win Georgia Senate seat', yes_price: 62, volume: 180000, heat_score: 8.7 },
      ]
    },
    {
      name: 'Economy', market_count: 32, total_volume: 1800000, total_heat: 72.3, top_markets: [
        { ticker: 'FED-DEC-25', title: 'Fed cuts rates in December 2025', yes_price: 78, volume: 320000, heat_score: 11.2 },
        { ticker: 'RECESSION-2026', title: 'US recession by end of 2026', yes_price: 28, volume: 250000, heat_score: 9.1 },
      ]
    },
    {
      name: 'Technology', market_count: 18, total_volume: 950000, total_heat: 45.2, top_markets: [
        { ticker: 'OPENAI-IPO', title: 'OpenAI IPO by 2026', yes_price: 45, volume: 180000, heat_score: 7.8 },
      ]
    },
    {
      name: 'Sports', market_count: 28, total_volume: 720000, total_heat: 38.9, top_markets: [
        { ticker: 'SB-2026', title: 'Chiefs win Super Bowl 2026', yes_price: 18, volume: 95000, heat_score: 5.2 },
      ]
    },
  ],
  hot_markets: [
    {
      ticker: 'FED-DEC-25', title: 'Fed cuts rates at December meeting', category: 'Economy', yes_price: 78, volume: 320000, heat_score: 11.2, combined_score: 18.4, related_news: [
        { title: 'Fed officials signal openness to rate cuts amid cooling inflation', source: 'Reuters', relevance_score: 0.82 },
        { title: 'Markets price in 80% chance of December rate cut', source: 'CNBC', relevance_score: 0.75 },
      ]
    },
    {
      ticker: 'PRES-2028-DEM', title: 'Democratic nominee for 2028', category: 'Politics', yes_price: 34, volume: 450000, heat_score: 12.4, combined_score: 16.8, related_news: [
        { title: 'Early 2028 polling shows tight Democratic primary field', source: 'Politico', relevance_score: 0.68 },
      ]
    },
    {
      ticker: 'OPENAI-IPO', title: 'OpenAI announces IPO by end of 2026', category: 'Technology', yes_price: 45, volume: 180000, heat_score: 7.8, combined_score: 14.2, related_news: [
        { title: 'OpenAI in talks for new funding round at $150B valuation', source: 'TechCrunch', relevance_score: 0.89 },
        { title: 'Sam Altman discusses potential public offering timeline', source: 'The Verge', relevance_score: 0.71 },
      ]
    },
  ]
};

function App() {
  const [activeTab, setActiveTab] = useState('hot');
  const [topics, setTopics] = useState([]);
  const [hotMarkets, setHotMarkets] = useState([]);
  const [selectedTopic, setSelectedTopic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [topicsRes, hotRes] = await Promise.all([
        fetch(`${API_BASE}/topics`),
        fetch(`${API_BASE}/hot?limit=15`),
      ]);

      if (!topicsRes.ok || !hotRes.ok) throw new Error('API unavailable');

      const topicsData = await topicsRes.json();
      const hotData = await hotRes.json();

      setTopics(topicsData.topics);
      setHotMarkets(hotData.hot_markets);
      setLastUpdated(new Date(topicsData.last_updated));
      setError(null);
    } catch (err) {
      console.log('Using mock data - API not available');
      setTopics(MOCK_DATA.topics);
      setHotMarkets(MOCK_DATA.hot_markets);
      setLastUpdated(new Date());
      setError('Demo mode - connect backend for live data');
    } finally {
      setLoading(false);
    }
  };

  const formatPrice = (price) => `${price}¢`;
  const formatVolume = (vol) => {
    if (vol >= 1000000) return `$${(vol / 1000000).toFixed(1)}M`;
    if (vol >= 1000) return `$${(vol / 1000).toFixed(0)}K`;
    return `$${vol}`;
  };

  const getHeatColor = (heat) => {
    if (heat >= 10) return '#ff3b3b';
    if (heat >= 7) return '#ff8c42';
    if (heat >= 4) return '#ffd166';
    return '#7ec8e3';
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <h1 style={styles.logo}>
            <span style={styles.logoK}>K</span>ALSHI
            <span style={styles.logoAccent}>PULSE</span>
          </h1>
          <p style={styles.tagline}>Prediction markets meet the news cycle</p>
        </div>
        <div style={styles.headerRight}>
          {lastUpdated && (
            <span style={styles.timestamp}>
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button onClick={fetchData} style={styles.refreshBtn}>
            ↻ Refresh
          </button>
        </div>
      </header>

      {error && <div style={styles.errorBanner}>{error}</div>}

      {/* Navigation */}
      <nav style={styles.nav}>
        <button
          onClick={() => setActiveTab('hot')}
          style={{ ...styles.navBtn, ...(activeTab === 'hot' ? styles.navBtnActive : {}) }}
        >
          🔥 Hot Markets
        </button>
        <button
          onClick={() => setActiveTab('topics')}
          style={{ ...styles.navBtn, ...(activeTab === 'topics' ? styles.navBtnActive : {}) }}
        >
          📊 By Topic
        </button>
      </nav>

      {/* Main Content */}
      <main style={styles.main}>
        {loading ? (
          <div style={styles.loading}>Loading markets...</div>
        ) : activeTab === 'hot' ? (
          <HotMarketsView markets={hotMarkets} formatPrice={formatPrice} formatVolume={formatVolume} getHeatColor={getHeatColor} />
        ) : (
          <TopicsView
            topics={topics}
            selectedTopic={selectedTopic}
            setSelectedTopic={setSelectedTopic}
            formatPrice={formatPrice}
            formatVolume={formatVolume}
            getHeatColor={getHeatColor}
          />
        )}
      </main>

      {/* Footer */}
      <footer style={styles.footer}>
        <p>Data from Kalshi prediction markets • News from major RSS feeds • Not financial advice</p>
      </footer>
    </div>
  );
}

function HotMarketsView({ markets, formatPrice, formatVolume, getHeatColor }) {
  return (
    <div style={styles.hotContainer}>
      <div style={styles.sectionHeader}>
        <h2 style={styles.sectionTitle}>Trending Now</h2>
        <p style={styles.sectionSubtitle}>Markets with the highest activity + news coverage</p>
      </div>

      <div style={styles.marketGrid}>
        {markets.map((market, idx) => (
          <div key={market.ticker} style={{ ...styles.marketCard, animationDelay: `${idx * 0.05}s` }}>
            <div style={styles.marketHeader}>
              <span style={styles.marketCategory}>{market.category}</span>
              <span style={{ ...styles.heatBadge, backgroundColor: getHeatColor(market.heat_score) }}>
                {market.combined_score.toFixed(1)} 🔥
              </span>
            </div>

            <h3 style={styles.marketTitle}>{market.title}</h3>

            <div style={styles.priceRow}>
              <div style={styles.priceBox}>
                <span style={styles.priceLabel}>YES</span>
                <span style={{ ...styles.priceValue, color: market.yes_price > 50 ? '#4ade80' : '#f87171' }}>
                  {formatPrice(market.yes_price)}
                </span>
              </div>
              <div style={styles.volumeBox}>
                <span style={styles.volumeLabel}>Volume</span>
                <span style={styles.volumeValue}>{formatVolume(market.volume)}</span>
              </div>
            </div>

            {market.related_news && market.related_news.length > 0 && (
              <div style={styles.newsSection}>
                <span style={styles.newsLabel}>Related News</span>
                {market.related_news.slice(0, 2).map((news, nIdx) => (
                  <div key={nIdx} style={styles.newsItem}>
                    <span style={styles.newsSource}>{news.source}</span>
                    <p style={styles.newsTitle}>{news.title}</p>
                  </div>
                ))}
              </div>
            )}

            <a
              href={`https://kalshi.com/markets/${market.ticker}`}
              target="_blank"
              rel="noopener noreferrer"
              style={styles.viewLink}
            >
              View on Kalshi →
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopicsView({ topics, selectedTopic, setSelectedTopic, formatPrice, formatVolume, getHeatColor }) {
  return (
    <div style={styles.topicsContainer}>
      <div style={styles.sectionHeader}>
        <h2 style={styles.sectionTitle}>Markets by Topic</h2>
        <p style={styles.sectionSubtitle}>Explore prediction market activity across categories</p>
      </div>

      <div style={styles.topicGrid}>
        {topics.map((topic) => (
          <div
            key={topic.name}
            style={{
              ...styles.topicCard,
              ...(selectedTopic === topic.name ? styles.topicCardSelected : {})
            }}
            onClick={() => setSelectedTopic(selectedTopic === topic.name ? null : topic.name)}
          >
            <div style={styles.topicHeader}>
              <h3 style={styles.topicName}>{topic.name}</h3>
              <span style={{ ...styles.topicHeat, color: getHeatColor(topic.total_heat / topic.market_count) }}>
                {topic.total_heat.toFixed(1)}
              </span>
            </div>

            <div style={styles.topicStats}>
              <div style={styles.topicStat}>
                <span style={styles.statValue}>{topic.market_count}</span>
                <span style={styles.statLabel}>markets</span>
              </div>
              <div style={styles.topicStat}>
                <span style={styles.statValue}>{formatVolume(topic.total_volume)}</span>
                <span style={styles.statLabel}>volume</span>
              </div>
            </div>

            {selectedTopic === topic.name && topic.top_markets && (
              <div style={styles.topicMarkets}>
                {topic.top_markets.map((m) => (
                  <div key={m.ticker} style={styles.miniMarket}>
                    <span style={styles.miniTitle}>{m.title}</span>
                    <div style={styles.miniStats}>
                      <span style={{ color: m.yes_price > 50 ? '#4ade80' : '#f87171' }}>
                        {formatPrice(m.yes_price)}
                      </span>
                      <span style={styles.miniVolume}>{formatVolume(m.volume)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#0a0a0f',
    color: '#e4e4e7',
    fontFamily: "'IBM Plex Sans', -apple-system, sans-serif",
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '24px 40px',
    borderBottom: '1px solid #27272a',
    background: 'linear-gradient(180deg, #0f0f15 0%, #0a0a0f 100%)',
  },
  headerLeft: {},
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  logo: {
    fontSize: '28px',
    fontWeight: 700,
    letterSpacing: '-0.5px',
    margin: 0,
    fontFamily: "'Space Mono', monospace",
  },
  logoK: {
    color: '#22d3ee',
    fontSize: '32px',
  },
  logoAccent: {
    color: '#a78bfa',
    marginLeft: '4px',
    fontWeight: 400,
  },
  tagline: {
    color: '#71717a',
    fontSize: '14px',
    marginTop: '4px',
  },
  timestamp: {
    color: '#52525b',
    fontSize: '13px',
    fontFamily: "'Space Mono', monospace",
  },
  refreshBtn: {
    background: 'transparent',
    border: '1px solid #3f3f46',
    color: '#a1a1aa',
    padding: '8px 16px',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    transition: 'all 0.2s',
  },
  errorBanner: {
    background: '#451a03',
    color: '#fbbf24',
    padding: '12px 40px',
    fontSize: '14px',
    borderBottom: '1px solid #78350f',
  },
  nav: {
    display: 'flex',
    gap: '8px',
    padding: '16px 40px',
    borderBottom: '1px solid #18181b',
  },
  navBtn: {
    background: 'transparent',
    border: 'none',
    color: '#71717a',
    padding: '10px 20px',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '15px',
    fontWeight: 500,
    transition: 'all 0.2s',
  },
  navBtnActive: {
    background: '#27272a',
    color: '#fafafa',
  },
  main: {
    padding: '32px 40px',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  loading: {
    textAlign: 'center',
    padding: '80px',
    color: '#71717a',
    fontSize: '18px',
  },
  sectionHeader: {
    marginBottom: '32px',
  },
  sectionTitle: {
    fontSize: '24px',
    fontWeight: 600,
    margin: 0,
    color: '#fafafa',
  },
  sectionSubtitle: {
    color: '#71717a',
    fontSize: '15px',
    marginTop: '6px',
  },
  hotContainer: {},
  marketGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
    gap: '20px',
  },
  marketCard: {
    background: 'linear-gradient(135deg, #18181b 0%, #0f0f12 100%)',
    border: '1px solid #27272a',
    borderRadius: '12px',
    padding: '24px',
    transition: 'all 0.2s',
    animation: 'fadeIn 0.4s ease-out forwards',
    opacity: 0,
  },
  marketHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  marketCategory: {
    fontSize: '12px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '1px',
    color: '#a78bfa',
  },
  heatBadge: {
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: 600,
    color: '#0a0a0f',
  },
  marketTitle: {
    fontSize: '17px',
    fontWeight: 500,
    lineHeight: 1.4,
    margin: '0 0 16px 0',
    color: '#fafafa',
  },
  priceRow: {
    display: 'flex',
    gap: '16px',
    marginBottom: '16px',
  },
  priceBox: {
    flex: 1,
    background: '#0f0f12',
    padding: '12px',
    borderRadius: '8px',
    textAlign: 'center',
  },
  priceLabel: {
    display: 'block',
    fontSize: '11px',
    fontWeight: 600,
    color: '#52525b',
    marginBottom: '4px',
    letterSpacing: '1px',
  },
  priceValue: {
    fontSize: '24px',
    fontWeight: 700,
    fontFamily: "'Space Mono', monospace",
  },
  volumeBox: {
    flex: 1,
    background: '#0f0f12',
    padding: '12px',
    borderRadius: '8px',
    textAlign: 'center',
  },
  volumeLabel: {
    display: 'block',
    fontSize: '11px',
    fontWeight: 600,
    color: '#52525b',
    marginBottom: '4px',
    letterSpacing: '1px',
  },
  volumeValue: {
    fontSize: '20px',
    fontWeight: 600,
    color: '#22d3ee',
    fontFamily: "'Space Mono', monospace",
  },
  newsSection: {
    borderTop: '1px solid #27272a',
    paddingTop: '16px',
    marginBottom: '16px',
  },
  newsLabel: {
    fontSize: '11px',
    fontWeight: 600,
    color: '#52525b',
    textTransform: 'uppercase',
    letterSpacing: '1px',
    display: 'block',
    marginBottom: '10px',
  },
  newsItem: {
    marginBottom: '10px',
  },
  newsSource: {
    fontSize: '11px',
    color: '#a78bfa',
    fontWeight: 600,
  },
  newsTitle: {
    fontSize: '13px',
    color: '#a1a1aa',
    margin: '2px 0 0 0',
    lineHeight: 1.4,
  },
  viewLink: {
    display: 'block',
    textAlign: 'center',
    color: '#22d3ee',
    textDecoration: 'none',
    fontSize: '14px',
    fontWeight: 500,
    padding: '10px',
    borderRadius: '6px',
    background: 'rgba(34, 211, 238, 0.1)',
    transition: 'all 0.2s',
  },
  topicsContainer: {},
  topicGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '16px',
  },
  topicCard: {
    background: '#18181b',
    border: '1px solid #27272a',
    borderRadius: '12px',
    padding: '20px',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  topicCardSelected: {
    borderColor: '#a78bfa',
    background: 'linear-gradient(135deg, #1e1b4b 0%, #18181b 100%)',
  },
  topicHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  topicName: {
    fontSize: '18px',
    fontWeight: 600,
    margin: 0,
  },
  topicHeat: {
    fontSize: '20px',
    fontWeight: 700,
    fontFamily: "'Space Mono', monospace",
  },
  topicStats: {
    display: 'flex',
    gap: '24px',
  },
  topicStat: {
    display: 'flex',
    flexDirection: 'column',
  },
  statValue: {
    fontSize: '20px',
    fontWeight: 600,
    color: '#fafafa',
    fontFamily: "'Space Mono', monospace",
  },
  statLabel: {
    fontSize: '12px',
    color: '#71717a',
  },
  topicMarkets: {
    marginTop: '16px',
    paddingTop: '16px',
    borderTop: '1px solid #27272a',
  },
  miniMarket: {
    padding: '10px 0',
    borderBottom: '1px solid #27272a',
  },
  miniTitle: {
    fontSize: '14px',
    color: '#e4e4e7',
    display: 'block',
    marginBottom: '4px',
  },
  miniStats: {
    display: 'flex',
    gap: '16px',
    fontSize: '14px',
    fontFamily: "'Space Mono', monospace",
  },
  miniVolume: {
    color: '#71717a',
  },
  footer: {
    textAlign: 'center',
    padding: '24px 40px',
    borderTop: '1px solid #18181b',
    color: '#52525b',
    fontSize: '13px',
  },
};

// Add keyframes for animation
const styleSheet = document.createElement('style');
styleSheet.textContent = `
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
  
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  
  button:hover {
    opacity: 0.85;
  }
  
  a:hover {
    background: rgba(34, 211, 238, 0.15) !important;
  }
`;
document.head.appendChild(styleSheet);

export default App;

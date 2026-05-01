import { useEffect, useState } from 'react';
import { api } from '../api/client';

const MARKETS = [
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_stock', label: '港股' },
  { key: 'us_stock', label: '美股' },
];

function sentimentBadge(score: number | null) {
  if (score == null) return null;
  if (score > 0.15) return <span className="badge buy">积极</span>;
  if (score < -0.15) return <span className="badge sell">消极</span>;
  return <span className="badge hold">中性</span>;
}

export default function NewsFeed() {
  const [market, setMarket] = useState('a_stock');
  const [news, setNews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getNews(market, 40)
      .then((data) => setNews(data || []))
      .catch(() => setNews([]))
      .finally(() => setLoading(false));
  }, [market]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>新闻舆情</h1>
        <p>最新财经资讯 · 情绪分析 · 市场风向</p>
      </header>

      <div className="market-tabs" style={{ marginBottom: 'var(--space-6)' }}>
        {MARKETS.map((m) => (
          <button
            key={m.key}
            className={`market-tab ${market === m.key ? 'active' : ''}`}
            onClick={() => setMarket(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : news.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">⊠</div>
          <p>暂无新闻数据</p>
          <div className="empty-hint">数据源可能暂不可用，请稍后重试</div>
        </div>
      ) : (
        <div className="news-list">
          {news.map((item, i) => (
            <a
              key={i}
              href={item.url || '#'}
              target={item.url ? '_blank' : undefined}
              rel="noopener noreferrer"
              className="news-item"
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 'var(--space-4)',
                padding: 'var(--space-4) var(--space-5)',
                borderBottom: '1px solid var(--border)',
                textDecoration: 'none',
                color: 'inherit',
                transition: 'background var(--duration-fast) var(--ease-out)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 'var(--font-size-md)',
                  fontWeight: 500,
                  marginBottom: 'var(--space-1)',
                  lineHeight: 1.4,
                }}>
                  {item.title}
                </div>
                <div style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--text-muted)',
                  display: 'flex',
                  gap: 'var(--space-4)',
                }}>
                  <span>{item.source}</span>
                  {item.published_at && (
                    <span>{new Date(item.published_at).toLocaleDateString('zh-CN')}</span>
                  )}
                </div>
              </div>
              <div style={{ flexShrink: 0 }}>
                {sentimentBadge(item.sentiment)}
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

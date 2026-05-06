import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import ResearchWorkflow from '../components/ResearchWorkflow';

const MARKETS = [
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_stock', label: '港股' },
  { key: 'us_stock', label: '美股' },
];

const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'positive', label: '积极' },
  { key: 'neutral', label: '中性' },
  { key: 'negative', label: '消极' },
];

export default function NewsFeed() {
  const [market, setMarket] = useState('a_stock');
  const [filter, setFilter] = useState('all');
  const [news, setNews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getNews(market, 60)
      .then((data) => setNews(data || []))
      .catch(() => setNews([]))
      .finally(() => setLoading(false));
  }, [market]);

  const stats = useMemo(() => {
    const positive = news.filter((item) => item.sentiment > 0.15).length;
    const negative = news.filter((item) => item.sentiment < -0.15).length;
    const neutral = news.length - positive - negative;
    const avg = news.length ? news.reduce((sum, item) => sum + (item.sentiment || 0), 0) / news.length : 0;
    return { positive, negative, neutral, avg };
  }, [news]);

  const filteredNews = news.filter((item) => {
    if (filter === 'positive') return item.sentiment > 0.15;
    if (filter === 'negative') return item.sentiment < -0.15;
    if (filter === 'neutral') return item.sentiment <= 0.15 && item.sentiment >= -0.15;
    return true;
  });

  return (
    <div className="page">
      <header className="page-header">
        <h1>新闻资讯</h1>
        <p>最新财经资讯 · 情绪温度 · 风险事件识别</p>
      </header>

      <ResearchWorkflow active="news" />

      <div className="market-tabs" style={{ marginBottom: 'var(--space-6)' }}>
        {MARKETS.map((m) => (
          <button key={m.key} className={`market-tab ${market === m.key ? 'active' : ''}`} onClick={() => setMarket(m.key)}>
            {m.label}
          </button>
        ))}
      </div>

      <section className="news-dashboard">
        <div className="news-sentiment-card">
          <div className="metric-label">市场情绪均值</div>
          <strong className={stats.avg >= 0 ? 'gain' : 'loss'}>{stats.avg.toFixed(2)}</strong>
          <p>{sentimentText(stats.avg)}</p>
        </div>
        <div className="news-stat-card positive">
          <span>积极新闻</span>
          <strong>{stats.positive}</strong>
        </div>
        <div className="news-stat-card neutral">
          <span>中性新闻</span>
          <strong>{stats.neutral}</strong>
        </div>
        <div className="news-stat-card negative">
          <span>消极新闻</span>
          <strong>{stats.negative}</strong>
        </div>
      </section>

      <div className="market-tabs compact-tabs">
        {FILTERS.map((item) => (
          <button key={item.key} className={`market-tab ${filter === item.key ? 'active' : ''}`} onClick={() => setFilter(item.key)}>
            {item.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : filteredNews.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">⊠</div>
          <p>暂无新闻数据</p>
          <div className="empty-hint">数据源可能暂不可用，请稍后重试</div>
        </div>
      ) : (
        <div className="news-board">
          {filteredNews.map((item, i) => (
            <div key={`${item.title}-${i}`} className="news-card">
              <div className="news-card-main">
                <div className="news-card-title">{item.title}</div>
                <div className="news-card-meta">
                  <span>{item.source || '财经媒体'}</span>
                  {item.quality_score != null && <span>质量 {Number(item.quality_score || 0).toFixed(0)}</span>}
                  {item.url && (
                    <a href={item.url} target="_blank" rel="noopener noreferrer">原文</a>
                  )}
                  {item.standardized?.symbol && (
                    <Link
                      to={`/analysis?symbol=${encodeURIComponent(item.standardized.symbol)}&market=${item.standardized.market || market}`}
                    >
                      深度分析
                    </Link>
                  )}
                  {item.published_at && <span>{formatDate(item.published_at)}</span>}
                </div>
              </div>
              <div className="news-card-side">
                {sentimentBadge(item.sentiment)}
                <span className="sentiment-score">{item.sentiment != null ? item.sentiment.toFixed(2) : '-'}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function sentimentBadge(score: number | null) {
  if (score == null) return <span className="badge hold">未知</span>;
  if (score > 0.15) return <span className="badge buy">积极</span>;
  if (score < -0.15) return <span className="badge sell">消极</span>;
  return <span className="badge hold">中性</span>;
}

function sentimentText(score: number) {
  if (score > 0.18) return '资讯环境偏正面，可提高候选股情绪权重';
  if (score < -0.18) return '资讯环境偏负面，自动交易应降低仓位';
  return '资讯环境中性，重点看公司质量和行情确认';
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

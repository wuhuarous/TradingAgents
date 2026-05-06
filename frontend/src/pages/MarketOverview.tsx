import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import ResearchWorkflow from '../components/ResearchWorkflow';

const MARKETS = [
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_stock', label: '港股' },
  { key: 'us_stock', label: '美股' },
];

const CURRENCY: Record<string, string> = {
  a_stock: '¥',
  hk_stock: 'HK$',
  us_stock: '$',
};

function fmtPct(value: number | null | undefined) {
  if (value == null || Number.isNaN(Number(value))) return '--';
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
}

function fmtPrice(value: number | null | undefined, market: string) {
  if (value == null || Number.isNaN(Number(value))) return '--';
  return `${CURRENCY[market] || ''}${Number(value).toFixed(2)}`;
}

export default function MarketOverview() {
  const [market, setMarket] = useState('a_stock');
  const [data, setData] = useState<any>(null);
  const [rankings, setRankings] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setData(null);
    api.getSimulationRankings(10).then(setRankings).catch(() => {});

    const apiBase = import.meta.env.VITE_API_BASE || '/api';
    const wsBase = apiBase.startsWith('http')
      ? apiBase.replace(/^http/, 'ws').replace(/\/api\/?$/, '')
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8000`;
    const wsUrl = `${wsBase}/api/market/ws/${market}`;
    const ws = new WebSocket(wsUrl);
    let settled = false;

    ws.onmessage = (event) => {
      setData(JSON.parse(event.data));
      setLoading(false);
      settled = true;
    };
    ws.onerror = () => {
      if (!settled) {
        api.getMarketOverview(market)
          .then(setData)
          .catch(() => {})
          .finally(() => setLoading(false));
      }
    };

    const timer = window.setTimeout(() => {
      if (!settled) {
        api.getMarketOverview(market)
          .then(setData)
          .catch(() => {})
          .finally(() => setLoading(false));
      }
    }, 3500);

    return () => {
      window.clearTimeout(timer);
      ws.close();
    };
  }, [market]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>行情总览</h1>
        <p>实时指数 · 热门标的 · 涨跌排名</p>
      </header>

      <ResearchWorkflow active="market" />

      <div className="market-tabs">
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
      ) : !data ? (
        <div className="empty-state">
          <div className="empty-icon">⊟</div>
          <p>行情数据加载失败</p>
          <div className="empty-hint">请检查网络连接后重试</div>
        </div>
      ) : (
        <>
          <section className="market-pulse-grid">
            {MARKETS.map((m) => {
              const summary = rankings?.markets?.find((item: any) => item.market === m.key);
              const avg = summary?.avg_score || 0;
              const leaders = summary?.buy_signals || 0;
              return (
                <button
                  className={`market-pulse-card ${market === m.key ? 'active' : ''}`}
                  key={m.key}
                  onClick={() => setMarket(m.key)}
                >
                  <span>{m.label}</span>
                  <strong className={avg >= 0 ? 'gain' : 'loss'}>
                    {avg ? avg.toFixed(1) : '--'}
                  </strong>
                  <p>{leaders} 个模拟买入信号</p>
                </button>
              );
            })}
          </section>

          {/* Indices */}
          {data.indices && data.indices.length > 0 && (
            <div className="indices-row" style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${Math.min(data.indices.length, 4)}, 1fr)`,
              gap: 'var(--space-4)',
              marginBottom: 'var(--space-8)',
            }}>
              {data.indices.map((idx: any) => (
                <div className="metric-card" key={idx.symbol}>
                  <div className="metric-label">{idx.name}</div>
                  <div className="metric-value" style={{ fontSize: 'var(--font-size-xl)' }}>
                    {idx.price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </div>
                  <div className={`metric-sub ${idx.change_pct >= 0 ? 'gain' : 'loss'}`}>
                    {idx.change_pct >= 0 ? '↑' : '↓'} {fmtPct(idx.change_pct)}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-6)' }}>
            {/* Top Gainers */}
            <section>
              <div className="section-header">
                <h2>涨幅榜</h2>
                <span className="section-badge">Top 5</span>
              </div>
              {data.top_gainers?.length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr><th>代码</th><th>名称</th><th>价格</th><th>涨幅</th></tr>
                  </thead>
                  <tbody>
                    {data.top_gainers.map((s: any) => (
                      <tr key={s.symbol}>
                        <td className="mono" style={{ fontWeight: 600 }}>
                          <Link to={`/stock?symbol=${s.symbol}&market=${market}`} style={{ color: 'var(--amber)', textDecoration: 'none' }}>
                            {s.symbol}
                          </Link>
                        </td>
                        <td>{s.name}</td>
                        <td className="mono">{fmtPrice(s.price, market)}</td>
                        <td className="gain">{fmtPct(s.change_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
                  <p>暂无数据</p>
                </div>
              )}
            </section>

            {/* Top Losers */}
            <section>
              <div className="section-header">
                <h2>跌幅榜</h2>
                <span className="section-badge">Top 5</span>
              </div>
              {data.top_losers?.length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr><th>代码</th><th>名称</th><th>价格</th><th>跌幅</th></tr>
                  </thead>
                  <tbody>
                    {data.top_losers.map((s: any) => (
                      <tr key={s.symbol}>
                        <td className="mono" style={{ fontWeight: 600 }}>
                          <Link to={`/stock?symbol=${s.symbol}&market=${market}`} style={{ color: 'var(--amber)', textDecoration: 'none' }}>
                            {s.symbol}
                          </Link>
                        </td>
                        <td>{s.name}</td>
                        <td className="mono">{fmtPrice(s.price, market)}</td>
                        <td className="loss">{fmtPct(s.change_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
                  <p>暂无数据</p>
                </div>
              )}
            </section>
          </div>

          {rankings && (
            <section className="section" style={{ marginTop: 'var(--space-8)' }}>
              <div className="section-header">
                <h2>全市场强势候选</h2>
                <span className="section-badge">质量 + 潜力</span>
              </div>
              <div className="market-leader-grid">
                {(rankings.all || []).slice(0, 12).map((item: any) => (
                  <Link
                    className="leader-card"
                    key={`${item.market}-${item.symbol}`}
                    to={`/analysis?symbol=${encodeURIComponent(item.symbol)}&market=${item.market}`}
                  >
                    <div>
                      <strong>{item.symbol}</strong>
                      <p>{item.name}</p>
                    </div>
                    <span className={`action-pill ${String(item.action).toLowerCase()}`}>
                      {item.action === 'BUY' ? '买入' : item.action === 'WATCH' ? '观察' : item.action}
                    </span>
                    <b>{item.final_score}</b>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* All Hot Stocks */}
          <section className="section" style={{ marginTop: 'var(--space-8)' }}>
            <div className="section-header">
              <h2>热门标的</h2>
              <span className="section-badge">{data.hot_stocks?.length || 0} 个</span>
            </div>
            {data.hot_stocks?.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr><th>代码</th><th>名称</th><th>价格</th><th>涨跌幅</th><th>成交量</th></tr>
                </thead>
                <tbody>
                  {data.hot_stocks.map((s: any) => (
                    <tr key={s.symbol}>
                      <td className="mono" style={{ fontWeight: 600 }}>
                        <Link to={`/stock?symbol=${s.symbol}&market=${market}`} style={{ color: 'var(--amber)', textDecoration: 'none' }}>
                          {s.symbol}
                        </Link>
                      </td>
                      <td>{s.name}</td>
                      <td className="mono">{fmtPrice(s.price, market)}</td>
                      <td className={`mono ${s.change_pct >= 0 ? 'gain' : 'loss'}`}>
                        {fmtPct(s.change_pct)}
                      </td>
                      <td className="mono">{s.volume?.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
                <p>暂无热门数据</p>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

import { useEffect, useState } from 'react';
import { api } from '../api/client';

const MARKETS = [
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_stock', label: '港股' },
  { key: 'us_stock', label: '美股' },
];

export default function MarketOverview() {
  const [market, setMarket] = useState('a_stock');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setData(null);
    api.getMarketOverview(market)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [market]);

  return (
    <div className="page">
      <header className="page-header">
        <h1>行情总览</h1>
        <p>实时指数 · 热门标的 · 涨跌排名</p>
      </header>

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
                    {idx.change_pct >= 0 ? '↑' : '↓'} {idx.change_pct?.toFixed(2)}%
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
                        <td className="mono" style={{ fontWeight: 600 }}>{s.symbol}</td>
                        <td>{s.name}</td>
                        <td className="mono">¥{s.price?.toFixed(2)}</td>
                        <td className="gain">{s.change_pct?.toFixed(2)}%</td>
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
                        <td className="mono" style={{ fontWeight: 600 }}>{s.symbol}</td>
                        <td>{s.name}</td>
                        <td className="mono">¥{s.price?.toFixed(2)}</td>
                        <td className="loss">{s.change_pct?.toFixed(2)}%</td>
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
                      <td className="mono" style={{ fontWeight: 600 }}>{s.symbol}</td>
                      <td>{s.name}</td>
                      <td className="mono">¥{s.price?.toFixed(2)}</td>
                      <td className={`mono ${s.change_pct >= 0 ? 'gain' : 'loss'}`}>
                        {s.change_pct >= 0 ? '+' : ''}{s.change_pct?.toFixed(2)}%
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

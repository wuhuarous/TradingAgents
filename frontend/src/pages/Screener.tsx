import { useState } from 'react';
import { api } from '../api/client';

const MARKETS = [
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_stock', label: '港股' },
  { key: 'us_stock', label: '美股' },
];

const SORT_OPTIONS = [
  { key: 'roe', label: 'ROE' },
  { key: 'pe', label: 'PE（低优先）' },
  { key: 'pb', label: 'PB（低优先）' },
  { key: 'revenue_growth', label: '营收增长' },
];

export default function Screener() {
  const [market, setMarket] = useState('a_stock');
  const [filters, setFilters] = useState({
    min_roe: '',
    max_pe: '',
    max_pb: '',
    min_revenue_growth: '',
    sort_by: 'roe',
    limit: 20,
  });
  const [results, setResults] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const runScreen = async () => {
    setLoading(true);
    const params: Record<string, any> = { market, limit: filters.limit, sort_by: filters.sort_by };
    if (filters.min_roe) params.min_roe = parseFloat(filters.min_roe) / 100;
    if (filters.max_pe) params.max_pe = parseFloat(filters.max_pe);
    if (filters.max_pb) params.max_pb = parseFloat(filters.max_pb);
    if (filters.min_revenue_growth) params.min_revenue_growth = parseFloat(filters.min_revenue_growth) / 100;
    try {
      const data = await api.screenStocks(params);
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>智能选股</h1>
        <p>多维度财务指标筛选 · 发现优质标的</p>
      </header>

      {/* Market tabs */}
      <div className="market-tabs" style={{ marginBottom: 'var(--space-6)' }}>
        {MARKETS.map((m) => (
          <button
            key={m.key}
            className={`market-tab ${market === m.key ? 'active' : ''}`}
            onClick={() => { setMarket(m.key); setResults(null); }}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Filter panel */}
      <div className="filter-panel" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
        gap: 'var(--space-4)',
        marginBottom: 'var(--space-6)',
      }}>
        <div className="filter-group">
          <label className="filter-label">最低 ROE (%)</label>
          <input
            type="number"
            className="filter-input"
            placeholder="例如 15"
            value={filters.min_roe}
            onChange={(e) => handleFilter('min_roe', e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label">最高 PE</label>
          <input
            type="number"
            className="filter-input"
            placeholder="例如 30"
            value={filters.max_pe}
            onChange={(e) => handleFilter('max_pe', e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label">最高 PB</label>
          <input
            type="number"
            className="filter-input"
            placeholder="例如 5"
            value={filters.max_pb}
            onChange={(e) => handleFilter('max_pb', e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label">最低营收增长 (%)</label>
          <input
            type="number"
            className="filter-input"
            placeholder="例如 10"
            value={filters.min_revenue_growth}
            onChange={(e) => handleFilter('min_revenue_growth', e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label">排序依据</label>
          <select
            className="filter-input"
            value={filters.sort_by}
            onChange={(e) => handleFilter('sort_by', e.target.value)}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.key} value={o.key}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <button
        className="btn-primary"
        onClick={runScreen}
        disabled={loading}
        style={{
          padding: 'var(--space-3) var(--space-8)',
          marginBottom: 'var(--space-8)',
        }}
      >
        {loading ? '筛选中...' : '开始筛选'}
      </button>

      {/* Results */}
      {loading ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : results === null ? (
        <div className="empty-state">
          <div className="empty-icon">⊞</div>
          <p>设置筛选条件后点击"开始筛选"</p>
          <div className="empty-hint">留空条件将不限制该项指标</div>
        </div>
      ) : results.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">∅</div>
          <p>没有符合条件的股票</p>
          <div className="empty-hint">尝试放宽筛选条件</div>
        </div>
      ) : (
        <div className="stock-grid">
          {results.map((s: any) => (
            <div className="stock-card" key={s.symbol}>
              <div className="stock-head">
                <div>
                  <div className="stock-symbol">{s.symbol}</div>
                  <div className="stock-name">{s.name}</div>
                </div>
              </div>
              <div className="stock-metrics">
                <div>
                  <div className="stock-metric-label">PE</div>
                  <div className="stock-metric-value">
                    {s.pe != null ? s.pe.toFixed(1) : '—'}
                  </div>
                </div>
                <div>
                  <div className="stock-metric-label">PB</div>
                  <div className="stock-metric-value">
                    {s.pb != null ? s.pb.toFixed(1) : '—'}
                  </div>
                </div>
                <div>
                  <div className="stock-metric-label">ROE</div>
                  <div className="stock-metric-value" style={{
                    color: (s.roe || 0) >= 15 ? 'var(--gain)' : 'var(--text-primary)',
                  }}>
                    {s.roe != null ? `${s.roe}%` : '—'}
                  </div>
                </div>
                <div>
                  <div className="stock-metric-label">营收增长</div>
                  <div className="stock-metric-value">
                    {s.revenue_growth != null ? `${s.revenue_growth}%` : '—'}
                  </div>
                </div>
              </div>
              {(s.roe || 0) >= 15 && (
                <div className="stock-confidence">
                  <span>优质标的</span>
                  <div className="conf-bar">
                    <div className="conf-fill" style={{ width: '100%' }} />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

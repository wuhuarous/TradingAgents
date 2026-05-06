import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import ResearchWorkflow from '../components/ResearchWorkflow';

const MARKETS = [
  { key: 'all', label: '全市场' },
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
  const [market, setMarket] = useState('all');
  const [rankings, setRankings] = useState<any>(null);
  const [results, setResults] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    min_roe: '',
    max_pe: '',
    max_pb: '',
    min_revenue_growth: '',
    sort_by: 'roe',
    limit: 20,
  });

  useEffect(() => {
    setLoading(true);
    setResults(null);
    if (market === 'all') {
      api.getSimulationRankings(10)
        .then(setRankings)
        .catch(() => setRankings(null))
        .finally(() => setLoading(false));
      return;
    }
    api.getSimulationCandidates(market, 12)
      .then((data) => setRankings({ all: data.candidates || [] }))
      .catch(() => setRankings({ all: [] }))
      .finally(() => setLoading(false));
  }, [market]);

  const handleFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const runScreen = async () => {
    const targetMarket = market === 'all' ? 'a_stock' : market;
    setLoading(true);
    const params: Record<string, any> = { market: targetMarket, limit: filters.limit, sort_by: filters.sort_by };
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

  const quality = rankings?.quality_top10 || rankings?.all || [];
  const potential = rankings?.potential_top10 || rankings?.all || [];

  return (
    <div className="page">
      <header className="page-header">
        <h1>智能选股</h1>
        <p>全市场 Top10 优质股与潜力股 · 营收成长 · 新闻情绪 · 行情趋势</p>
      </header>

      <ResearchWorkflow active="screener" />

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

      <section className="screener-hero">
        <div>
          <div className="agent-label">默认策略</div>
          <h2>先选好公司，再找高胜率买点</h2>
          <p>优质股偏重 ROE、营收增长、估值和低风险；潜力股偏重趋势突破、成长、情绪和流动性。两张榜单都来自同一套模拟训练评分，方便后续复盘。</p>
        </div>
        <div className="hero-link-row">
          <Link className="panel-link-btn" to="/analysis">深度分析</Link>
          <Link className="panel-link-btn secondary" to="/backtest">验证策略</Link>
          <Link className="panel-link-btn secondary" to="/simulation">模拟训练</Link>
        </div>
      </section>

      {loading ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : (
        <>
          <div className="screener-rank-grid">
            <PickBoard title="优质股 Top 10" items={quality.slice(0, 10)} />
            <PickBoard title="潜力股 Top 10" items={potential.slice(0, 10)} />
          </div>

          <section className="section" style={{ marginTop: 'var(--space-8)' }}>
            <div className="section-header">
              <h2>条件筛选</h2>
              <span className="section-badge">{market === 'all' ? '默认 A股条件池' : marketLabel(market)}</span>
            </div>
            <div className="filter-panel" style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 'var(--space-4)',
              marginBottom: 'var(--space-5)',
            }}>
              <FilterInput label="最低 ROE (%)" value={filters.min_roe} onChange={(v) => handleFilter('min_roe', v)} placeholder="例如 15" />
              <FilterInput label="最高 PE" value={filters.max_pe} onChange={(v) => handleFilter('max_pe', v)} placeholder="例如 30" />
              <FilterInput label="最高 PB" value={filters.max_pb} onChange={(v) => handleFilter('max_pb', v)} placeholder="例如 5" />
              <FilterInput label="最低营收增长 (%)" value={filters.min_revenue_growth} onChange={(v) => handleFilter('min_revenue_growth', v)} placeholder="例如 10" />
              <div className="filter-group">
                <label className="filter-label">排序依据</label>
                <select className="filter-input" value={filters.sort_by} onChange={(e) => handleFilter('sort_by', e.target.value)}>
                  {SORT_OPTIONS.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
                </select>
              </div>
            </div>

            <button className="btn-primary" onClick={runScreen} disabled={loading} style={{ padding: 'var(--space-3) var(--space-8)', marginBottom: 'var(--space-6)' }}>
              {loading ? '筛选中...' : '运行条件筛选'}
            </button>

            {results && (
              results.length === 0 ? (
                <div className="empty-state">
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
                        <Metric label="PE" value={s.pe != null ? s.pe.toFixed(1) : '-'} />
                        <Metric label="PB" value={s.pb != null ? s.pb.toFixed(1) : '-'} />
                        <Metric label="ROE" value={s.roe != null ? `${s.roe}%` : '-'} />
                        <Metric label="营收增长" value={s.revenue_growth != null ? `${s.revenue_growth}%` : '-'} />
                      </div>
                    </div>
                  ))}
                </div>
              )
            )}
          </section>
        </>
      )}
    </div>
  );
}

function PickBoard({ title, items }: { title: string; items: any[] }) {
  return (
    <section className="rank-panel">
      <div className="section-header">
        <h2>{title}</h2>
        <span className="section-badge">Top {items.length}</span>
      </div>
      <div className="pick-board">
        {items.map((item, index) => (
          <Link className="pick-row" key={`${item.market}-${item.symbol}-${index}`} to={`/analysis?symbol=${encodeURIComponent(item.symbol)}&market=${item.market}`}>
            <span className="rank-index">{index + 1}</span>
            <div className="pick-main">
              <strong>{item.symbol}</strong>
              <p>{item.name} · {marketLabel(item.market)}</p>
            </div>
            <div className="pick-scores">
              <b>{item.board_score ?? item.final_score}</b>
              <span>{item.action === 'BUY' ? '买入' : item.action === 'WATCH' ? '观察' : item.action}</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

function FilterInput({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (value: string) => void; placeholder: string;
}) {
  return (
    <div className="filter-group">
      <label className="filter-label">{label}</label>
      <input type="number" className="filter-input" placeholder={placeholder} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="stock-metric-label">{label}</div>
      <div className="stock-metric-value">{value}</div>
    </div>
  );
}

function marketLabel(market: string) {
  return market === 'a_stock' ? 'A股' : market === 'hk_stock' ? '港股' : market === 'us_stock' ? '美股' : market;
}

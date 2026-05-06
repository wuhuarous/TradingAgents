import { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ComposedChart, Area
} from 'recharts';

const PERIODS = [
  { key: '5d', label: '5日' },
  { key: '1mo', label: '1月' },
  { key: '3mo', label: '3月' },
  { key: '6mo', label: '6月' },
  { key: '1y', label: '1年' },
];

const MKT_LABELS: Record<string, string> = {
  a_stock: 'A股', hk_stock: '港股', us_stock: '美股',
};

export default function StockDetail() {
  const [searchParams] = useSearchParams();
  const symbol = searchParams.get('symbol') || '';
  const market = searchParams.get('market') || 'a_stock';
  const [period, setPeriod] = useState('3mo');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError('');
    api.getStockDetail(symbol, market, period)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [symbol, market, period]);

  const fmt = (n: number, d = 2) =>
    n != null ? Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';
  const fmtPct = (n: number) =>
    n != null ? `${(n >= 0 ? '+' : '')}${(n * 100).toFixed(2)}%` : '—';
  const isGain = data?.change_pct >= 0;

  if (!symbol) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>个股详情</h1>
          <p>从行情总览点击股票查看详情</p>
        </header>
        <div className="empty-state">
          <div className="empty-icon">📈</div>
          <p>未选择股票</p>
          <p className="empty-hint">
            <Link to="/market" style={{ color: 'var(--amber)' }}>前往行情总览</Link> 选择股票
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header" style={{ marginBottom: 'var(--space-6)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-4)', flexWrap: 'wrap' }}>
          <h1>{data?.name || symbol}</h1>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-md)',
            color: 'var(--text-muted)', background: 'var(--bg-card)',
            padding: '2px 8px', borderRadius: 'var(--radius)',
            border: '1px solid var(--border)',
          }}>
            {symbol} · {MKT_LABELS[market] || market}
          </span>
        </div>
      </header>

      {loading ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : error ? (
        <div className="empty-state">
          <div className="empty-icon">⚠</div>
          <p>{error}</p>
          <p className="empty-hint">请检查股票代码或稍后重试</p>
        </div>
      ) : data ? (
        <>
          {/* Price Card */}
          <div className="metrics-row" style={{ marginBottom: 'var(--space-8)' }}>
            <div className="metric-card primary">
              <div className="metric-label">最新价</div>
              <div className="metric-value" style={{ fontSize: 'var(--font-size-2xl)' }}>
                {fmt(data.price)}
              </div>
              <div className={`metric-sub ${isGain ? 'gain' : 'loss'}`} style={{ fontSize: 'var(--font-size-md)' }}>
                {fmtPct(data.change_pct)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">开盘</div>
              <div className="metric-value" style={{ fontSize: 'var(--font-size-xl)' }}>{fmt(data.open)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">最高 / 最低</div>
              <div className="metric-value" style={{ fontSize: 'var(--font-size-xl)' }}>
                <span style={{ color: 'var(--gain)' }}>{fmt(data.high)}</span>
                {' / '}
                <span style={{ color: 'var(--loss)' }}>{fmt(data.low)}</span>
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">成交量</div>
              <div className="metric-value" style={{ fontSize: 'var(--font-size-xl)' }}>
                {(data.volume / 10000).toFixed(0)}万
              </div>
            </div>
          </div>

          {/* K-Line Chart */}
          <section className="section">
            <div className="section-header">
              <h2>K线走势</h2>
              <div className="market-tabs" style={{ marginBottom: 0 }}>
                {PERIODS.map((p) => (
                  <button
                    key={p.key}
                    className={`market-tab ${period === p.key ? 'active' : ''}`}
                    onClick={() => setPeriod(p.key)}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="chart-container">
              {data.kline?.length > 0 ? (
                <KlineChart data={data.kline} />
              ) : (
                <div className="chart-empty">
                  <span className="chart-empty-icon">📊</span>
                  <span>暂无K线数据</span>
                </div>
              )}
            </div>
          </section>

          {/* Fundamentals */}
          <section className="section">
            <div className="section-header">
              <h2>基本面</h2>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 'var(--space-4)' }}>
              {renderFundamentals(data.fundamentals)}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function KlineChart({ data }: { data: any[] }) {
  // Split into price chart and volume chart
  return (
    <div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--amber)" stopOpacity={0.3} />
              <stop offset="100%" stopColor="var(--amber)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
            tickLine={false}
            axisLine={false}
            domain={['auto', 'auto']}
            tickFormatter={(v: number) => v.toFixed(2)}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--font-size-sm)',
              color: 'var(--text-primary)',
            }}
            labelStyle={{ color: 'var(--text-secondary)', marginBottom: 4 }}
          />
          <Area type="monotone" dataKey="close" stroke="var(--amber)" fill="url(#priceGrad)" strokeWidth={1.5} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Volume bars */}
      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="4 4" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => v > 10000 ? `${(v / 10000).toFixed(0)}万` : String(v)}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--font-size-sm)',
              color: 'var(--text-primary)',
            }}
          />
          <Bar dataKey="volume" fill="var(--blue-dim)" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function renderFundamentals(f: any) {
  if (!f) return <div className="metric-card"><div className="metric-label">暂无数据</div></div>;

  const items = [
    { label: '市盈率 PE', value: f.pe_ratio ?? f.pe, fmt: (v: any) => v != null ? Number(v).toFixed(2) : '—' },
    { label: '市净率 PB', value: f.pb_ratio ?? f.pb, fmt: (v: any) => v != null ? Number(v).toFixed(2) : '—' },
    { label: 'ROE', value: f.roe, fmt: (v: any) => v != null ? `${(v * 100).toFixed(2)}%` : '—' },
    { label: '总市值', value: f.market_cap, fmt: (v: any) => v != null ? `${(v / 1e8).toFixed(2)}亿` : '—' },
    { label: '营收', value: f.revenue, fmt: (v: any) => v != null ? `${(v / 1e8).toFixed(2)}亿` : '—' },
    { label: '净利润', value: f.net_income, fmt: (v: any) => v != null ? `${(v / 1e8).toFixed(2)}亿` : '—' },
    { label: '股息率', value: f.dividend_yield, fmt: (v: any) => v != null ? `${(Number(v) * 100).toFixed(2)}%` : '—' },
    { label: '负债权益比', value: f.debt_to_equity, fmt: (v: any) => v != null ? Number(v).toFixed(2) : '—' },
  ];

  return items.filter((i) => i.value != null).map((item) => (
    <div key={item.label} className="metric-card">
      <div className="metric-label">{item.label}</div>
      <div className="metric-value" style={{ fontSize: 'var(--font-size-lg)', fontFamily: 'var(--font-mono)' }}>
        {item.fmt(item.value)}
      </div>
    </div>
  ));
}

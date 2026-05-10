import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import PnLChart from '../components/PnLChart';

type DailyPoint = {
  date: string;
  daily_pnl: number;
  daily_pnl_pct: number;
  total_pnl: number;
  total_value: number;
  total_pnl_pct: number;
  positions_count: number;
};

type MonthlyPoint = {
  month: string;
  pnl: number;
  return_pct: number;
  trading_days: number;
  positive_days: number;
  negative_days: number;
  win_day_rate: number;
  start_value: number;
  end_value: number;
  max_daily_pnl: number;
  min_daily_pnl: number;
};

export default function Reports() {
  const [days, setDays] = useState(180);
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    api.getPortfolioReport(days)
      .then(setReport)
      .catch((err) => setError(readError(err)))
      .finally(() => setLoading(false));
  }, [days]);

  const daily: DailyPoint[] = report?.daily || [];
  const monthly: MonthlyPoint[] = report?.monthly || [];
  const summary = report?.summary || {};
  const dailyChart = useMemo(() => daily.map((item) => ({
    time: formatDay(item.date),
    value: Number(item.daily_pnl || 0),
    total_pnl: Number(item.total_pnl || 0),
    total_value: Number(item.total_value || 0),
  })), [daily]);

  return (
    <div className="reports-page">
      <header className="page-header report-header">
        <div>
          <h1>收益报表</h1>
          <p>按日和按月查看模拟账户收益，便于复盘交易节奏。</p>
        </div>
        <select className="filter-input report-range" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={30}>近30天</option>
          <option value={90}>近90天</option>
          <option value={180}>近180天</option>
          <option value={365}>近1年</option>
        </select>
      </header>

      {error && <div className="alert-error">{error}</div>}

      {loading ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : (
        <>
          <div className="metrics-row report-metrics">
            <Metric title="区间盈亏" value={formatMoney(summary.total_pnl)} tone={metricClass(summary.total_pnl)} sub={`${summary.days || 0} 个交易日`} />
            <Metric title="当前累计" value={formatMoney(summary.latest_total_pnl)} tone={metricClass(summary.latest_total_pnl)} sub={formatPct(summary.latest_total_pnl_pct)} />
            <Metric title="盈利天数" value={`${summary.positive_days || 0}`} tone="gain" sub={`胜日率 ${formatPct(summary.win_day_rate)}`} />
            <Metric title="亏损天数" value={`${summary.negative_days || 0}`} tone="loss" sub={`最新资产 ${formatMoney(summary.latest_total_value)}`} />
          </div>

          <section className="section">
            <div className="section-header">
              <h2>每日收益</h2>
              <span className="section-badge">{daily.length} 天</span>
            </div>
            <PnLChart data={dailyChart} />
          </section>

          <section className="section">
            <div className="section-header">
              <h2>月收益</h2>
              <span className="section-badge">{monthly.length} 月</span>
            </div>
            <MonthlyChart data={monthly} />
          </section>

          <section className="report-grid">
            <ReportTable title="每日明细" rows={daily.slice().reverse()} type="daily" />
            <ReportTable title="月度汇总" rows={monthly.slice().reverse()} type="monthly" />
          </section>
        </>
      )}
    </div>
  );
}

function Metric({ title, value, sub, tone }: { title: string; value: string; sub: string; tone?: string }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{title}</div>
      <div className={`metric-value ${tone || ''}`}>{value}</div>
      <div className="metric-sub">{sub}</div>
    </div>
  );
}

function MonthlyChart({ data }: { data: MonthlyPoint[] }) {
  if (!data.length) {
    return (
      <div className="chart-container">
        <div className="chart-empty"><span>暂无月收益数据</span></div>
      </div>
    );
  }
  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1c2332" vertical={false} />
          <XAxis dataKey="month" tick={{ fill: '#404a5e', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#1c2332' }} />
          <YAxis tick={{ fill: '#404a5e', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(v) => formatCompact(v)} />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number, name: string) => {
              if (name === 'pnl') return [formatMoney(v), '月盈亏'];
              return [v, name];
            }}
          />
          <Bar dataKey="pnl" radius={[4, 4, 0, 0]} maxBarSize={42}>
            {data.map((point) => (
              <Cell key={point.month} fill={point.pnl >= 0 ? '#d9454b' : '#2ea87a'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ReportTable({ title, rows, type }: { title: string; rows: any[]; type: 'daily' | 'monthly' }) {
  return (
    <section className="section report-table-card">
      <div className="section-header">
        <h2>{title}</h2>
        <span className="section-badge">{rows.length} 条</span>
      </div>
      <div className="backtest-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{type === 'daily' ? '日期' : '月份'}</th>
              <th>盈亏</th>
              <th>收益率</th>
              <th>{type === 'daily' ? '累计盈亏' : '盈利天数'}</th>
              <th>{type === 'daily' ? '总资产' : '亏损天数'}</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 80).map((row) => {
              const pnl = type === 'daily' ? row.daily_pnl : row.pnl;
              const pct = type === 'daily' ? row.daily_pnl_pct : row.return_pct;
              return (
                <tr key={type === 'daily' ? row.date : row.month}>
                  <td className="mono">{type === 'daily' ? row.date : row.month}</td>
                  <td className={`mono ${metricClass(pnl)}`}>{formatMoney(pnl)}</td>
                  <td className={`mono ${metricClass(pct)}`}>{formatPct(pct)}</td>
                  <td className="mono">{type === 'daily' ? formatMoney(row.total_pnl) : row.positive_days}</td>
                  <td className="mono">{type === 'daily' ? formatMoney(row.total_value) : row.negative_days}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const tooltipStyle = {
  background: '#111620',
  border: '1px solid #293040',
  borderRadius: 6,
  fontFamily: 'JetBrains Mono, monospace',
  fontSize: 12,
  color: '#e3e6ed',
  padding: '8px 12px',
};

function readError(err: any) {
  const message = err?.message || '请求失败';
  try {
    const parsed = JSON.parse(message);
    if (parsed?.detail) return String(parsed.detail);
  } catch {
    return message;
  }
  return message;
}

function formatMoney(value?: number) {
  return `¥${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function formatPct(value?: number) {
  const n = Number(value || 0) * 100;
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function formatCompact(value?: number) {
  const n = Number(value || 0);
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toFixed(0);
}

function metricClass(value?: number) {
  return Number(value || 0) >= 0 ? 'gain' : 'loss';
}

function formatDay(value?: string) {
  if (!value) return '-';
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return `${Number(m[2])}/${Number(m[3])}`;
  return value;
}

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import PositionTable from '../components/PositionTable';
import PnLChart from '../components/PnLChart';

interface Account {
  initial_capital: number;
  total_value: number;
  cash: number;
  total_pnl: number;
  total_pnl_pct: number;
  positions_value: number;
}

interface PnLPoint {
  time: string;
  value: number;
  total_pnl?: number;
  total_value?: number;
}

export default function Dashboard() {
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [pnlHistory, setPnlHistory] = useState<PnLPoint[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [readiness, setReadiness] = useState<any>(null);
  const [rankings, setRankings] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    const loadAccount = (forcePrices = false) => api.getAccountOverview(forcePrices).then((data) => {
      setAccount(data.account);
      setPositions(data.positions || []);
    }).catch(() => {});
    loadAccount(true);
    const accountTimer = window.setInterval(() => loadAccount(false), 15000);
    api.getSimulationSummary().then(setSummary).catch(() => {});
    api.getQuantReadiness().then(setReadiness).catch(() => {});
    api.getSimulationRankings(10).then(setRankings).catch(() => {});
    api.getSimulationRuns(5).then((data) => setRuns(data.runs || [])).catch(() => {});
    api.getDailyPnl(30).then((data) => {
      setPnlHistory((data.points || []).map((item: any) => ({
        time: formatDay(item.date),
        value: Number(item.daily_pnl || 0),
        total_pnl: Number(item.total_pnl || 0),
        total_value: Number(item.total_value || 0),
      })));
    }).catch(() => setPnlHistory([]));
    return () => window.clearInterval(accountTimer);
  }, []);

  const livePositionsValue = positions.reduce(
    (sum, item) => sum + Number(item.market_value ?? Number(item.quantity || 0) * Number(item.current_price || 0)),
    0,
  );
  const liveTotalValue = account ? Number(account.cash || 0) + livePositionsValue : 0;
  const liveTotalPnl = account ? liveTotalValue - Number(account.initial_capital || 0) : 0;
  const livePnlPct = account && account.initial_capital > 0 ? liveTotalPnl / account.initial_capital : 0;
  const pnlPct = livePnlPct * 100;
  const isGain = liveTotalPnl >= 0;
  const targetPct = (summary?.target_annual_return || 0.5) * 100;
  const targetProgress = Math.max(0, Math.min(100, targetPct ? (pnlPct / targetPct) * 100 : 0));

  return (
    <div className="dashboard">
      <header className="page-header">
        <h1>仪表盘</h1>
        <p>实时资产概览与风险监控</p>
      </header>

      {!account ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : (
        <>
          <div className="metrics-row">
            <div className="metric-card primary">
              <div className="metric-label">总资产</div>
              <div className="metric-value">
                ¥{formatMoney(liveTotalValue)}
              </div>
              <div className="metric-sub">
                可用现金 ¥{formatMoney(account.cash)}
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">持仓市值</div>
              <div className="metric-value" style={{ fontSize: 'var(--font-size-2xl)' }}>
                ¥{formatMoney(livePositionsValue)}
              </div>
              <div className="metric-sub">
                {positions.length} 个标的
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">累计盈亏</div>
              <div className="metric-value" style={{
                color: isGain ? 'var(--gain)' : 'var(--loss)',
                fontSize: 'var(--font-size-2xl)',
              }}>
                {isGain ? '+' : ''}¥{formatMoney(liveTotalPnl)}
              </div>
              <div className={`metric-sub ${isGain ? 'gain' : 'loss'}`}>
                {isGain ? '↑' : '↓'} {pnlPct.toFixed(2)}%
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">50% 年化进度</div>
              <div className="metric-value" style={{ fontSize: 'var(--font-size-2xl)' }}>
                {targetProgress.toFixed(1)}%
              </div>
              <div className="metric-sub">
                当前 {pnlPct.toFixed(2)}% / 目标 {targetPct.toFixed(0)}%
              </div>
            </div>
          </div>

          <section className="mission-panel">
            <div>
              <div className="agent-label">今日交易任务</div>
              <h2>先找优质和潜力，再让模拟盘验证</h2>
              <p>仪表板聚合全市场 Top10、模拟收益进度、持仓风险和最近训练记录。每一次自动买卖都会进入复盘日志，用后续收益校准权重。</p>
            </div>
            <Link className="panel-link-btn" to="/simulation">进入模拟训练</Link>
          </section>

          {readiness && (
            <section className="readiness-panel">
              <div className="readiness-head">
                <div>
                  <div className="agent-label">AI 量化准备度</div>
                  <h2>先把交易底座做稳，再追求 50% 年化</h2>
                  <p>这里把数据、策略验证、风控、执行、复盘和 AI 稳定性拆成可检查项。</p>
                </div>
                <div className={`readiness-score ${readiness.status}`}>
                  <strong>{readiness.overall_score}</strong>
                  <span>{statusLabel(readiness.status)}</span>
                </div>
              </div>
              <div className="readiness-grid">
                {(readiness.checks || []).map((item: any) => (
                  <div className={`readiness-item ${item.status}`} key={item.key}>
                    <div className="readiness-item-head">
                      <strong>{item.label}</strong>
                      <span>{item.score}</span>
                    </div>
                    <div className="readiness-bar">
                      <i style={{ width: `${item.score}%` }} />
                    </div>
                    <p>{item.description}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {rankings && (
            <section className="dashboard-grid">
              <TopPickPanel title="全市场优质股 Top 10" items={rankings.quality_top10 || []} />
              <TopPickPanel title="全市场潜力股 Top 10" items={rankings.potential_top10 || []} />
            </section>
          )}

          <section className="section">
            <div className="section-header">
              <h2>盈亏走势</h2>
              <Link className="section-badge link-badge" to="/reports">日报/月报</Link>
            </div>
            <PnLChart data={pnlHistory} />
          </section>

          <section className="section">
            <div className="section-header">
              <h2>当前持仓</h2>
              <span className="section-badge">{positions.length} 个</span>
            </div>
            <PositionTable positions={positions} />
          </section>

          <section className="section">
            <div className="section-header">
              <h2>最近训练复盘</h2>
              <span className="section-badge">{runs.length} 轮</span>
            </div>
            {runs.length === 0 ? (
              <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
                <p>还没有模拟训练记录</p>
                <div className="empty-hint">从模拟训练页运行一轮后，这里会显示买卖动作和收益进度</div>
              </div>
            ) : (
              <div className="run-list">
                {runs.map((run) => (
                  <div className="run-card" key={run.run_id}>
                    <div className="run-head">
                      <strong>{run.run_id}</strong>
                      <span>{marketLabel(run.market)}</span>
                    </div>
                    <div className="run-stats">
                      <span>订单 {run.orders?.length || 0}</span>
                      <span>决策 {run.decisions?.length || 0}</span>
                      <span>收益 {((run.review?.current_return || 0) * 100).toFixed(2)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function TopPickPanel({ title, items }: { title: string; items: any[] }) {
  return (
    <section className="rank-panel">
      <div className="section-header">
        <h2>{title}</h2>
        <span className="section-badge">Top {items.length}</span>
      </div>
      <div className="compact-rank-list">
        {items.slice(0, 10).map((item, index) => (
          <Link
            className="compact-rank-row"
            key={`${item.market}-${item.symbol}`}
            to={`/analysis?symbol=${encodeURIComponent(item.symbol)}&market=${item.market}`}
          >
            <span className="rank-index">{index + 1}</span>
            <div>
              <strong>{item.symbol}</strong>
              <p>{item.name} · {marketLabel(item.market)}</p>
            </div>
            <b>{item.final_score}</b>
          </Link>
        ))}
      </div>
    </section>
  );
}

function marketLabel(market: string) {
  return market === 'a_stock' ? 'A股' : market === 'hk_stock' ? '港股' : market === 'us_stock' ? '美股' : market;
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    ready: '可推进',
    partial: '需补强',
    blocked: '未就绪',
  };
  return map[status] || status;
}

function formatMoney(value?: number) {
  return Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDay(value?: string) {
  if (!value) return '-';
  const m = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return `${Number(m[2])}/${Number(m[3])}`;
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) return `${date.getMonth() + 1}/${date.getDate()}`;
  return value;
}

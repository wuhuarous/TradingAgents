import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import PositionTable from '../components/PositionTable';
import PnLChart from '../components/PnLChart';

interface Account {
  total_value: number;
  cash: number;
  total_pnl: number;
  total_pnl_pct: number;
  positions_value: number;
}

interface PnLPoint {
  time: string;
  value: number;
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
    api.getAccount().then(setAccount).catch(() => {});
    api.getPositions().then(setPositions).catch(() => {});
    api.getSimulationSummary().then(setSummary).catch(() => {});
    api.getQuantReadiness().then(setReadiness).catch(() => {});
    api.getSimulationRankings(10).then(setRankings).catch(() => {});
    api.getSimulationRuns(5).then((data) => setRuns(data.runs || [])).catch(() => {});
  }, []);

  const pnlPct = account ? account.total_pnl_pct * 100 : 0;
  const isGain = account ? account.total_pnl >= 0 : true;
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
                ¥{account.total_value.toLocaleString()}
              </div>
              <div className="metric-sub">
                可用现金 ¥{account.cash.toLocaleString()}
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">持仓市值</div>
              <div className="metric-value" style={{ fontSize: 'var(--font-size-2xl)' }}>
                ¥{account.positions_value?.toLocaleString() || '0'}
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
                {isGain ? '+' : ''}¥{account.total_pnl.toLocaleString()}
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
              <span className="section-badge">累计</span>
            </div>
            <PnLChart data={pnlHistory.length > 0 ? pnlHistory : generateMockPnl(account)} />
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

/** Generate mock PnL data when the backend history endpoint is not available yet. */
function generateMockPnl(account: Account): PnLPoint[] {
  const points: PnLPoint[] = [];
  const days = 14;
  const startValue = account.total_value - account.total_pnl;
  const start = new Date();
  start.setDate(start.getDate() - days);

  for (let i = 0; i <= days; i++) {
    const date = new Date(start);
    date.setDate(date.getDate() + i);
    const progress = i / days;
    const noise = (Math.sin(i * 1.8) * 0.3 + Math.cos(i * 0.7) * 0.2) * (account.total_pnl * 0.15);
    const value = Math.round(startValue + account.total_pnl * progress + noise);
    points.push({
      time: `${date.getMonth() + 1}/${date.getDate()}`,
      value,
    });
  }
  points[points.length - 1] = {
    time: points[points.length - 1].time,
    value: account.total_value,
  };
  return points;
}

import { useEffect, useState } from 'react';
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

  useEffect(() => {
    api.getAccount().then(setAccount).catch(() => {});
    api.getPositions().then(setPositions).catch(() => {});
  }, []);

  const pnlPct = account ? account.total_pnl_pct * 100 : 0;
  const isGain = account ? account.total_pnl >= 0 : true;

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
              <div className="metric-label">仓位比例</div>
              <div className="metric-value" style={{ fontSize: 'var(--font-size-2xl)' }}>
                {account.total_value > 0
                  ? ((account.positions_value || 0) / account.total_value * 100).toFixed(1)
                  : '0'}%
              </div>
              <div className="metric-sub">
                上限 80%
              </div>
            </div>
          </div>

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
        </>
      )}
    </div>
  );
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
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import PositionTable from '../components/PositionTable';
import PnLChart from '../components/PnLChart';

export default function Dashboard() {
  const [account, setAccount] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);

  useEffect(() => {
    api.getAccount().then(setAccount).catch(() => {});
    api.getPositions().then(setPositions).catch(() => {});
  }, []);

  if (!account) return <div className="loading">加载中...</div>;

  return (
    <div className="dashboard">
      <div className="account-cards">
        <div className="card">
          <div className="card-label">总资产</div>
          <div className="card-value">¥{account.total_value?.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">可用资金</div>
          <div className="card-value">¥{account.cash?.toLocaleString()}</div>
        </div>
        <div className={`card ${account.total_pnl >= 0 ? 'profit' : 'loss'}`}>
          <div className="card-label">总盈亏</div>
          <div className="card-value">
            ¥{account.total_pnl?.toLocaleString()}
            <span className="pct">({(account.total_pnl_pct * 100)?.toFixed(2)}%)</span>
          </div>
        </div>
      </div>

      <section className="section">
        <h2>盈亏走势</h2>
        <PnLChart data={[]} />
      </section>

      <section className="section">
        <h2>当前持仓</h2>
        <PositionTable positions={positions} />
      </section>
    </div>
  );
}

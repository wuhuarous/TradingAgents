import { useEffect, useState } from 'react';
import { api } from '../api/client';

interface Order {
  order_id: string;
  symbol: string;
  name: string;
  action: 'buy' | 'sell';
  price: number;
  quantity: number;
  cost: number;
  reason: string;
  timestamp: string;
  status: string;
}

export default function TradingLog() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getOrders()
      .then((data) => setOrders(data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <header className="page-header">
        <h1>交易记录</h1>
        <p>所有历史委托与成交明细</p>
      </header>

      {loading ? (
        <div className="loading-spinner">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
      ) : orders.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">⊟</div>
          <p>暂无交易记录</p>
          <div className="empty-hint">分析师团队产生交易信号后将自动执行并记录</div>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>代码</th>
              <th>名称</th>
              <th>方向</th>
              <th>价格</th>
              <th>数量</th>
              <th>金额</th>
              <th>状态</th>
              <th>理由</th>
            </tr>
          </thead>
          <tbody>
            {[...orders].reverse().map((o) => (
              <tr key={o.order_id}>
                <td>{new Date(o.timestamp).toLocaleString('zh-CN', {
                  month: '2-digit', day: '2-digit',
                  hour: '2-digit', minute: '2-digit',
                })}</td>
                <td className="mono" style={{ fontWeight: 600 }}>{o.symbol}</td>
                <td>{o.name || '—'}</td>
                <td>
                  <span className={`badge ${o.action}`}>
                    {o.action === 'buy' ? '买入' : '卖出'}
                  </span>
                </td>
                <td className="mono">¥{o.price?.toFixed(2)}</td>
                <td className="mono">{o.quantity.toLocaleString()}</td>
                <td className="mono">¥{o.cost?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                <td>{o.status || '已成交'}</td>
                <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {o.reason || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
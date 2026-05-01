import { useEffect, useState } from 'react';
import { api } from '../api/client';

export default function TradingLog() {
  const [orders, setOrders] = useState<any[]>([]);

  useEffect(() => {
    api.getOrders().then(setOrders).catch(() => {});
  }, []);

  return (
    <div className="page">
      <h1>交易记录</h1>
      <table className="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>股票</th>
            <th>操作</th>
            <th>价格</th>
            <th>数量</th>
            <th>金额</th>
            <th>理由</th>
          </tr>
        </thead>
        <tbody>
          {orders.slice().reverse().map((o: any, i: number) => (
            <tr key={i}>
              <td>{new Date(o.timestamp).toLocaleString()}</td>
              <td>{o.symbol} {o.name}</td>
              <td className={o.action === 'buy' ? 'buy-action' : 'sell-action'}>
                {o.action === 'buy' ? '买入' : '卖出'}
              </td>
              <td>¥{o.price?.toFixed(2)}</td>
              <td>{o.quantity}</td>
              <td>¥{o.cost?.toFixed(2)}</td>
              <td>{o.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface Position {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  pnl_pct: number;
  market_value?: number;
  pnl?: number;
}

export default function PositionTable({ positions }: { positions: Position[] }) {
  if (!positions || positions.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">∅</div>
        <p>暂无持仓</p>
        <div className="empty-hint">系统将在收到交易信号后自动建立仓位</div>
      </div>
    );
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>代码</th>
          <th>名称</th>
          <th>持仓</th>
          <th>成本</th>
          <th>现价</th>
          <th>市值</th>
          <th>盈亏</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((p) => {
          const mv = p.market_value || p.quantity * p.current_price;
          const pnl = p.pnl || (p.current_price - p.avg_cost) * p.quantity;
          const isGain = p.pnl_pct >= 0;
          return (
            <tr key={p.symbol}>
              <td className="mono" style={{ fontWeight: 600 }}>{p.symbol}</td>
              <td>{p.name}</td>
              <td className="mono">{p.quantity.toLocaleString()}</td>
              <td className="mono">¥{p.avg_cost.toFixed(2)}</td>
              <td className="mono">¥{p.current_price.toFixed(2)}</td>
              <td className="mono">¥{mv.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
              <td className={`mono ${isGain ? 'gain' : 'loss'}`}>
                {isGain ? '+' : ''}¥{pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                &nbsp;({(p.pnl_pct * 100).toFixed(2)}%)
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

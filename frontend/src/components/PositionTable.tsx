export default function PositionTable({ positions }: { positions: any[] }) {
  if (!positions?.length) return <div className="empty-state">暂无持仓</div>;
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>股票代码</th>
          <th>名称</th>
          <th>持仓数量</th>
          <th>成本价</th>
          <th>现价</th>
          <th>盈亏%</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((p: any) => (
          <tr key={p.symbol}>
            <td>{p.symbol}</td>
            <td>{p.name}</td>
            <td>{p.quantity}</td>
            <td>¥{p.avg_cost?.toFixed(2)}</td>
            <td>¥{p.current_price?.toFixed(2)}</td>
            <td className={p.pnl_pct >= 0 ? 'profit' : 'loss'}>
              {(p.pnl_pct * 100)?.toFixed(2)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

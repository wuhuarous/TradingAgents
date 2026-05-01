export default function PnLChart({ data }: { data: any[] }) {
  return (
    <div className="chart-placeholder">
      {data.length === 0 ? '暂无盈亏数据（需要完成交易后生成）' : ''}
    </div>
  );
}

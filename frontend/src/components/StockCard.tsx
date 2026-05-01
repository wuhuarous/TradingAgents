export default function StockCard({ symbol, decision }: any) {
  const conf = (decision?.confidence || 0) * 100;
  return (
    <div className="stock-card">
      <div className="stock-header">
        <span className="stock-symbol">{symbol}</span>
        <span className={`action-badge ${decision?.action}`}>
          {decision?.action === 'buy' ? '买入' : decision?.action === 'sell' ? '卖出' : '观望'}
        </span>
      </div>
      <div className="stock-body">
        <div>买入区间: ¥{decision?.price_lower} - ¥{decision?.price_upper}</div>
        <div>止损: ¥{decision?.stop_loss} | 止盈: ¥{decision?.take_profit}</div>
        <div>置信度: {conf.toFixed(0)}%</div>
      </div>
      <div className="stock-footer">{decision?.reasoning}</div>
    </div>
  );
}

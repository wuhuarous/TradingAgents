interface Decision {
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  price_lower: number;
  price_upper: number;
  stop_loss: number;
  take_profit: number;
  reasoning: string;
}

export default function StockCard({ symbol, name, decision }: {
  symbol: string;
  name?: string;
  decision: Decision;
}) {
  const confPct = Math.round((decision.confidence || 0) * 100);
  const actionLabel =
    decision.action === 'buy' ? '买入' :
    decision.action === 'sell' ? '卖出' : '观望';

  return (
    <div className="stock-card">
      <div className="stock-head">
        <div>
          <div className="stock-symbol">{symbol}</div>
          {name && <div className="stock-name">{name}</div>}
        </div>
        <span className={`stock-action ${decision.action}`}>
          {actionLabel}
        </span>
      </div>

      <div className="stock-metrics">
        <div>
          <div className="stock-metric-label">买入区间</div>
          <div className="stock-metric-value">
            ¥{decision.price_lower} – ¥{decision.price_upper}
          </div>
        </div>
        <div>
          <div className="stock-metric-label">止损</div>
          <div className="stock-metric-value" style={{ color: 'var(--loss)' }}>
            ¥{decision.stop_loss}
          </div>
        </div>
        <div>
          <div className="stock-metric-label">止盈</div>
          <div className="stock-metric-value" style={{ color: 'var(--gain)' }}>
            ¥{decision.take_profit}
          </div>
        </div>
        <div>
          <div className="stock-metric-label">置信度</div>
          <div className="stock-metric-value" style={{ color: 'var(--amber)' }}>
            {confPct}%
          </div>
        </div>
      </div>

      <div className="stock-confidence">
        <span>置信度</span>
        <div className="conf-bar">
          <div
            className="conf-fill"
            style={{ width: `${confPct}%` }}
          />
        </div>
        <span>{confPct}%</span>
      </div>

      {decision.reasoning && (
        <div className="stock-reason">{decision.reasoning}</div>
      )}
    </div>
  );
}

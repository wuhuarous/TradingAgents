export default function Settings() {
  return (
    <div className="page">
      <header className="page-header">
        <h1>系统配置</h1>
        <p>风险控制 · 模型选择 · 数据源 · 交易参数</p>
      </header>

      <div className="settings-grid">
        <div className="settings-card">
          <h3>LLM 模型</h3>
          <p>当前引擎驱动 10 节点多智能体工作流，开发中</p>
        </div>
        <div className="settings-card">
          <h3>风控参数</h3>
          <p>单仓位上限 20% · 总仓位上限 80% · 日止损线 3%</p>
        </div>
        <div className="settings-card">
          <h3>数据源</h3>
          <p>yfinance · Tushare · AKShare — Phase 2 可配置</p>
        </div>
        <div className="settings-card">
          <h3>通知</h3>
          <p>交易执行、风险告警、每日复盘 — Phase 2 接入</p>
        </div>
      </div>
    </div>
  );
}
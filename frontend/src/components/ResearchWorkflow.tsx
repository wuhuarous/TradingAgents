import { Link } from 'react-router-dom';

const STEPS = [
  { key: 'market', label: '行情', desc: '仓位环境', to: '/market' },
  { key: 'news', label: '资讯', desc: '事件风险', to: '/news' },
  { key: 'screener', label: '选股', desc: '候选池', to: '/screener' },
  { key: 'analysis', label: '分析', desc: '交易证据', to: '/analysis' },
  { key: 'backtest', label: '回测', desc: '策略验证', to: '/backtest' },
  { key: 'simulation', label: '模拟', desc: '复盘训练', to: '/simulation' },
];

export default function ResearchWorkflow({ active }: { active: string }) {
  return (
    <nav className="workflow-strip" aria-label="量化研究闭环">
      {STEPS.map((step, index) => (
        <Link className={`workflow-step ${active === step.key ? 'active' : ''}`} to={step.to} key={step.key}>
          <span className="workflow-index">{index + 1}</span>
          <span>
            <strong>{step.label}</strong>
            <small>{step.desc}</small>
          </span>
        </Link>
      ))}
    </nav>
  );
}

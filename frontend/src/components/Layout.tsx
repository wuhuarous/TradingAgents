import { NavLink } from 'react-router-dom';

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-brand">
          <div className="mark">T</div>
          <div className="name">Trading<span>Agents</span></div>
        </div>

        <ul className="sidebar-nav">
          <li>
            <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">⊡</span>仪表盘
            </NavLink>
          </li>
          <li>
            <NavLink to="/market" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">⊟</span>行情总览
            </NavLink>
          </li>
          <li>
            <NavLink to="/screener" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">⊞</span>智能选股
            </NavLink>
          </li>
          <li>
            <NavLink to="/simulation" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">▣</span>模拟训练
            </NavLink>
          </li>
          <li>
            <NavLink to="/backtest" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">▤</span>回测复盘
            </NavLink>
          </li>
          <li>
            <NavLink to="/reports" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">▥</span>收益报表
            </NavLink>
          </li>
          <li>
            <NavLink to="/news" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">⊠</span>新闻资讯
            </NavLink>
          </li>
          <li>
            <NavLink to="/analysis" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">◎</span>深度分析
            </NavLink>
          </li>
          <li>
            <NavLink to="/trades" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">⊡</span>交易记录
            </NavLink>
          </li>
          <li>
            <NavLink to="/settings" className={({ isActive }) => isActive ? 'active' : ''}>
              <span className="nav-icon">⚙</span>系统配置
            </NavLink>
          </li>
        </ul>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className="dot" />
            系统运行中
          </div>
          <div>v0.1.0 · Phase 1</div>
        </div>
      </nav>

      <main className="main-content">{children}</main>
    </div>
  );
}

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
            <NavLink
              to="/"
              end
              className={({ isActive }) => isActive ? 'active' : ''}
            >
              <span className="nav-icon">⊡</span>
              仪表盘
            </NavLink>
          </li>
          <li>
            <NavLink
              to="/trades"
              className={({ isActive }) => isActive ? 'active' : ''}
            >
              <span className="nav-icon">⊞</span>
              交易记录
            </NavLink>
          </li>
          <li>
            <NavLink
              to="/settings"
              className={({ isActive }) => isActive ? 'active' : ''}
            >
              <span className="nav-icon">⊠</span>
              系统配置
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

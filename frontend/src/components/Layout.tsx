import { Link } from 'react-router-dom';

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="logo">TradingAgents</div>
        <ul className="nav-links">
          <li><Link to="/">仪表盘</Link></li>
          <li><Link to="/trades">交易记录</Link></li>
          <li><Link to="/settings">系统配置</Link></li>
        </ul>
      </nav>
      <main className="main-content">{children}</main>
    </div>
  );
}

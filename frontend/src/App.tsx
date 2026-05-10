import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import MarketOverview from './pages/MarketOverview';
import Screener from './pages/Screener';
import NewsFeed from './pages/NewsFeed';
import AnalysisDetail from './pages/AnalysisDetail';
import StockDetail from './pages/StockDetail';
import TradingLog from './pages/TradingLog';
import Settings from './pages/Settings';
import SimulationLab from './pages/SimulationLab';
import BacktestLab from './pages/BacktestLab';
import Reports from './pages/Reports';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/market" element={<MarketOverview />} />
        <Route path="/stock" element={<StockDetail />} />
        <Route path="/simulation" element={<SimulationLab />} />
        <Route path="/backtest" element={<BacktestLab />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/screener" element={<Screener />} />
        <Route path="/news" element={<NewsFeed />} />
        <Route path="/analysis" element={<AnalysisDetail />} />
        <Route path="/analysis/:symbol" element={<AnalysisDetail />} />
        <Route path="/trades" element={<TradingLog />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}

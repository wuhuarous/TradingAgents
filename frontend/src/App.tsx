import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import MarketOverview from './pages/MarketOverview';
import Screener from './pages/Screener';
import NewsFeed from './pages/NewsFeed';
import AnalysisDetail from './pages/AnalysisDetail';
import TradingLog from './pages/TradingLog';
import Settings from './pages/Settings';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/market" element={<MarketOverview />} />
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

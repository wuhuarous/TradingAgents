import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import TradingLog from './pages/TradingLog';
import Settings from './pages/Settings';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/trades" element={<TradingLog />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}

const BASE = import.meta.env.VITE_API_BASE || '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text().catch(() => 'Unknown error');
    throw new Error(err);
  }
  return res.json();
}

export const api = {
  // Account
  getAccount: () => request<any>('/account/'),
  getAccountOverview: () => request<any>('/account/overview'),
  getPositions: () => request<any[]>('/account/positions'),
  getOrders: (limit?: number) =>
    request<any[]>(`/account/orders${limit ? `?limit=${limit}` : ''}`),

  // Trading
  executeTrade: (data: { symbol: string; action: string; price: number; quantity: number }) =>
    request<any>('/trading/execute', { method: 'POST', body: JSON.stringify(data) }),

  // Stocks
  getQuote: (symbol: string, market: string) =>
    request<any>(`/stocks/quote?symbol=${encodeURIComponent(symbol)}&market=${market}`),
  searchStocks: (keyword: string, market: string) =>
    request<any[]>(`/stocks/search?keyword=${encodeURIComponent(keyword)}&market=${market}`),
  getStockDetail: (symbol: string, market: string, period?: string) =>
    request<any>(`/stocks/detail?symbol=${encodeURIComponent(symbol)}&market=${market}&period=${period || '3mo'}`),

  // Market overview
  getMarketOverview: (market: string) => request<any>(`/market/overview?market=${market}`),

  // Screener
  screenStocks: (params: Record<string, any>) =>
    request<any>('/screener/screen', { method: 'POST', body: JSON.stringify(params) }),

  // Analysis
  runAnalysis: (symbol: string, market: string) =>
    request<any>('/analysis/run', {
      method: 'POST',
      body: JSON.stringify({ symbol, market }),
    }),

  // News
  getNews: (market: string, limit?: number) =>
    request<any[]>(`/news/?market=${market}&limit=${limit || 30}`),

  // Simulation training
  getSimulationSummary: () => request<any>('/simulation/summary'),
  getQuantReadiness: () => request<any>('/simulation/readiness'),
  getSimulationCandidates: (market: string, limit?: number) =>
    request<any>(`/simulation/candidates?market=${market}&limit=${limit || 10}`),
  getSimulationRankings: (limit?: number) =>
    request<any>(`/simulation/rankings?limit=${limit || 10}`),
  runSimulationCycle: (market: string) =>
    request<any>(`/simulation/run?market=${market}`, { method: 'POST' }),
  getSimulationRuns: (limit?: number) =>
    request<any>(`/simulation/runs?limit=${limit || 20}`),
  getSimulationEvents: (kind: string, limit?: number) =>
    request<any>(`/simulation/events?kind=${kind}&limit=${limit || 50}`),
  getEventStoreStatus: () => request<any>('/simulation/event-store/status'),
  backfillSimulationReviews: (limit?: number, forceLatest?: boolean) =>
    request<any>(`/simulation/backfill-reviews?limit=${limit || 20}&force_latest=${forceLatest ? 'true' : 'false'}`, { method: 'POST' }),
  syncDailyKlines: (market: string, limit?: number) =>
    request<any>(`/data-quality/sync-klines?market=${market}&limit=${limit || 50}&role=all`, { method: 'POST' }),
  getDailyPnl: (days?: number) =>
    request<any>(`/portfolio/daily-pnl?days=${days || 30}`),
  getPortfolioReport: (days?: number) =>
    request<any>(`/portfolio/report?days=${days || 180}`),

  // Backtest
  runBacktest: (params: {
    strategy?: string;
    market: string;
    period: string;
    initial_cash?: number;
    universe_limit?: number;
    top_n?: number;
    rebalance_days?: number;
  }) => {
    const query = new URLSearchParams({
      strategy: params.strategy || 'baseline_momentum',
      market: params.market,
      period: params.period,
      initial_cash: String(params.initial_cash || 1000000),
      universe_limit: String(params.universe_limit || 200),
      top_n: String(params.top_n || 5),
      rebalance_days: String(params.rebalance_days || 20),
    });
    return request<any>(`/backtest/run?${query.toString()}`, { method: 'POST' });
  },
  getBacktestRuns: (market?: string, limit?: number) => {
    const query = new URLSearchParams({ limit: String(limit || 30) });
    if (market) query.set('market', market);
    return request<any>(`/backtest/runs?${query.toString()}`);
  },
  getBacktestRun: (runId: string) =>
    request<any>(`/backtest/runs/${encodeURIComponent(runId)}`),

  // Research experiments
  getQlibStatus: () => request<any>('/research/qlib/status'),
  getQlibProjectDataStatus: (market?: string) => {
    const query = new URLSearchParams();
    if (market) query.set('market', market);
    return request<any>(`/research/qlib/project-data-status?${query.toString()}`);
  },
  prepareQlibData: () =>
    request<any>('/research/qlib/prepare-data', { method: 'POST' }),
  exportQlibProjectData: (params: {
    market: string;
    target_dir?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    min_rows?: number;
    overwrite?: boolean;
  }) => {
    const query = new URLSearchParams({
      market: params.market,
      limit: String(params.limit || 500),
      min_rows: String(params.min_rows || 30),
      overwrite: params.overwrite ? 'true' : 'false',
    });
    if (params.target_dir) query.set('target_dir', params.target_dir);
    if (params.start_date) query.set('start_date', params.start_date);
    if (params.end_date) query.set('end_date', params.end_date);
    return request<any>(`/research/qlib/export-project-data?${query.toString()}`, { method: 'POST' });
  },
  runQlibExperiment: (params?: {
    top_n?: number;
    n_drop?: number;
    download_data?: boolean;
  }) => {
    const query = new URLSearchParams({
      top_n: String(params?.top_n || 50),
      n_drop: String(params?.n_drop || 5),
      download_data: params?.download_data ? 'true' : 'false',
    });
    return request<any>(`/research/experiments/run-qlib?${query.toString()}`, { method: 'POST' });
  },
  runResearchGrid: (params: {
    strategy?: string;
    market: string;
    period: string;
    initial_cash?: number;
    universe_limit?: number;
    top_n_options?: string;
    rebalance_options?: string;
  }) => {
    const query = new URLSearchParams({
      strategy: params.strategy || 'baseline_momentum',
      market: params.market,
      period: params.period,
      initial_cash: String(params.initial_cash || 1000000),
      universe_limit: String(params.universe_limit || 200),
      top_n_options: params.top_n_options || '3,5',
      rebalance_options: params.rebalance_options || '10,20',
    });
    return request<any>(`/research/experiments/run-grid?${query.toString()}`, { method: 'POST' });
  },
  getStrategyLeaderboard: (market?: string, limit?: number) => {
    const query = new URLSearchParams({ limit: String(limit || 20) });
    if (market) query.set('market', market);
    return request<any>(`/research/leaderboard?${query.toString()}`);
  },

  // Settings
  getSettings: () => request<any>('/settings/'),
  updateSettings: (data: Record<string, any>) =>
    request<any>('/settings/', { method: 'PUT', body: JSON.stringify(data) }),

  // Health
  health: () => request<any>('/health'),
};

const BASE = '/api';

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

  // Settings
  getSettings: () => request<any>('/settings/'),
  updateSettings: (data: Record<string, any>) =>
    request<any>('/settings/', { method: 'PUT', body: JSON.stringify(data) }),

  // Health
  health: () => request<any>('/health'),
};

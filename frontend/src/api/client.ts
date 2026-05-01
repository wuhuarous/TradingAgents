const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  getAccount: () => request<any>('/account/'),
  getPositions: () => request<any[]>('/account/positions'),
  getOrders: () => request<any[]>('/account/orders'),
  executeTrade: (data: any) =>
    request<any>('/trading/execute', { method: 'POST', body: JSON.stringify(data) }),
  runAnalysis: (symbol: string, market: string) =>
    request<any>('/analysis/run', {
      method: 'POST',
      body: JSON.stringify({ symbol, market }),
    }),
  getQuote: (symbol: string, market: string) =>
    request<any>(`/stocks/quote?symbol=${symbol}&market=${market}`),
  searchStocks: (keyword: string, market: string) =>
    request<any[]>(`/stocks/search?keyword=${keyword}&market=${market}`),
};

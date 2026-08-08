/**
 * API client.
 * `__PORT_8000__` is rewritten to the proxy path at deploy time; during local
 * development it stays literal, so we fall back to the dev backend URL.
 */
const RAW = '__PORT_8000__';
export const API_BASE =
  RAW.startsWith('__') ? (import.meta.env.VITE_API_BASE || 'http://localhost:8000') : RAW;

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json();
}

export const api = {
  health: () => get<any>('/api/health'),
  overview: (lang = 'en') => get<any>(`/api/overview?lang=${lang}`),
  geojson: () => get<any>('/api/geojson'),
  riskMap: () => get<any>('/api/risk-map'),
  plots: () => get<any[]>('/api/plots'),
  farms: () => get<any[]>('/api/farms'),
  plot: (id: string, lang = 'en') => get<any>(`/api/plots/${id}?lang=${lang}`),
  advisory: (id: string, lang = 'en') => get<any>(`/api/plots/${id}/advisory?lang=${lang}`),
  explain: (id: string, model: string) => get<any>(`/api/plots/${id}/explain/${model}`),
  ndviGrid: (id: string, size = 14) => get<any>(`/api/plots/${id}/ndvi-grid?size=${size}`),
  twin: (id: string) => get<any>(`/api/plots/${id}/digital-twin`),
  benchmark: () => get<any>('/api/benchmark'),
  offline: (lang = 'en') => get<any>(`/api/offline-bundle?lang=${lang}`),
  smsOutbox: () => get<any[]>('/api/sms/outbox'),
  indices: (b: any) => post<any>('/api/indices', b),
  sms: (plot_id: string, lang: string) => post<any>('/api/sms', { plot_id, lang }),
  irrigate: (plot_id: string, valve = 'V1', mode = 'auto') =>
    post<any>('/api/irrigation/command', { plot_id, valve, mode }),
};

export const LANGS = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
];

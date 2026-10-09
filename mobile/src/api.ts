export type MarketStats = { listings_count: number; median_price_rub: number | null };
export type Device = {
  model_id: string; name: string; brand: string; tier: string; msrp_rub: number;
  current_price_rub: number | null; residual_value_percent: number | null;
  depreciation_drop_percent: number | null; forecast_summary: string | null;
  market_stats: MarketStats | null; characteristics?: Record<string, unknown>;
};

const API_URL = (process.env.EXPO_PUBLIC_API_URL || 'http://10.0.2.2:8000/api/v1').replace(/\/$/, '');
const TIMEOUT_MS = 10000;

export async function request<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${API_URL}${path}`, { signal: controller.signal });
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(body?.message || `Ошибка API (${response.status})`);
    return body as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw new Error('Превышено время ожидания API');
    if (error instanceof TypeError) throw new Error('Нет соединения с API');
    throw error;
  } finally { clearTimeout(timer); }
}

export const searchDevices = (query: string) => request<Device[]>(`/devices/search?query=${encodeURIComponent(query)}`);
export const compareDevices = (ids: string[]) => request<{ devices: Device[] }>(`/analytics/compare?${ids.map((id) => `model_ids=${encodeURIComponent(id)}`).join('&')}`);
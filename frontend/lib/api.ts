export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api').replace(/\/$/, '');

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: 'include', signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`API request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    signal: AbortSignal.timeout(5000),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function moduleRows(moduleKey: string, payload: any): string[] {
  const rows = Array.isArray(payload) ? payload : payload?.items || [];
  if (moduleKey === 'customer-360') return rows.map((row: any) => `${row.name} · ${row.id} · ${row.segment} · ${row.plan}`);
  if (moduleKey === 'campaign-calendar') return rows.map((row: any) => `${row.name} · ${row.start_date || 'No start date'} · ${row.status}`);
  if (moduleKey === 'audience-segments' || moduleKey === 'ai-segment-builder') return rows.map((row: any) => `${row.name} · ${Number(row.customer_count).toLocaleString()} customers`);
  if (moduleKey === 'offer-management') return rows.map((row: any) => `${row.name} · ${row.product} · PKR ${row.price} · ${row.validity_days} days`);
  return rows.map((row: any) => `${row.name || row.label || row.id} · ${row.status || 'Recorded'}${row.channel ? ` · ${row.channel}` : ''}`);
}

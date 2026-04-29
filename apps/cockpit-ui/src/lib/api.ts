// Hand-rolled fetch wrapper for the cockpit-api (Story 1.4 AC #11).
// Injects the X-Cockpit-Demo-User header on every request.
// TODO(story-2-11): swap to openapi-fetch once `make contracts` exports types.

import { useCurrentUser } from '@/stores/currentUser';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { user } = useCurrentUser.getState();
  const headers = new Headers(init.headers);
  headers.set('X-Cockpit-Demo-User', user.id);
  headers.set('Accept', 'application/json');

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`API ${resp.status} ${resp.statusText}: ${text}`);
  }
  return (await resp.json()) as T;
}

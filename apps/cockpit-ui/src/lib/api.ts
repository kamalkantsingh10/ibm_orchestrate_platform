// Typed API client for the cockpit-api (Story 2.2).
//
// Uses openapi-fetch over the generated `paths` type from `@/api-types`.
// The X-Cockpit-Demo-User header is read on every request from the
// Zustand currentUser store so user-switcher changes propagate without
// recreating the client.
//
// Default `baseUrl` is empty (same-origin) so requests go through Vite's
// dev-server proxy — see vite.config.ts. This keeps the demo behind a
// single URL when exposed via ngrok / cloudflared. Override with
// `VITE_API_BASE_URL` for builds that talk directly to a remote API.

import createClient from 'openapi-fetch';
import type { paths } from '@/api-types';
import { useCurrentUser } from '@/stores/currentUser';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export const apiClient = createClient<paths>({
  baseUrl: API_BASE,
  headers: {
    Accept: 'application/json',
  },
  // Indirect through globalThis so vi.stubGlobal('fetch', ...) works in tests.
  fetch: (...args) => globalThis.fetch(...args),
});

apiClient.use({
  onRequest({ request }) {
    request.headers.set('X-Cockpit-Demo-User', useCurrentUser.getState().user.id);
    return request;
  },
});

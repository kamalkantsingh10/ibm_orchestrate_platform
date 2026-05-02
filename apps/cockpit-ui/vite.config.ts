import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // Allow ngrok / cloudflared / tailscale-funnel hostnames so the demo can
    // be exposed publicly via a single tunnel (see README "Exposing the demo").
    allowedHosts: true,
    // Proxy the cockpit-api so the UI's API calls are same-origin. Visitors
    // hit one URL (the Vite dev server / tunnel) and `/v1/*` + `/health` are
    // forwarded to localhost:8000.
    proxy: {
      '/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});

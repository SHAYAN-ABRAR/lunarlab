import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The production build is served by the FastAPI backend (same origin).
// In development (`npm run dev`), /api is proxied to the backend on 127.0.0.1:8765;
// start the backend with LUNARLAB_DEV=1 so it accepts the dev-server origin.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8765', changeOrigin: false } },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
  },
})

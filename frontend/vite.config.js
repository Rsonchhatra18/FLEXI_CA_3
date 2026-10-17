import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During `npm run dev` the React app runs on :5173 and forwards /api/* to the
// Python backend (python server.py on :8000). `npm run build` writes dist/,
// which server.py then serves itself on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// BACKEND_URL se pasa como variable de entorno del shell (no del .env de Vite)
// Linux con certs: https://localhost:8000 (default)
// Windows sin certs: BACKEND_URL=http://localhost:8000 npm run dev
const backendTarget = process.env.BACKEND_URL ?? 'https://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: backendTarget,
        rewrite: (path) => path.replace(/^\/api/, ''),
        secure: false,
        changeOrigin: true,
      },
    },
  },
})

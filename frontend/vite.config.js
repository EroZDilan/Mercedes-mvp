import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import basicSsl from '@vitejs/plugin-basic-ssl'

const backendTarget = process.env.BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss(), basicSsl()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: backendTarget,
        rewrite: (path) => path.replace(/^\/api/, ''),
        secure: false,
        changeOrigin: true,
        proxyTimeout: 180000,  // 3 min — Ollama puede tardar en responder
        timeout: 180000,
      },
    },
  },
})

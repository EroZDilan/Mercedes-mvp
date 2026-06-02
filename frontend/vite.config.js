import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const BACKEND = process.env.VITE_BACKEND_URL || 'http://localhost:8000'
const HTTPS_BACKEND = BACKEND.startsWith('https')

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: BACKEND,
        rewrite: (path) => path.replace(/^\/api/, ''),
        // necesario con certificados autofirmados
        secure: !HTTPS_BACKEND,
      },
    },
  },
})

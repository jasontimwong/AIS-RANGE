import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/ui/',
  build: {
    outDir: 'dist'
  },
  server: {
    port: 3001,
    proxy: {
      '/plan': 'http://localhost:8001',
      '/validate': 'http://localhost:8001',
      '/export': 'http://localhost:8001',
      '/import': 'http://localhost:8001',
      '/enc': 'http://localhost:8001',
      '/status': 'http://localhost:8001',
      '/api/route': 'http://localhost:8001',
      '/api/eval': 'http://localhost:8001',
      '/api/ais': 'http://localhost:8001',
      '/api/test': 'http://localhost:8001',
      '/ws': {
        target: 'http://localhost:8001',
        ws: true,
        changeOrigin: true
      }
    }
  }
})

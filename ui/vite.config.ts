import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/ui/',
  build: {
    outDir: 'dist'
  },
  server: {
    port: 3000,
    proxy: {
      '/plan': 'http://localhost:8000',
      '/validate': 'http://localhost:8000',
      '/export': 'http://localhost:8000',
      '/import': 'http://localhost:8000',
      '/enc': 'http://localhost:8000',
      '/status': 'http://localhost:8000',
      '/api/ais': 'http://localhost:8000',
      '/ws': {
        target: 'http://localhost:8000',
        ws: true,
        changeOrigin: true
      }
    }
  }
})

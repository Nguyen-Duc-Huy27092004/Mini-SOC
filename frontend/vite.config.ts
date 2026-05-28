import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:8000',  ws: true },
      '/metrics': { target: 'http://localhost:8000' },
    },
  },
  build: {
    // Split large vendor chunks to improve load time
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react':   ['react', 'react-dom', 'react-router-dom'],
          'vendor-echarts': ['echarts', 'echarts-for-react'],
          'vendor-ui':      ['lucide-react', 'clsx', 'tailwind-merge'],
          'vendor-state':   ['zustand', 'axios'],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
})

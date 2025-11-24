import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

const proxyTarget =
  process.env.VITE_PROXY_TARGET ||
  process.env.VITE_API_URL ||
  'http://backend:5000' // 在 docker-compose 内，直接连 backend 服务

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})

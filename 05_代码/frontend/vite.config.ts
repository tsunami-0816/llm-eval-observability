import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true, // Windows 下 Vite 默认仅监听 IPv6 回环，显式开启以同时支持 IPv4 访问
    port: 5179,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8086',
        changeOrigin: true,
      },
    },
  },
})

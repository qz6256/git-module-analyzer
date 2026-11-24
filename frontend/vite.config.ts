import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      // 后端契约前缀本身就是 /api/v1，不做 rewrite，原样透传
      '^/api': {
        target: 'http://127.0.0.1:8777',
        changeOrigin: true,
      },
    },
  },
})

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  base: process.env.NODE_ENV === 'production' ? '/static/' : '/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    origin: 'http://127.0.0.1:5173',
    cors: true,
  },
  build: {
    manifest: true,
    outDir: 'dist',
    rollupOptions: {
    input: '/src/main.js',
    },
  },
})
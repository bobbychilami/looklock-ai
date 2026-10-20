import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
// From `vitest/config`, not `vite`: the extended config type is what gives
// `test` its type-checking here, so a mistyped option fails the build rather
// than being silently ignored at runtime.
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Keeps the browser on a single origin in development, so no CORS
      // preflight and no chance of a relative-path bug in production.
      '/api': {
        target: process.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    // The components are rendered, not string-compared, so a DOM is required.
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
})

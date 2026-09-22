import react from '@vitejs/plugin-react'
// vitest/config rather than vite, so the `test` block below is typed.
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    // e2e/ belongs to Playwright; vitest would try to run it as a unit test.
    include: ['src/**/*.test.ts'],
  },
})

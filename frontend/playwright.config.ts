import { defineConfig, devices } from '@playwright/test'

// Drives the real page against the real Live API: the worklet, resampler,
// playback and SDK wiring that the unit tests cannot reach.
export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/generate-speech.ts',
  timeout: 150_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'http://localhost:5173',
    permissions: ['microphone'],
  },
  webServer: [
    {
      command: 'uv run uvicorn kataribe.main:app --port 8000',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'pnpm dev --port 5173 --strictPort',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})

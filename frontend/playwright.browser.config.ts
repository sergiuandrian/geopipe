/**
 * Browser smoke against a running GeoPipe preview (local or Vercel).
 * Usage: BASE_URL=http://127.0.0.1:4173 npx playwright test -c playwright.browser.config.ts
 */
import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.BASE_URL || 'http://127.0.0.1:4173'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'on',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})

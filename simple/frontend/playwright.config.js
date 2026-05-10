import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:8123',
    headless: true,
    channel: process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'msedge',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'python manage.py runserver 127.0.0.1:8123 --noreload',
    cwd: '..',
    url: 'http://127.0.0.1:8123/login',
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      DJANGO_VITE_DEV_MODE: 'False',
    },
  },
})

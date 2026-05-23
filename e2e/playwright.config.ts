import { defineConfig, devices } from '@playwright/test';

/**
 * E2E на боевом проде https://grammy.mediann.dev
 * Переменные:
 *   E2E_BASE_URL    — корень фронта (default: https://grammy.mediann.dev)
 *   E2E_ADMIN_USER  — username (default: admin)
 *   E2E_ADMIN_PASS  — required, без него ничего не запустится
 */
const baseURL = process.env.E2E_BASE_URL || 'https://grammy.mediann.dev';

export default defineConfig({
  testDir: './tests',
  testIgnore: '**/global-setup.ts',
  globalSetup: require.resolve('./tests/global-setup.ts'),
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  timeout: 30_000,
  reporter: process.env.CI ? [['html'], ['github']] : [['list'], ['html']],
  expect: { timeout: 5_000 },

  use: {
    baseURL,
    headless: true,
    viewport: { width: 1280, height: 800 },
    ignoreHTTPSErrors: true,
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    storageState: './.auth/state.json',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});

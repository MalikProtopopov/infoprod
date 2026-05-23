import { test as base, expect, Page } from '@playwright/test';

/**
 * adminPage — playwright Page с cookie из globalSetup (один логин на все тесты,
 * чтобы не упереться в rate-limit /api/auth/login).
 */
type Fixtures = {
  adminPage: Page;
};

export const test = base.extend<Fixtures>({
  adminPage: async ({ page }, use) => {
    await use(page);
  },
});

export { expect };

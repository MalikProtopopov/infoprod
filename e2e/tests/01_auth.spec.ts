import { test, expect } from './fixtures';

// Login-тесты не используют сохранённую куку — иначе они не смогут протестировать редирект
test.use({ storageState: { cookies: [], origins: [] } });

test.describe('Auth', () => {
  test('login page loads', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: /Вход/i })).toBeVisible();
    await expect(page.getByLabel('Логин')).toBeVisible();
    await expect(page.getByLabel('Пароль')).toBeVisible();
  });

  test('unauthorized user is redirected to /login', async ({ page }) => {
    await page.goto('/');
    await page.waitForURL(/\/login$/, { timeout: 5_000 });
  });

  // Реальный login через UI экономим на rate-limit; flow проверяется в globalSetup

  // wrong-password тест опускаем намеренно: rate-limit на prod /api/auth/login.
  // Этот сценарий покрывается backend pytest'ом.
});

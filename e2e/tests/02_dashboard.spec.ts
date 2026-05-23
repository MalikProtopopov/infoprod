import { test, expect } from './fixtures';

test.describe('Dashboard', () => {
  test('renders main stats', async ({ adminPage }) => {
    await adminPage.goto('/');
    await expect(adminPage.getByText('Активные подписки')).toBeVisible();
    await expect(adminPage.getByText('Новые заявки')).toBeVisible();
    await expect(adminPage.getByText('Пользователи бота')).toBeVisible();
    await expect(adminPage.getByText(/Оборот за/)).toBeVisible();
  });

  test('navigation links work', async ({ adminPage }) => {
    await adminPage.goto('/');
    // Через sidebar
    await adminPage.getByRole('link', { name: 'Продукты', exact: true }).first().click();
    await adminPage.waitForURL(/\/products$/);
  });
});

import { test, expect } from './fixtures';

const ROUTES: Array<{ url: string; expect: RegExp }> = [
  { url: '/leads', expect: /Заявки/ },
  { url: '/users', expect: /Пользователи/ },
  { url: '/payments', expect: /Платежи/ },
  { url: '/subscriptions', expect: /Подписки/ },
  { url: '/products', expect: /Продукты/ },
  { url: '/channels', expect: /Каналы/ },
  { url: '/bots', expect: /Боты/ },
  { url: '/funnels', expect: /Воронки/ },
  { url: '/lead-magnets', expect: /Лидмагниты/ },
  { url: '/funnel-triggers', expect: /Кодовые слова/ },
  { url: '/sources', expect: /Источники/ },
];

test.describe('All routes load', () => {
  for (const route of ROUTES) {
    test(`${route.url} renders heading`, async ({ adminPage }) => {
      const resp = await adminPage.goto(route.url);
      expect(resp?.status()).toBeLessThan(400);
      await expect(adminPage.getByRole('heading', { name: route.expect }).first()).toBeVisible();
    });
  }
});

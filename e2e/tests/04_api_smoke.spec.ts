import { test, expect } from './fixtures';

/**
 * API smoke: проверка что все основные endpoint'ы отвечают для авторизованного пользователя.
 */
const ENDPOINTS = [
  '/api/healthz',
  '/api/auth/me',
  '/api/bots',
  '/api/channels',
  '/api/products',
  '/api/users',
  '/api/leads',
  '/api/payments',
  '/api/subscriptions',
  '/api/tracking-links',
  '/api/stats/overview',
  '/api/stats/sources?group_by=source',
  '/api/funnels',
  '/api/lead-magnets',
  '/api/funnel-triggers',
];

test.describe('API smoke', () => {
  for (const path of ENDPOINTS) {
    test(`GET ${path} returns 200`, async ({ adminPage }) => {
      const resp = await adminPage.request.get(path);
      expect(resp.ok(), `${path} → ${resp.status()}`).toBe(true);
    });
  }
});

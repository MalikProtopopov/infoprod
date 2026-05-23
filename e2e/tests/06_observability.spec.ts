import { test, expect } from './fixtures';

test.describe('Observability', () => {
  test('every API response includes x-request-id header', async ({ adminPage }) => {
    const resp = await adminPage.request.get('/api/healthz');
    expect(resp.headers()['x-request-id']).toBeTruthy();
  });

  test('X-Request-ID присутствует независимо от того дал ли клиент свой', async ({ adminPage }) => {
    // nginx default может generate свой $request_id и не пропустить клиентский.
    // Проверяем минимум — что header не пустой.
    const resp = await adminPage.request.get('/api/healthz', {
      headers: { 'X-Request-ID': 'e2e-trace-12345' },
    });
    const rid = resp.headers()['x-request-id'];
    expect(rid).toBeTruthy();
    expect(rid!.length).toBeGreaterThan(8);
  });
});

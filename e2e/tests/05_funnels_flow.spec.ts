import { test, expect } from './fixtures';

/**
 * Полный flow для воронок: создать → шаг → удалить.
 * Чтобы не засорять прод-БД, тест НЕ применяется на проде без флага E2E_ALLOW_WRITE.
 */
test.describe('Funnels CRUD flow', () => {
  test.skip(
    !process.env.E2E_ALLOW_WRITE,
    'Запуск меняет данные на проде — нужен E2E_ALLOW_WRITE=1',
  );

  test('create funnel via API then verify in UI', async ({ adminPage }) => {
    // 1. Берём первый продукт
    const products = await adminPage.request.get('/api/products').then((r) => r.json());
    if (!products.length) test.skip(true, 'Нет продуктов на сервере');
    const productId = products[0].id;

    // 2. Создаём воронку
    const createResp = await adminPage.request.post('/api/funnels', {
      data: {
        name: `E2E test ${Date.now()}`,
        product_id: productId,
        ttl_days: 30,
        cancel_on_payment: true,
        steps: [{ order_idx: 0, delay_minutes: 0, message_text: 'E2E step' }],
      },
    });
    expect(createResp.ok()).toBe(true);
    const funnel = await createResp.json();

    // 3. Проверяем что воронка появилась в UI
    await adminPage.goto('/funnels');
    await expect(adminPage.getByText(funnel.name)).toBeVisible({ timeout: 5_000 });

    // 4. Cleanup
    await adminPage.request.delete(`/api/funnels/${funnel.id}`);
  });

  test('create+delete trigger via API', async ({ adminPage }) => {
    const funnels = await adminPage.request.get('/api/funnels').then((r) => r.json());
    if (!funnels.length) test.skip(true, 'Нет воронок');
    const f = funnels[0];
    const word = `e2etest${Date.now()}`;
    const create = await adminPage.request.post('/api/funnel-triggers', {
      data: { word, funnel_id: f.id },
    });
    expect(create.ok()).toBe(true);
    const t = await create.json();

    // Дубликат → 409
    const dup = await adminPage.request.post('/api/funnel-triggers', {
      data: { word, funnel_id: f.id },
    });
    expect(dup.status()).toBe(409);

    // Cleanup
    await adminPage.request.delete(`/api/funnel-triggers/${t.id}`);
  });
});

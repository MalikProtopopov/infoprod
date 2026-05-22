import { http, HttpResponse } from 'msw';

const API = '/api';

export const handlers = [
  // ─────────── Auth ───────────
  http.post(`${API}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string };
    if (body.username === 'admin' && body.password === 'goodpass') {
      return HttpResponse.json({ ok: true, username: 'admin' });
    }
    return HttpResponse.json({ detail: 'Неверный логин или пароль' }, { status: 401 });
  }),

  http.post(`${API}/auth/logout`, () => HttpResponse.json({ ok: true })),

  http.get(`${API}/auth/me`, () =>
    HttpResponse.json({ id: 1, username: 'admin' }),
  ),

  // ─────────── Users (для UserPicker) ───────────
  http.get(`${API}/users`, ({ request }) => {
    const q = new URL(request.url).searchParams.get('q') ?? '';
    const all = [
      { id: 1, telegram_user_id: 111, username: 'alice', first_name: 'Alice', last_name: null,
        language_code: 'en', phone: null, email: null, notes: null,
        first_seen_at: '2026-05-01T10:00:00Z', last_seen_at: '2026-05-22T10:00:00Z' },
      { id: 2, telegram_user_id: 222, username: 'bob', first_name: 'Bob', last_name: null,
        language_code: 'en', phone: null, email: null, notes: null,
        first_seen_at: '2026-05-02T10:00:00Z', last_seen_at: '2026-05-22T10:00:00Z' },
    ];
    const filter = q.toLowerCase().replace(/^@/, '');
    const items = !filter
      ? all
      : all.filter((u) => (u.first_name + u.username).toLowerCase().includes(filter));
    return HttpResponse.json({ total: items.length, items });
  }),

  // ─────────── Products ───────────
  http.get(`${API}/products`, () =>
    HttpResponse.json([
      {
        id: 1, code: 'p1', name: 'Product 1', description: null, cover_url: null,
        channel_id: 1, channel_title: 'Channel A',
        price_3m: '1000', price_6m: '1800', price_12m: '3000',
        currency: 'RUB', is_active: true, created_at: '2026-05-01T00:00:00Z',
      },
    ]),
  ),

  // ─────────── Tracking links ───────────
  http.get(`${API}/tracking-links`, () => HttpResponse.json([])),

  http.post(`${API}/tracking-links`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: 99,
        slug: 'newslug1',
        url: 'https://t.me/bot?start=newslug1',
        product: { id: body.product_id, code: 'p1', name: 'Product 1' },
        bot: { id: 1, username: 'bot' },
        utm_source: body.utm_source,
        utm_medium: body.utm_medium ?? null,
        utm_campaign: body.utm_campaign ?? null,
        utm_content: null,
        notes: null,
        is_active: true,
        click_count: 0,
        unique_users: 0,
        leads_count: 0,
        payments_count: 0,
        revenue: '0',
        created_at: '2026-05-22T12:00:00Z',
      },
      { status: 201 },
    );
  }),

  // ─────────── Stats ───────────
  http.get(`${API}/stats/sources`, () =>
    HttpResponse.json({
      from: '2026-04-22T00:00:00Z',
      to: '2026-05-22T00:00:00Z',
      group_by: 'source',
      rows: [
        { source: 'instagram', clicks: 100, unique_users: 80, leads: 20, payments: 5,
          revenue: '5000', conv_click_to_lead: 0.2, conv_lead_to_payment: 0.25, avg_check: 1000 },
      ],
      totals: { clicks: 100, unique_users: 80, leads: 20, payments: 5, revenue: '5000' },
    }),
  ),

  http.get(`${API}/stats/overview`, () =>
    HttpResponse.json({
      users: { total: 3, new_7d: 1 },
      leads: { total: 2, new: 2, last_24h: 0 },
      subscriptions: { active: 1, expiring_7d: 0 },
      revenue: { total: '120000', last_30d: '120000', payments_30d: 1 },
      catalog: { products: 2, channels: 2, active_bots: 1 },
      recent_leads: [],
      recent_payments: [],
    }),
  ),
];

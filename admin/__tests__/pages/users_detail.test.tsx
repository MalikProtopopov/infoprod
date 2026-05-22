/**
 * @vitest-environment happy-dom
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Suspense } from 'react';
import { describe, expect, it } from 'vitest';
import { SWRConfig } from 'swr';

import UserPage from '@/app/(dash)/users/[id]/page';
import { server } from '../mocks/server';

async function renderFresh(ui: React.ReactNode) {
  const r = render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <Suspense fallback={<div>loading</div>}>{ui}</Suspense>
    </SWRConfig>,
  );
  await waitFor(() => expect(screen.queryByText('loading')).not.toBeInTheDocument());
  return r;
}

function params(id = '1') {
  const value = { id };
  const p = Promise.resolve(value);
  Object.assign(p, { status: 'fulfilled', value });
  return p as Promise<{ id: string }>;
}

const card = {
  user: {
    id: 1, telegram_user_id: 100, username: 'alice',
    first_name: 'Alice', last_name: 'Aaa',
    phone: '+7-911-111-22-33', email: 'a@b.com', notes: 'VIP',
    first_seen_at: new Date('2026-01-01').toISOString(),
    last_seen_at: new Date('2026-05-01').toISOString(),
  },
  leads: [
    {
      id: 11, product_name: 'YogaPro', channel_title: 'Yoga Channel',
      status: 'paid', created_at: new Date().toISOString(),
    },
  ],
  payments: [
    {
      id: 21, product_name: 'YogaPro', channel_title: 'Yoga Channel',
      period_months: 3, amount: '1500.00', currency: 'RUB',
      created_at: new Date().toISOString(),
    },
  ],
  subscriptions: [
    {
      id: 31, channel_id: 1, channel_title: 'Yoga Channel',
      product_id: 1, product_name: 'YogaPro',
      starts_at: new Date().toISOString(),
      ends_at: new Date(Date.now() + 30 * 86400e3).toISOString(),
      status: 'active', invite_link: 'https://t.me/+abc',
    },
  ],
};

describe('UserPage (detail)', () => {
  it('renders user name and contacts', async () => {
    server.use(http.get('/api/users/1', () => HttpResponse.json(card)));
    await renderFresh(<UserPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText('Alice Aaa')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('+7-911-111-22-33')).toBeInTheDocument();
    expect(screen.getByDisplayValue('a@b.com')).toBeInTheDocument();
  });

  it('renders leads, payments, subscriptions', async () => {
    server.use(http.get('/api/users/1', () => HttpResponse.json(card)));
    await renderFresh(<UserPage params={params()} />);
    await waitFor(() => screen.getByText('Alice Aaa'));
    expect(screen.getAllByText('YogaPro').length).toBeGreaterThan(0);
    expect(screen.getByText(/1\s*500/)).toBeInTheDocument();
    // Status может выводиться как русский pill "оплачена" или raw "paid"
    expect(
      screen.queryByText('paid') || screen.queryByText('оплачена'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/active/) || screen.queryByText(/активн/i),
    ).toBeInTheDocument();
  });

  it('patches user fields via PATCH', async () => {
    let patchBody: Record<string, unknown> | null = null;
    server.use(
      http.get('/api/users/1', () => HttpResponse.json(card)),
      http.patch('/api/users/1', async ({ request }) => {
        patchBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    await renderFresh(<UserPage params={params()} />);
    await waitFor(() => screen.getByText('Alice Aaa'));
    const notes = screen.getByDisplayValue('VIP');
    await user.clear(notes);
    await user.type(notes, 'CHANGED');
    await user.click(screen.getByRole('button', { name: /Сохранить/i }));
    await waitFor(() => expect(patchBody).toMatchObject({ notes: 'CHANGED' }));
  });

  it('shows fallback name when no first_name', async () => {
    server.use(
      http.get('/api/users/1', () =>
        HttpResponse.json({
          ...card,
          user: { ...card.user, first_name: null, last_name: null, username: null },
        }),
      ),
    );
    await renderFresh(<UserPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText(/Пользователь #1/)).toBeInTheDocument();
    });
  });

  it('shows Empty when no history', async () => {
    server.use(
      http.get('/api/users/1', () =>
        HttpResponse.json({ ...card, leads: [], payments: [], subscriptions: [] }),
      ),
    );
    await renderFresh(<UserPage params={params()} />);
    await waitFor(() => screen.getByText('Alice Aaa'));
    // Хотя бы одно слово "ещё" / "Нет" встречается
    expect(screen.getAllByText(/нет|пусто|—/i).length).toBeGreaterThan(0);
  });
});

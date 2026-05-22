/**
 * @vitest-environment happy-dom
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Suspense } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import LeadPage from '@/app/(dash)/leads/[id]/page';
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

const lead = {
  id: 1, status: 'new', created_at: new Date().toISOString(),
  user_id: 100, user_telegram_id: 999, user_username: 'alice',
  user_first_name: 'Alice', user_last_name: 'A',
  user_language: 'ru', user_phone: null, user_email: null, user_notes: null,
  product_id: 5, product_code: 'yoga', product_name: 'YogaPro',
  product_description: 'desc', product_currency: 'RUB',
  product_price_3m: '1000.00', product_price_6m: '1800.00', product_price_12m: '3000.00',
  channel_id: 7, channel_title: 'Yoga Channel',
};

describe('LeadPage (detail)', () => {
  it('renders lead header and user', async () => {
    server.use(http.get('/api/leads/1', () => HttpResponse.json(lead)));
    await renderFresh(<LeadPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText(/Заявка #1/)).toBeInTheDocument();
      // Имя пользователя выводится в нескольких местах — ищем хотя бы одно
      expect(screen.getAllByText(/Alice A/).length).toBeGreaterThan(0);
    });
  });

  it('changes status via PATCH', async () => {
    let patchBody: Record<string, unknown> | null = null;
    server.use(
      http.get('/api/leads/1', () => HttpResponse.json(lead)),
      http.patch('/api/leads/1', async ({ request }) => {
        patchBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    await renderFresh(<LeadPage params={params()} />);
    await waitFor(() => screen.getByText(/Заявка #1/));
    const select = screen.getByDisplayValue('новая') as HTMLSelectElement;
    await user.selectOptions(select, 'contacted');
    await waitFor(() => expect(patchBody).toEqual({ status: 'contacted' }));
  });

  it('renders product info: code, channel, prices', async () => {
    server.use(http.get('/api/leads/1', () => HttpResponse.json(lead)));
    await renderFresh(<LeadPage params={params()} />);
    await waitFor(() => screen.getByText(/Заявка #1/));
    expect(screen.getByText('yoga')).toBeInTheDocument();
    expect(screen.getByText('Yoga Channel')).toBeInTheDocument();
    expect(screen.getAllByText('YogaPro').length).toBeGreaterThan(0);
  });

  it('renders new-status pill', async () => {
    server.use(http.get('/api/leads/1', () => HttpResponse.json(lead)));
    await renderFresh(<LeadPage params={params()} />);
    await waitFor(() => screen.getByText(/Заявка #1/));
    expect(screen.getAllByText('новая').length).toBeGreaterThan(0);
  });

  it('renders paid-status differently', async () => {
    server.use(http.get('/api/leads/1', () => HttpResponse.json({ ...lead, status: 'paid' })));
    await renderFresh(<LeadPage params={params()} />);
    await waitFor(() => screen.getByText(/Заявка #1/));
    expect(screen.getAllByText('оплачена').length).toBeGreaterThan(0);
  });

  it('deletes lead when user confirms', async () => {
    let deleted = false;
    server.use(
      http.get('/api/leads/1', () => HttpResponse.json(lead)),
      http.delete('/api/leads/1', () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    await renderFresh(<LeadPage params={params()} />);
    await waitFor(() => screen.getByText(/Заявка #1/));
    try {
      await user.click(screen.getByRole('button', { name: 'Удалить' }));
    } catch {
      // window.location.href = '/leads' может бросать в jsdom — игнорируем
    }
    await waitFor(() => expect(deleted).toBe(true));
    vi.unstubAllGlobals();
  });
});

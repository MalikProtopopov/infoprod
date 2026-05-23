/**
 * @vitest-environment happy-dom
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Suspense } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import EditPage from '@/app/(dash)/funnels/[id]/edit/page';
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

function params() {
  const value = { id: '1' };
  const p = Promise.resolve(value);
  Object.assign(p, { status: 'fulfilled', value });
  return p as Promise<{ id: string }>;
}

const funnel = {
  id: 1, name: 'My funnel', description: 'desc',
  product_id: 1, bot_id: null, is_active: true,
  ttl_days: 7, cancel_on_payment: true,
  steps_count: 2, active_entries: 5, completed_entries: 0,
  steps: [
    {
      id: 11, funnel_id: 1, order_idx: 0, delay_minutes: 0,
      message_text: 'Welcome!', parse_mode: 'HTML',
      lead_magnet_id: null, buttons: null, is_active: true,
    },
    {
      id: 12, funnel_id: 1, order_idx: 1, delay_minutes: 1440,
      message_text: 'Second step (day 1)', parse_mode: 'HTML',
      lead_magnet_id: null, buttons: null, is_active: true,
    },
  ],
};

describe('FunnelEditPage', () => {
  it('renders funnel name in header', async () => {
    server.use(
      http.get('/api/funnels/1', () => HttpResponse.json(funnel)),
      http.get('/api/products', () => HttpResponse.json([])),
      http.get('/api/lead-magnets', () => HttpResponse.json([])),
    );
    await renderFresh(<EditPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /My funnel/ })).toBeInTheDocument();
    });
  });

  it('renders steps list with previews', async () => {
    server.use(
      http.get('/api/funnels/1', () => HttpResponse.json(funnel)),
      http.get('/api/products', () => HttpResponse.json([])),
      http.get('/api/lead-magnets', () => HttpResponse.json([])),
    );
    await renderFresh(<EditPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText(/Welcome!/)).toBeInTheDocument();
      expect(screen.getByText(/Second step/)).toBeInTheDocument();
    });
  });

  it('shows "Шагов ещё нет" when empty', async () => {
    server.use(
      http.get('/api/funnels/1', () => HttpResponse.json({ ...funnel, steps: [] })),
      http.get('/api/products', () => HttpResponse.json([])),
      http.get('/api/lead-magnets', () => HttpResponse.json([])),
    );
    await renderFresh(<EditPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText('Шагов ещё нет')).toBeInTheDocument();
    });
  });

  it('saves meta via PATCH', async () => {
    let patched = false;
    server.use(
      http.get('/api/funnels/1', () => HttpResponse.json(funnel)),
      http.get('/api/products', () => HttpResponse.json([])),
      http.get('/api/lead-magnets', () => HttpResponse.json([])),
      http.patch('/api/funnels/1', () => {
        patched = true;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    await renderFresh(<EditPage params={params()} />);
    await waitFor(() => screen.getByDisplayValue('My funnel'));
    await user.click(screen.getByRole('button', { name: /Сохранить$/ }));
    await waitFor(() => expect(patched).toBe(true));
  });

  it('clicking step opens editor', async () => {
    server.use(
      http.get('/api/funnels/1', () => HttpResponse.json(funnel)),
      http.get('/api/products', () => HttpResponse.json([])),
      http.get('/api/lead-magnets', () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    await renderFresh(<EditPage params={params()} />);
    await waitFor(() => screen.getByText(/Welcome!/));
    await user.click(screen.getByText(/Welcome!/));
    // Должен появиться header редактора
    expect(screen.getByText(/Редактор шага/)).toBeInTheDocument();
  });

  it('deletes step when confirmed', async () => {
    let deleted = false;
    server.use(
      http.get('/api/funnels/1', () => HttpResponse.json(funnel)),
      http.get('/api/products', () => HttpResponse.json([])),
      http.get('/api/lead-magnets', () => HttpResponse.json([])),
      http.delete('/api/funnel-steps/:id', () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    await renderFresh(<EditPage params={params()} />);
    await waitFor(() => screen.getByText(/Welcome!/));
    const delBtns = screen.getAllByText('Удалить');
    await user.click(delBtns[0]);
    await waitFor(() => expect(deleted).toBe(true));
    vi.unstubAllGlobals();
  });
});

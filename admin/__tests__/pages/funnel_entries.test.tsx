/**
 * @vitest-environment happy-dom
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Suspense } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import EntriesPage from '@/app/(dash)/funnels/[id]/entries/page';
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

const entries = [
  {
    id: 1, funnel_id: 1, user_id: 100,
    user_first_name: 'Alice', user_username: 'alice',
    source: 'tracking_link', source_ref: 5,
    started_at: new Date().toISOString(),
    completed_at: null, cancelled_at: null, cancel_reason: null,
    status: 'active',
  },
  {
    id: 2, funnel_id: 1, user_id: 101,
    user_first_name: 'Bob', user_username: null,
    source: 'code_word', source_ref: 1,
    started_at: new Date().toISOString(),
    completed_at: null,
    cancelled_at: new Date().toISOString(),
    cancel_reason: 'payment_received',
    status: 'cancelled',
  },
];

describe('FunnelEntriesPage', () => {
  it('renders entries list', async () => {
    server.use(http.get('/api/funnels/1/entries', () => HttpResponse.json(entries)));
    await renderFresh(<EntriesPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
    });
  });

  it('filters by status via tab', async () => {
    let queryStatus: string | null = null;
    server.use(
      http.get('/api/funnels/1/entries', ({ request }) => {
        const url = new URL(request.url);
        queryStatus = url.searchParams.get('status');
        return HttpResponse.json(entries);
      }),
    );
    const user = userEvent.setup();
    await renderFresh(<EntriesPage params={params()} />);
    await waitFor(() => expect(queryStatus).toBe('active')); // default
    await user.click(screen.getByRole('button', { name: 'Отменено' }));
    await waitFor(() => expect(queryStatus).toBe('cancelled'));
  });

  it('shows source pills', async () => {
    server.use(http.get('/api/funnels/1/entries', () => HttpResponse.json(entries)));
    await renderFresh(<EntriesPage params={params()} />);
    await waitFor(() => screen.getByText('Alice'));
    expect(screen.getByText('Ссылка')).toBeInTheDocument();
    expect(screen.getByText('Слово')).toBeInTheDocument();
  });

  it('shows cancel button only for active entries', async () => {
    server.use(http.get('/api/funnels/1/entries', () => HttpResponse.json(entries)));
    await renderFresh(<EntriesPage params={params()} />);
    await waitFor(() => screen.getByText('Alice'));
    const cancelBtns = screen.getAllByRole('button', { name: 'Отменить' });
    // Только одна — для Alice (active)
    expect(cancelBtns).toHaveLength(1);
  });

  it('cancels entry via POST when confirmed', async () => {
    let cancelled = false;
    server.use(
      http.get('/api/funnels/1/entries', () => HttpResponse.json(entries)),
      http.post('/api/funnel-entries/:id/cancel', () => {
        cancelled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    await renderFresh(<EntriesPage params={params()} />);
    await waitFor(() => screen.getByText('Alice'));
    await user.click(screen.getByRole('button', { name: 'Отменить' }));
    await waitFor(() => expect(cancelled).toBe(true));
    vi.unstubAllGlobals();
  });

  it('shows empty when no entries', async () => {
    server.use(http.get('/api/funnels/1/entries', () => HttpResponse.json([])));
    await renderFresh(<EntriesPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText('Подписчиков пока нет')).toBeInTheDocument();
    });
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import SubscriptionsPage from '@/app/(dash)/subscriptions/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

const subs = [
  {
    id: 1, user_id: 10, user_username: 'alice', user_first_name: 'Alice',
    channel_id: 1, channel_title: 'Yoga Channel',
    product_id: 1, product_name: 'YogaPro', payment_id: 1,
    starts_at: new Date().toISOString(),
    ends_at: new Date(Date.now() + 30 * 86400e3).toISOString(),
    status: 'active', invite_link: 'https://t.me/+abc',
  },
];

describe('SubscriptionsPage', () => {
  it('renders list', async () => {
    server.use(http.get('/api/subscriptions', () => HttpResponse.json(subs)));
    renderFresh(<SubscriptionsPage />);
    await waitFor(() => {
      expect(screen.getByText('Yoga Channel')).toBeInTheDocument();
    });
  });

  it('filters by status when tab clicked', async () => {
    let lastStatus: string | null = null;
    server.use(
      http.get('/api/subscriptions', ({ request }) => {
        lastStatus = new URL(request.url).searchParams.get('status');
        return HttpResponse.json(subs);
      }),
    );
    const user = userEvent.setup();
    renderFresh(<SubscriptionsPage />);
    await waitFor(() => expect(lastStatus).toBe('active'));
    await user.click(screen.getByRole('button', { name: 'Истёкшие' }));
    await waitFor(() => expect(lastStatus).toBe('expired'));
  });

  it('revokes subscription when confirmed', async () => {
    let revoked = false;
    server.use(
      http.get('/api/subscriptions', () => HttpResponse.json(subs)),
      http.post('/api/subscriptions/:id/revoke', () => {
        revoked = true;
        return HttpResponse.json({});
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    renderFresh(<SubscriptionsPage />);
    await waitFor(() => screen.getByText('Yoga Channel'));
    const btn = screen.getByRole('button', { name: /Отозвать/i });
    await user.click(btn);
    await waitFor(() => expect(revoked).toBe(true));
    vi.unstubAllGlobals();
  });

  it('shows Empty when no subs', async () => {
    server.use(http.get('/api/subscriptions', () => HttpResponse.json([])));
    renderFresh(<SubscriptionsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Подписок нет/)).toBeInTheDocument();
    });
  });
});

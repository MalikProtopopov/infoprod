import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { SWRConfig } from 'swr';

import LeadsPage from '@/app/(dash)/leads/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

const leads = {
  total: 2,
  items: [
    {
      id: 1, status: 'new', created_at: new Date().toISOString(),
      user_id: 10, user_telegram_id: 100, user_username: 'alice',
      user_first_name: 'Alice', user_last_name: null,
      product_id: 1, product_name: 'YogaPro', channel_title: 'Yoga',
    },
    {
      id: 2, status: 'paid', created_at: new Date().toISOString(),
      user_id: 11, user_telegram_id: 200, user_username: null,
      user_first_name: 'Bob', user_last_name: null,
      product_id: 1, product_name: 'YogaPro', channel_title: 'Yoga',
    },
  ],
};

describe('LeadsPage', () => {
  it('renders tabs and lead list', async () => {
    server.use(http.get('/api/leads', () => HttpResponse.json(leads)));
    renderFresh(<LeadsPage />);
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Новые' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Связались' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Оплачены' })).toBeInTheDocument();
  });

  it('filters by status when tab clicked', async () => {
    let lastStatus: string | null = null;
    server.use(
      http.get('/api/leads', ({ request }) => {
        lastStatus = new URL(request.url).searchParams.get('status');
        return HttpResponse.json(leads);
      }),
    );
    const user = userEvent.setup();
    renderFresh(<LeadsPage />);
    await waitFor(() => expect(lastStatus).toBe('new')); // initial
    await user.click(screen.getByRole('button', { name: 'Оплачены' }));
    await waitFor(() => expect(lastStatus).toBe('paid'));
    await user.click(screen.getByRole('button', { name: 'Все' }));
    await waitFor(() => expect(lastStatus).toBe('all'));
  });

  it('shows Empty when no leads', async () => {
    server.use(http.get('/api/leads', () => HttpResponse.json({ total: 0, items: [] })));
    renderFresh(<LeadsPage />);
    await waitFor(() => {
      expect(screen.getByText('Заявок нет')).toBeInTheDocument();
    });
  });

  it('user row links to /users/[id]', async () => {
    server.use(http.get('/api/leads', () => HttpResponse.json(leads)));
    renderFresh(<LeadsPage />);
    await waitFor(() => screen.getByText('Alice'));
    const link = screen.getByText('Alice').closest('a');
    expect(link).toHaveAttribute('href', '/users/10');
  });
});

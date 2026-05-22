import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { SWRConfig } from 'swr';

import DashboardPage from '@/app/(dash)/page';
import { server } from '../mocks/server';

/** Каждый тест получает свой Map() в качестве SWR cache — изолируем. */
function renderWithFreshSWR(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      {ui}
    </SWRConfig>,
  );
}

const overview = {
  users: { total: 42, new_7d: 3 },
  leads: { total: 100, new: 5, last_24h: 2 },
  subscriptions: { active: 12, expiring_7d: 1 },
  revenue: { total: '50000.00', last_30d: '12000.00', payments_30d: 7 },
  catalog: { products: 4, channels: 2, active_bots: 1 },
  recent_leads: [
    {
      id: 1, status: 'new', created_at: new Date().toISOString(),
      user_id: 10, user_first_name: 'Alice', user_username: 'alice',
      product_name: 'YogaPro',
    },
    {
      id: 2, status: 'paid', created_at: new Date().toISOString(),
      user_id: 11, user_first_name: 'Bob', user_username: null,
      product_name: 'PilatesPlus',
    },
  ],
  recent_payments: [
    {
      id: 1, amount: '1500.00', currency: 'RUB', period_months: 3,
      created_at: new Date().toISOString(),
      user_first_name: 'Charlie', user_username: 'ch',
      product_name: 'YogaPro',
    },
  ],
};

describe('DashboardPage', () => {
  it('shows stats after data loads', async () => {
    server.use(http.get('/api/stats/overview', () => HttpResponse.json(overview)));
    renderWithFreshSWR(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText('Активные подписки')).toBeInTheDocument();
    });
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('shows hint when expiring_7d > 0', async () => {
    server.use(http.get('/api/stats/overview', () => HttpResponse.json(overview)));
    renderWithFreshSWR(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/Истекают за 7 дней: 1/)).toBeInTheDocument();
    });
  });

  it('renders recent leads with names', async () => {
    server.use(http.get('/api/stats/overview', () => HttpResponse.json(overview)));
    renderWithFreshSWR(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
    });
  });

  it('renders recent payment amount', async () => {
    server.use(http.get('/api/stats/overview', () => HttpResponse.json(overview)));
    renderWithFreshSWR(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText('Charlie')).toBeInTheDocument();
      expect(screen.getByText(/1\s*500/)).toBeInTheDocument();
    });
  });

  it('shows "Заявок пока нет" when no leads/payments', async () => {
    server.use(
      http.get('/api/stats/overview', () =>
        HttpResponse.json({
          ...overview,
          recent_leads: [],
          recent_payments: [],
        }),
      ),
    );
    renderWithFreshSWR(<DashboardPage />);
    await waitFor(() => {
      expect(screen.getByText('Заявок пока нет')).toBeInTheDocument();
    });
    expect(screen.getByText('Платежей пока нет')).toBeInTheDocument();
  });

  it('catalog cards link to /products, /channels, /bots', async () => {
    server.use(http.get('/api/stats/overview', () => HttpResponse.json(overview)));
    renderWithFreshSWR(<DashboardPage />);
    await waitFor(() => screen.getByText('Продукты'));
    expect(screen.getByText('Продукты').closest('a')).toHaveAttribute('href', '/products');
    expect(screen.getByText('Каналы').closest('a')).toHaveAttribute('href', '/channels');
    expect(screen.getByText('Активные боты').closest('a')).toHaveAttribute('href', '/bots');
  });
});

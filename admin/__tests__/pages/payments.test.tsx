import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { SWRConfig } from 'swr';

import PaymentsPage from '@/app/(dash)/payments/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

const payments = [
  {
    id: 1, user_id: 10, user_username: 'alice', user_first_name: 'Alice',
    product_id: 1, product_name: 'YogaPro', period_months: 3,
    amount: '1500.00', currency: 'RUB', comment: null,
    created_at: new Date().toISOString(),
  },
];

const products = [
  {
    id: 1, name: 'YogaPro', price_3m: '1000.00', price_6m: '1800.00',
    price_12m: '3000.00', currency: 'RUB',
  },
];

describe('PaymentsPage', () => {
  it('renders list', async () => {
    server.use(
      http.get('/api/payments', () => HttpResponse.json(payments)),
      http.get('/api/products', () => HttpResponse.json(products)),
    );
    renderFresh(<PaymentsPage />);
    await waitFor(() => {
      expect(screen.getByText(/1\s*500/)).toBeInTheDocument();
    });
  });

  it('shows Empty when no payments', async () => {
    server.use(
      http.get('/api/payments', () => HttpResponse.json([])),
      http.get('/api/products', () => HttpResponse.json(products)),
    );
    renderFresh(<PaymentsPage />);
    await waitFor(() => {
      expect(screen.getByText(/нет/i)).toBeInTheDocument();
    });
  });

  it('opens add-payment sheet', async () => {
    server.use(
      http.get('/api/payments', () => HttpResponse.json([])),
      http.get('/api/products', () => HttpResponse.json(products)),
    );
    const user = userEvent.setup();
    renderFresh(<PaymentsPage />);
    await waitFor(() => screen.getByRole('button', { name: /Добавить/i }));
    await user.click(screen.getByRole('button', { name: /Добавить/i }));
    // Должны быть видны поля
    expect(screen.getByText('Пользователь')).toBeInTheDocument();
  });
});

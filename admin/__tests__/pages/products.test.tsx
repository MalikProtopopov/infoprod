import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { SWRConfig } from 'swr';

import ProductsPage from '@/app/(dash)/products/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

const products = [
  {
    id: 1, code: 'yoga', name: 'Yoga Pro', is_active: true,
    channel_id: 1, channel_title: 'Yoga Channel', channel_username: 'yoga_ch',
    bot_id: 1, bot_username: 'mybot',
    price_3m: '1000.00', price_6m: '1800.00', price_12m: '3000.00', currency: 'RUB',
    cover_url: null, created_at: new Date().toISOString(),
  },
];

describe('ProductsPage', () => {
  it('renders products grid', async () => {
    server.use(
      http.get('/api/products', () => HttpResponse.json(products)),
      http.get('/api/channels', () => HttpResponse.json([])),
    );
    renderFresh(<ProductsPage />);
    await waitFor(() => {
      expect(screen.getByText('Yoga Pro')).toBeInTheDocument();
    });
  });

  it('shows Empty when no products', async () => {
    server.use(
      http.get('/api/products', () => HttpResponse.json([])),
      http.get('/api/channels', () => HttpResponse.json([])),
    );
    renderFresh(<ProductsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Продуктов пока нет/i)).toBeInTheDocument();
    });
  });

  it('renders price columns', async () => {
    server.use(
      http.get('/api/products', () => HttpResponse.json(products)),
      http.get('/api/channels', () => HttpResponse.json([])),
    );
    renderFresh(<ProductsPage />);
    await waitFor(() => screen.getByText('Yoga Pro'));
    expect(screen.getByText(/1\s*000/)).toBeInTheDocument();
    expect(screen.getByText(/1\s*800/)).toBeInTheDocument();
    expect(screen.getByText(/3\s*000/)).toBeInTheDocument();
  });

  it('"Ссылки" button links to /products/[id]', async () => {
    server.use(
      http.get('/api/products', () => HttpResponse.json(products)),
      http.get('/api/channels', () => HttpResponse.json([])),
    );
    renderFresh(<ProductsPage />);
    await waitFor(() => screen.getByText('Yoga Pro'));
    const link = screen.getByRole('button', { name: 'Ссылки' }).closest('a');
    expect(link).toHaveAttribute('href', '/products/1');
  });
});

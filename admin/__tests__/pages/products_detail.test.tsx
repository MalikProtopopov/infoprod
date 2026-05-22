/**
 * @vitest-environment happy-dom
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { Suspense } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import ProductDetailPage from '@/app/(dash)/products/[id]/page';
import { server } from '../mocks/server';

async function renderFresh(ui: React.ReactNode) {
  const result = render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <Suspense fallback={<div>page-loading</div>}>{ui}</Suspense>
    </SWRConfig>,
  );
  // дать React'у размотать Suspense вокруг use(Promise)
  await waitFor(() => {
    expect(screen.queryByText('page-loading')).not.toBeInTheDocument();
  });
  return result;
}

const product = {
  id: 1, code: 'yoga', name: 'Yoga Pro', description: 'desc',
  cover_url: null, channel_id: 1, channel_title: 'Yoga Channel',
  price_3m: '1000.00', price_6m: '1800.00', price_12m: '3000.00',
  currency: 'RUB', is_active: true,
};

const bots = [{ id: 1, telegram_bot_id: 1, username: 'mybot', is_active: true,
  title: 'b', created_at: '2026-01-01', token_mask: 'x', channels_count: 0, products_count: 0 }];

const link1 = {
  id: 11, slug: 'igreels1', url: 'https://t.me/mybot?start=igreels1',
  product: { id: 1, code: 'yoga', name: 'Yoga Pro' },
  bot: { id: 1, username: 'mybot' },
  utm_source: 'instagram', utm_medium: 'reels', utm_campaign: 'spring',
  utm_content: null, notes: null, is_active: true,
  click_count: 42, unique_users: 30, leads_count: 5, payments_count: 2,
  revenue: '2000', created_at: new Date().toISOString(),
};

/** React 19 use() требует thenable с .status='fulfilled' для синхронного returna. */
function params(): Promise<{ id: string }> {
  const value = { id: '1' };
  const p = Promise.resolve(value);
  Object.assign(p, { status: 'fulfilled', value });
  return p;
}

describe('ProductDetailPage', () => {
  it('shows loading then product', async () => {
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText('Yoga Pro')).toBeInTheDocument();
    });
  });

  it('shows direct link with bot username and code', async () => {
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => {
      const input = screen.getByDisplayValue('https://t.me/mybot?start=yoga') as HTMLInputElement;
      expect(input).toBeInTheDocument();
    });
  });

  it('shows tracking links table', async () => {
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([link1])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText('igreels1')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();   // clicks
      expect(screen.getByText('30')).toBeInTheDocument();   // unique
      expect(screen.getByText('spring')).toBeInTheDocument();
    });
  });

  it('shows Empty when no links', async () => {
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => {
      expect(screen.getByText('Ссылок ещё нет')).toBeInTheDocument();
    });
  });

  it.skip('copies direct URL via Clipboard API (clipboard not available in happy-dom)', async () => {
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(global.navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    const user = userEvent.setup();
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => screen.getByText('Yoga Pro'));
    const copyBtns = screen.getAllByRole('button', { name: 'Скопировать' });
    await user.click(copyBtns[0]);
    await waitFor(() => {
      // Либо writeText звался, либо был fallback "Не получилось скопировать"
      const called = writeText.mock.calls.length > 0;
      const fallback = screen.queryByText(/Не получилось/);
      expect(called || !!fallback).toBe(true);
    });
  });

  it('opens create-link sheet on button click', async () => {
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    const user = userEvent.setup();
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => screen.getByText('Yoga Pro'));
    await user.click(screen.getByRole('button', { name: /Создать ссылку/i }));
    expect(screen.getByPlaceholderText('instagram')).toBeInTheDocument();
  });

  it('creates a tracking link via POST', async () => {
    let postBody: Record<string, unknown> | null = null;
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.post('/api/tracking-links', async ({ request }) => {
        postBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...link1, slug: 'newslug1' }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => screen.getByText('Yoga Pro'));
    await user.click(screen.getByRole('button', { name: /Создать ссылку/i }));
    await user.type(screen.getByPlaceholderText('instagram'), 'youtube');
    await user.click(screen.getByRole('button', { name: /Сгенерировать/i }));
    await waitFor(() => expect(postBody).toMatchObject({
      product_id: 1, utm_source: 'youtube',
    }));
    // После успеха показываем «успех» окно с ссылкой
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Скопировать ссылку/i })).toBeInTheDocument(),
    );
  });

  it('shows error when POST returns 409', async () => {
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.post('/api/tracking-links', () =>
        HttpResponse.json({ detail: 'Slug already taken' }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => screen.getByText('Yoga Pro'));
    await user.click(screen.getByRole('button', { name: /Создать ссылку/i }));
    await user.type(screen.getByPlaceholderText('instagram'), 'x');
    await user.click(screen.getByRole('button', { name: /Сгенерировать/i }));
    await waitFor(() => {
      expect(screen.getByText(/Slug already taken/)).toBeInTheDocument();
    });
  });

  it('deactivates link via DELETE when confirmed', async () => {
    let deleted = false;
    server.use(
      http.get('/api/products/1', () => HttpResponse.json(product)),
      http.get('/api/tracking-links', () => HttpResponse.json([link1])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.delete('/api/tracking-links/:id', () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    await renderFresh(<ProductDetailPage params={params()} />);
    await waitFor(() => screen.getByText('igreels1'));
    await user.click(screen.getByRole('button', { name: 'Деакт.' }));
    await waitFor(() => expect(deleted).toBe(true));
    vi.unstubAllGlobals();
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import LeadMagnetsPage from '@/app/(dash)/lead-magnets/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

const magnets = [
  {
    id: 1, name: 'PDF Guide', description: 'Утренний уход',
    file_type: 'pdf', file_size: 102400, product_id: 1,
    is_active: true, download_count: 42, has_telegram_file_id: true,
    created_at: new Date().toISOString(),
  },
  {
    id: 2, name: 'Video', description: null,
    file_type: 'video', file_size: 5120000, product_id: null,
    is_active: false, download_count: 0, has_telegram_file_id: false,
    created_at: new Date().toISOString(),
  },
];

const products = [{ id: 1, name: 'Клуб' }];

describe('LeadMagnetsPage', () => {
  it('renders list', async () => {
    server.use(
      http.get('/api/lead-magnets', () => HttpResponse.json(magnets)),
      http.get('/api/products', () => HttpResponse.json(products)),
    );
    renderFresh(<LeadMagnetsPage />);
    await waitFor(() => {
      expect(screen.getByText('PDF Guide')).toBeInTheDocument();
      expect(screen.getByText('Video')).toBeInTheDocument();
    });
  });

  it('shows download count and file size', async () => {
    server.use(
      http.get('/api/lead-magnets', () => HttpResponse.json(magnets)),
      http.get('/api/products', () => HttpResponse.json(products)),
    );
    renderFresh(<LeadMagnetsPage />);
    await waitFor(() => screen.getByText('PDF Guide'));
    expect(screen.getByText('42')).toBeInTheDocument();
    // 102400 bytes = 100.0 KB
    expect(screen.getByText(/100/)).toBeInTheDocument();
  });

  it('shows "универсальный" for product_id=null', async () => {
    server.use(
      http.get('/api/lead-magnets', () => HttpResponse.json(magnets)),
      http.get('/api/products', () => HttpResponse.json(products)),
    );
    renderFresh(<LeadMagnetsPage />);
    await waitFor(() => screen.getByText('PDF Guide'));
    expect(screen.getByText('универсальный')).toBeInTheDocument();
  });

  it('shows Empty when no magnets', async () => {
    server.use(
      http.get('/api/lead-magnets', () => HttpResponse.json([])),
      http.get('/api/products', () => HttpResponse.json([])),
    );
    renderFresh(<LeadMagnetsPage />);
    await waitFor(() => {
      expect(screen.getByText('Лидмагнитов пока нет')).toBeInTheDocument();
    });
  });

  it('opens upload sheet on button', async () => {
    server.use(
      http.get('/api/lead-magnets', () => HttpResponse.json([])),
      http.get('/api/products', () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    renderFresh(<LeadMagnetsPage />);
    await waitFor(() => screen.getByText('Лидмагнитов пока нет'));
    await user.click(screen.getByRole('button', { name: /Загрузить файл/i }));
    expect(screen.getByText(/Перетащите файл сюда или кликните/)).toBeInTheDocument();
  });

  it('toggles is_active via PATCH', async () => {
    let patched = false;
    server.use(
      http.get('/api/lead-magnets', () => HttpResponse.json(magnets)),
      http.get('/api/products', () => HttpResponse.json(products)),
      http.patch('/api/lead-magnets/:id', () => {
        patched = true;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    renderFresh(<LeadMagnetsPage />);
    await waitFor(() => screen.getByText('PDF Guide'));
    const toggle = screen.getAllByRole('button', { name: /Выключить|Включить/i })[0];
    await user.click(toggle);
    await waitFor(() => expect(patched).toBe(true));
  });

  it('deletes magnet when confirmed', async () => {
    let deleted = false;
    server.use(
      http.get('/api/lead-magnets', () => HttpResponse.json(magnets)),
      http.get('/api/products', () => HttpResponse.json(products)),
      http.delete('/api/lead-magnets/:id', () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    renderFresh(<LeadMagnetsPage />);
    await waitFor(() => screen.getByText('PDF Guide'));
    const dels = screen.getAllByRole('button', { name: 'Удалить' });
    await user.click(dels[0]);
    await waitFor(() => expect(deleted).toBe(true));
    vi.unstubAllGlobals();
  });

  it('shows tg-cache status pill', async () => {
    server.use(
      http.get('/api/lead-magnets', () => HttpResponse.json(magnets)),
      http.get('/api/products', () => HttpResponse.json(products)),
    );
    renderFresh(<LeadMagnetsPage />);
    await waitFor(() => screen.getByText('PDF Guide'));
    expect(screen.getByText('кеш')).toBeInTheDocument();
  });
});

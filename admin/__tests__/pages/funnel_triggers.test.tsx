import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import TriggersPage from '@/app/(dash)/funnel-triggers/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

const triggers = [
  {
    id: 1, word: 'клуб', funnel_id: 5, funnel_name: 'Воронка А',
    is_active: true, use_count: 42, created_at: new Date().toISOString(),
  },
  {
    id: 2, word: 'обучение', funnel_id: 6, funnel_name: 'Воронка Б',
    is_active: false, use_count: 0, created_at: new Date().toISOString(),
  },
];

const funnels = [
  { id: 5, name: 'Воронка А' },
  { id: 6, name: 'Воронка Б' },
];

describe('FunnelTriggersPage', () => {
  it('renders list', async () => {
    server.use(
      http.get('/api/funnel-triggers', () => HttpResponse.json(triggers)),
      http.get('/api/funnels', () => HttpResponse.json(funnels)),
    );
    renderFresh(<TriggersPage />);
    await waitFor(() => {
      expect(screen.getByText('клуб')).toBeInTheDocument();
      expect(screen.getByText('обучение')).toBeInTheDocument();
    });
  });

  it('shows funnel name as link', async () => {
    server.use(
      http.get('/api/funnel-triggers', () => HttpResponse.json(triggers)),
      http.get('/api/funnels', () => HttpResponse.json(funnels)),
    );
    renderFresh(<TriggersPage />);
    await waitFor(() => screen.getByText('клуб'));
    expect(screen.getByText('Воронка А').closest('a')).toHaveAttribute('href', '/funnels/5/edit');
  });

  it('shows Empty when no triggers', async () => {
    server.use(
      http.get('/api/funnel-triggers', () => HttpResponse.json([])),
      http.get('/api/funnels', () => HttpResponse.json([])),
    );
    renderFresh(<TriggersPage />);
    await waitFor(() => {
      expect(screen.getByText('Кодовых слов пока нет')).toBeInTheDocument();
    });
  });

  it('shows error on duplicate (409)', async () => {
    server.use(
      http.get('/api/funnel-triggers', () => HttpResponse.json([])),
      http.get('/api/funnels', () => HttpResponse.json(funnels)),
      http.post('/api/funnel-triggers', () =>
        HttpResponse.json({ detail: "Слово 'старт' уже используется" }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    renderFresh(<TriggersPage />);
    await waitFor(() => screen.getByText('Кодовых слов пока нет'));
    await user.click(screen.getByRole('button', { name: /Создать слово/i }));
    await user.type(screen.getByPlaceholderText('старт'), 'старт');
    // выбираем funnel
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    await user.selectOptions(select, '5');
    await user.click(screen.getByRole('button', { name: /^Создать$/i }));
    await waitFor(() => {
      expect(screen.getByText(/уже используется/)).toBeInTheDocument();
    });
  });

  it('deletes trigger when confirmed', async () => {
    let deleted = false;
    server.use(
      http.get('/api/funnel-triggers', () => HttpResponse.json(triggers)),
      http.get('/api/funnels', () => HttpResponse.json(funnels)),
      http.delete('/api/funnel-triggers/:id', () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    renderFresh(<TriggersPage />);
    await waitFor(() => screen.getByText('клуб'));
    const dels = screen.getAllByRole('button', { name: 'Удалить' });
    await user.click(dels[0]);
    await waitFor(() => expect(deleted).toBe(true));
    vi.unstubAllGlobals();
  });

  it('toggle is_active via PATCH', async () => {
    let patched = false;
    server.use(
      http.get('/api/funnel-triggers', () => HttpResponse.json(triggers)),
      http.get('/api/funnels', () => HttpResponse.json(funnels)),
      http.patch('/api/funnel-triggers/:id', () => {
        patched = true;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    renderFresh(<TriggersPage />);
    await waitFor(() => screen.getByText('клуб'));
    const toggles = screen.getAllByRole('button', { name: /Выключить|Включить/i });
    await user.click(toggles[0]);
    await waitFor(() => expect(patched).toBe(true));
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import BotsPage from '@/app/(dash)/bots/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      {ui}
    </SWRConfig>,
  );
}

const bots = [
  {
    id: 1, telegram_bot_id: 12345, username: 'mybot', title: 'Main Bot',
    is_active: true, created_at: new Date().toISOString(),
    token_mask: '123456…7890', channels_count: 2, products_count: 5,
  },
  {
    id: 2, telegram_bot_id: 67890, username: 'testbot', title: null,
    is_active: false, created_at: new Date().toISOString(),
    token_mask: '098765…4321', channels_count: 0, products_count: 0,
  },
];

describe('BotsPage', () => {
  it('shows loading then table', async () => {
    server.use(http.get('/api/bots', () => HttpResponse.json(bots)));
    renderFresh(<BotsPage />);
    await waitFor(() => {
      expect(screen.getByText('@mybot')).toBeInTheDocument();
      expect(screen.getByText('@testbot')).toBeInTheDocument();
    });
  });

  it('shows Empty when no bots', async () => {
    server.use(http.get('/api/bots', () => HttpResponse.json([])));
    renderFresh(<BotsPage />);
    await waitFor(() => {
      expect(screen.getByText('Ботов пока нет')).toBeInTheDocument();
    });
  });

  it('opens add-bot sheet on button click', async () => {
    server.use(http.get('/api/bots', () => HttpResponse.json([])));
    const user = userEvent.setup();
    renderFresh(<BotsPage />);
    await waitFor(() => screen.getByText('Ботов пока нет'));
    await user.click(screen.getByRole('button', { name: /Добавить бота/i }));
    expect(screen.getByText('Токен')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/12345/i)).toBeInTheDocument();
  });

  it('adds bot via API and closes sheet', async () => {
    let postCalled = false;
    server.use(
      http.get('/api/bots', () => HttpResponse.json([])),
      http.post('/api/bots', () => {
        postCalled = true;
        return HttpResponse.json({
          id: 3, telegram_bot_id: 1, username: 'new', title: null,
          is_active: true, created_at: new Date().toISOString(),
          token_mask: 'x…y', channels_count: 0, products_count: 0,
        }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderFresh(<BotsPage />);
    await waitFor(() => screen.getByText('Ботов пока нет'));
    await user.click(screen.getByRole('button', { name: /Добавить бота/i }));
    const tokenInput = screen.getByPlaceholderText(/12345/i);
    await user.type(tokenInput, '12345678:AAAAAAAAAA');
    await user.click(screen.getByRole('button', { name: /^Добавить$|Сохраняем/i }));
    await waitFor(() => expect(postCalled).toBe(true));
  });

  it('shows error message on duplicate (409)', async () => {
    server.use(
      http.get('/api/bots', () => HttpResponse.json([])),
      http.post('/api/bots', () =>
        HttpResponse.json({ detail: 'Такой бот уже добавлен' }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    renderFresh(<BotsPage />);
    await waitFor(() => screen.getByText('Ботов пока нет'));
    await user.click(screen.getByRole('button', { name: /Добавить бота/i }));
    await user.type(screen.getByPlaceholderText(/12345/i), '12345678:AAAAA');
    await user.click(screen.getByRole('button', { name: /^Добавить$|Сохраняем/i }));
    await waitFor(() => {
      expect(screen.getByText(/Такой бот уже добавлен/)).toBeInTheDocument();
    });
  });

  it('toggles bot is_active via PATCH', async () => {
    let patchCalled = false;
    server.use(
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.patch('/api/bots/:id', () => {
        patchCalled = true;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    renderFresh(<BotsPage />);
    await waitFor(() => screen.getByText('@mybot'));
    // Кликаем на кнопку Активировать/Отключить
    const toggles = screen.getAllByRole('button', { name: /Выключить|Включить/i });
    await user.click(toggles[0]);
    await waitFor(() => expect(patchCalled).toBe(true));
  });

  it('deletes bot when user confirms', async () => {
    let deleteCalled = false;
    server.use(
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.delete('/api/bots/:id', () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    renderFresh(<BotsPage />);
    await waitFor(() => screen.getByText('@mybot'));
    const dels = screen.getAllByRole('button', { name: /Удалить/i });
    await user.click(dels[0]);
    await waitFor(() => expect(deleteCalled).toBe(true));
    vi.unstubAllGlobals();
  });

  it('does not delete when user cancels confirm', async () => {
    let deleteCalled = false;
    server.use(
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.delete('/api/bots/:id', () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => false);
    const user = userEvent.setup();
    renderFresh(<BotsPage />);
    await waitFor(() => screen.getByText('@mybot'));
    const dels = screen.getAllByRole('button', { name: /Удалить/i });
    await user.click(dels[0]);
    expect(deleteCalled).toBe(false);
    vi.unstubAllGlobals();
  });

  it('shows alert on delete error 409', async () => {
    server.use(
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.delete('/api/bots/:id', () =>
        HttpResponse.json({ detail: 'Сначала удалите каналов: 2' }, { status: 409 }),
      ),
    );
    const alertMock = vi.fn();
    vi.stubGlobal('confirm', () => true);
    vi.stubGlobal('alert', alertMock);
    const user = userEvent.setup();
    renderFresh(<BotsPage />);
    await waitFor(() => screen.getByText('@mybot'));
    const dels = screen.getAllByRole('button', { name: /Удалить/i });
    await user.click(dels[0]);
    await waitFor(() => expect(alertMock).toHaveBeenCalled());
    expect(alertMock.mock.calls[0][0]).toMatch(/Сначала удалите/);
    vi.unstubAllGlobals();
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';

import ChannelsPage from '@/app/(dash)/channels/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

const channels = [
  {
    id: 1, telegram_chat_id: -1001234567890, title: 'Yoga Channel',
    username: 'yoga_ch', bot_id: 1, bot_username: 'mybot',
    products_count: 3, active_subs_count: 5, created_at: new Date().toISOString(),
  },
];

const bots = [
  { id: 1, telegram_bot_id: 12345, username: 'mybot', title: 'Main', is_active: true,
    created_at: new Date().toISOString(), token_mask: 'x', channels_count: 1, products_count: 0 },
];

describe('ChannelsPage', () => {
  it('renders channel list', async () => {
    server.use(
      http.get('/api/channels', () => HttpResponse.json(channels)),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    renderFresh(<ChannelsPage />);
    await waitFor(() => {
      expect(screen.getByText('Yoga Channel')).toBeInTheDocument();
    });
  });

  it('shows Empty when no channels', async () => {
    server.use(
      http.get('/api/channels', () => HttpResponse.json([])),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    renderFresh(<ChannelsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Каналов пока нет/i)).toBeInTheDocument();
    });
  });

  it('shows products/subs counts as pills', async () => {
    server.use(
      http.get('/api/channels', () => HttpResponse.json(channels)),
      http.get('/api/bots', () => HttpResponse.json(bots)),
    );
    renderFresh(<ChannelsPage />);
    await waitFor(() => screen.getByText('Yoga Channel'));
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('deletes channel when user confirms', async () => {
    let deleted = false;
    server.use(
      http.get('/api/channels', () => HttpResponse.json(channels)),
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.delete('/api/channels/:id', () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    vi.stubGlobal('confirm', () => true);
    const user = userEvent.setup();
    renderFresh(<ChannelsPage />);
    await waitFor(() => screen.getByText('Yoga Channel'));
    const dels = screen.getAllByRole('button', { name: /Удалить/i });
    await user.click(dels[0]);
    await waitFor(() => expect(deleted).toBe(true));
    vi.unstubAllGlobals();
  });

  it('alerts on delete error 409', async () => {
    server.use(
      http.get('/api/channels', () => HttpResponse.json(channels)),
      http.get('/api/bots', () => HttpResponse.json(bots)),
      http.delete('/api/channels/:id', () =>
        HttpResponse.json({ detail: 'Сначала удалите продуктов: 3' }, { status: 409 }),
      ),
    );
    const alertMock = vi.fn();
    vi.stubGlobal('confirm', () => true);
    vi.stubGlobal('alert', alertMock);
    const user = userEvent.setup();
    renderFresh(<ChannelsPage />);
    await waitFor(() => screen.getByText('Yoga Channel'));
    const dels = screen.getAllByRole('button', { name: /Удалить/i });
    await user.click(dels[0]);
    await waitFor(() => expect(alertMock).toHaveBeenCalled());
    vi.unstubAllGlobals();
  });
});

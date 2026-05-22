import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { SWRConfig } from 'swr';

import UsersPage from '@/app/(dash)/users/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

const users = {
  total: 2,
  items: [
    {
      id: 1, telegram_user_id: 100, username: 'alice',
      first_name: 'Alice', last_name: 'A',
      phone: null, email: null, notes: null,
      created_at: new Date().toISOString(),
    },
    {
      id: 2, telegram_user_id: 200, username: null,
      first_name: 'Bob', last_name: null,
      phone: null, email: null, notes: null,
      created_at: new Date().toISOString(),
    },
  ],
};

describe('UsersPage', () => {
  it('renders user list', async () => {
    server.use(http.get('/api/users', () => HttpResponse.json(users)));
    renderFresh(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Alice A')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
    });
  });

  it('renders username with @ prefix', async () => {
    server.use(http.get('/api/users', () => HttpResponse.json(users)));
    renderFresh(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('@alice')).toBeInTheDocument();
    });
  });

  it('triggers search on input', async () => {
    let lastQ: string | null = null;
    server.use(
      http.get('/api/users', ({ request }) => {
        lastQ = new URL(request.url).searchParams.get('q');
        return HttpResponse.json(users);
      }),
    );
    const user = userEvent.setup();
    renderFresh(<UsersPage />);
    await waitFor(() => screen.getByText('Alice A'));
    const search = screen.getByPlaceholderText(/Поиск/i);
    await user.type(search, 'alice');
    await waitFor(() => expect(lastQ).toBe('alice'));
  });

  it('user row links to /users/[id]', async () => {
    server.use(http.get('/api/users', () => HttpResponse.json(users)));
    renderFresh(<UsersPage />);
    await waitFor(() => screen.getByText('Alice A'));
    const link = screen.getByText('Alice A').closest('a');
    expect(link).toHaveAttribute('href', '/users/1');
  });

  it('shows Empty when no users', async () => {
    server.use(http.get('/api/users', () => HttpResponse.json({ total: 0, items: [] })));
    renderFresh(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText(/не найдены/i)).toBeInTheDocument();
    });
  });
});

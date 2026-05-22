import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LoginPage from '@/app/login/page';
import { server } from '../mocks/server';

const pushMock = vi.fn();
const refreshMock = vi.fn();
vi.mock('next/navigation', async () => {
  const actual = (await vi.importActual('next/navigation')) as Record<string, unknown>;
  return {
    ...actual,
    useRouter: () => ({ push: pushMock, refresh: refreshMock, replace: vi.fn() }),
    usePathname: () => '/login',
    useSearchParams: () => new URLSearchParams(),
  };
});

beforeEach(() => {
  pushMock.mockClear();
  refreshMock.mockClear();
});

describe('LoginPage', () => {
  it('renders the form', () => {
    render(<LoginPage />);
    expect(screen.getByRole('heading', { name: /Вход/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Логин')).toBeInTheDocument();
    expect(screen.getByLabelText('Пароль')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Войти' })).toBeInTheDocument();
  });

  it('logs in and navigates to / on success', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByLabelText('Логин'), 'admin');
    await user.type(screen.getByLabelText('Пароль'), 'goodpass');
    await user.click(screen.getByRole('button', { name: 'Войти' }));
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith('/');
      expect(refreshMock).toHaveBeenCalled();
    });
  });

  it('shows error message on wrong password (401)', async () => {
    server.use(
      http.post('/api/auth/login', () =>
        HttpResponse.json({ detail: 'Неверный логин или пароль' }, { status: 401 }),
      ),
    );
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByLabelText('Логин'), 'admin');
    await user.type(screen.getByLabelText('Пароль'), 'badpass');
    await user.click(screen.getByRole('button', { name: 'Войти' }));
    // На 401 lib/api кидает 'Unauthorized' (т.к. мы уже на /login, редирект не выполняется)
    await waitFor(() => {
      expect(screen.getByText(/Unauthorized/i)).toBeInTheDocument();
    });
    expect(pushMock).not.toHaveBeenCalled();
  });

  it('shows error detail on non-401 error', async () => {
    server.use(
      http.post('/api/auth/login', () =>
        HttpResponse.json({ detail: 'Сервер недоступен' }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByLabelText('Логин'), 'admin');
    await user.type(screen.getByLabelText('Пароль'), 'x');
    await user.click(screen.getByRole('button', { name: 'Войти' }));
    await waitFor(() => {
      expect(screen.getByText(/Сервер недоступен/i)).toBeInTheDocument();
    });
  });

  it('disables button while submitting', async () => {
    server.use(
      http.post('/api/auth/login', async () => {
        await new Promise((r) => setTimeout(r, 100));
        return HttpResponse.json({ ok: true });
      }),
    );
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByLabelText('Логин'), 'admin');
    await user.type(screen.getByLabelText('Пароль'), 'goodpass');
    await user.click(screen.getByRole('button', { name: 'Войти' }));
    expect(screen.getByRole('button', { name: /Входим|Войти/i })).toBeDisabled();
  });
});

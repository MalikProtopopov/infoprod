import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { SWRConfig } from 'swr';

import AccountPage from '@/app/(dash)/account/page';
import { server } from '../mocks/server';

function renderFresh(ui: React.ReactNode) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>,
  );
}

/** Field в компоненте не использует htmlFor — ищем input по label-text → label.querySelector. */
function inputByLabel(label: string): HTMLInputElement {
  const lbl = screen.getByText(label).closest('label');
  if (!lbl) throw new Error(`Label not found: ${label}`);
  const inp = lbl.querySelector('input');
  if (!inp) throw new Error(`Input not found for label: ${label}`);
  return inp as HTMLInputElement;
}

describe('AccountPage', () => {
  it('renders username', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({ id: 1, username: 'admin' })));
    renderFresh(<AccountPage />);
    await waitFor(() => {
      expect(screen.getByText('admin')).toBeInTheDocument();
    });
  });

  it('shows error when passwords do not match', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({ id: 1, username: 'admin' })));
    const user = userEvent.setup();
    renderFresh(<AccountPage />);
    await waitFor(() => screen.getByText('admin'));

    await user.type(inputByLabel('Старый пароль'), 'old');
    await user.type(inputByLabel('Новый пароль'), 'newpass123');
    await user.type(inputByLabel('Повторите новый пароль'), 'different');
    await user.click(screen.getByRole('button', { name: /Сменить пароль/i }));
    await waitFor(() => {
      expect(screen.getByText(/не совпадают/i)).toBeInTheDocument();
    });
  });

  it('shows error when new password too short', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({ id: 1, username: 'admin' })));
    const user = userEvent.setup();
    renderFresh(<AccountPage />);
    await waitFor(() => screen.getByText('admin'));

    await user.type(inputByLabel('Старый пароль'), 'old');
    await user.type(inputByLabel('Новый пароль'), 'abc');
    await user.type(inputByLabel('Повторите новый пароль'), 'abc');
    await user.click(screen.getByRole('button', { name: /Сменить пароль/i }));
    await waitFor(() => {
      expect(screen.getByText(/не короче 6/i)).toBeInTheDocument();
    });
  });

  it('changes password successfully via API', async () => {
    let postBody: Record<string, unknown> | null = null;
    server.use(
      http.get('/api/auth/me', () => HttpResponse.json({ id: 1, username: 'admin' })),
      http.post('/api/admin/password', async ({ request }) => {
        postBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ok: true });
      }),
    );
    const user = userEvent.setup();
    renderFresh(<AccountPage />);
    await waitFor(() => screen.getByText('admin'));

    await user.type(inputByLabel('Старый пароль'), 'oldpw');
    await user.type(inputByLabel('Новый пароль'), 'newpass123');
    await user.type(inputByLabel('Повторите новый пароль'), 'newpass123');
    await user.click(screen.getByRole('button', { name: /Сменить пароль/i }));
    await waitFor(() => {
      expect(postBody).toEqual({ old_password: 'oldpw', new_password: 'newpass123' });
      expect(screen.getByText(/обновлён/i)).toBeInTheDocument();
    });
  });

  it('shows API error', async () => {
    server.use(
      http.get('/api/auth/me', () => HttpResponse.json({ id: 1, username: 'admin' })),
      http.post('/api/admin/password', () =>
        HttpResponse.json({ detail: 'Неверный старый пароль' }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderFresh(<AccountPage />);
    await waitFor(() => screen.getByText('admin'));

    await user.type(inputByLabel('Старый пароль'), 'wrong');
    await user.type(inputByLabel('Новый пароль'), 'newpass123');
    await user.type(inputByLabel('Повторите новый пароль'), 'newpass123');
    await user.click(screen.getByRole('button', { name: /Сменить пароль/i }));
    await waitFor(() => {
      expect(screen.getByText(/Неверный старый пароль/)).toBeInTheDocument();
    });
  });

  it('disables button while empty fields', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({ id: 1, username: 'admin' })));
    renderFresh(<AccountPage />);
    await waitFor(() => screen.getByText('admin'));
    expect(screen.getByRole('button', { name: /Сменить пароль/i })).toBeDisabled();
  });
});

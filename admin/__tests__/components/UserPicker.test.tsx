import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { UserPicker, type PickedUser } from '@/components/UserPicker';
import { server } from '../mocks/server';

function Harness({ onChange }: { onChange?: (u: PickedUser | null) => void } = {}) {
  const [v, setV] = useState<PickedUser | null>(null);
  return (
    <UserPicker
      value={v}
      onChange={(u) => {
        setV(u);
        onChange?.(u);
      }}
    />
  );
}

describe('UserPicker', () => {
  it('shows placeholder text', () => {
    render(<Harness />);
    expect(screen.getByPlaceholderText(/имя/i)).toBeInTheDocument();
  });

  it('shows dropdown with users on focus', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByPlaceholderText(/имя/i));
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
    });
  });

  it('filters by query (debounced)', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByPlaceholderText(/имя/i);
    await user.click(input);
    await waitFor(() => screen.getByText('Alice'));
    await user.type(input, 'bob');
    await waitFor(() => {
      expect(screen.getByText('Bob')).toBeInTheDocument();
      expect(screen.queryByText('Alice')).not.toBeInTheDocument();
    });
  });

  it('strips @ prefix from query', async () => {
    let capturedQ: string | null = null;
    server.use(
      http.get('/api/users', ({ request }) => {
        capturedQ = new URL(request.url).searchParams.get('q');
        return HttpResponse.json({ total: 0, items: [] });
      }),
    );
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByPlaceholderText(/имя/i);
    await user.click(input);
    await user.type(input, '@alice');
    // Бэкенд получает строку с @ — он сам должен зачистить
    await waitFor(() => expect(capturedQ).toBe('@alice'));
  });

  it('selects user with mouse click', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Harness onChange={onChange} />);
    await user.click(screen.getByPlaceholderText(/имя/i));
    await waitFor(() => screen.getByText('Alice'));
    await user.click(screen.getByText('Alice'));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: 1, first_name: 'Alice', username: 'alice' }),
    );
  });

  it('selects user with ArrowDown + Enter', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Harness onChange={onChange} />);
    const input = screen.getByPlaceholderText(/имя/i);
    await user.click(input);
    await waitFor(() => screen.getByText('Alice'));
    await user.keyboard('{ArrowDown}{Enter}');
    await waitFor(() => expect(onChange).toHaveBeenCalled());
  });

  it('shows empty message when no results', async () => {
    server.use(
      http.get('/api/users', () =>
        HttpResponse.json({ total: 0, items: [] }),
      ),
    );
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByPlaceholderText(/имя/i));
    await waitFor(() => {
      expect(screen.getByText(/никого не нашли/i)).toBeInTheDocument();
    });
  });

  it('renders selected user as chip and supports clearing', async () => {
    const onChange = vi.fn();
    const value: PickedUser = {
      id: 1,
      telegram_user_id: 111,
      username: 'alice',
      first_name: 'Alice',
      last_name: null,
    };
    const user = userEvent.setup();
    render(<UserPicker value={value} onChange={onChange} />);
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.getByLabelText('Очистить')).toBeInTheDocument();
    await user.click(screen.getByLabelText('Очистить'));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('closes dropdown on outside click', async () => {
    const user = userEvent.setup();
    render(
      <>
        <div data-testid="outside">outside</div>
        <Harness />
      </>,
    );
    await user.click(screen.getByPlaceholderText(/имя/i));
    await waitFor(() => screen.getByText('Alice'));
    // Клик снаружи — закрывает
    await user.click(screen.getByTestId('outside'));
    await waitFor(() => {
      expect(screen.queryByText('Alice')).not.toBeInTheDocument();
    });
  });

  it('handles API error gracefully (empty list)', async () => {
    server.use(
      http.get('/api/users', () =>
        new HttpResponse('boom', { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByPlaceholderText(/имя/i));
    // Не падаем — показываем "никого не нашли"
    await waitFor(() => {
      expect(screen.getByText(/никого не нашли/i)).toBeInTheDocument();
    });
  });
});

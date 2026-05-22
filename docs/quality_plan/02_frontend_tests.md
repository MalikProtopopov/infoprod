# 02. Frontend — стратегия тестирования

## 2.1 Стек

| Инструмент | Версия | Назначение |
|-----------|-------|-----------|
| **Vitest** | 2.1+ | Test runner, Jest-совместимый, нативный TS, быстрее Jest в ~2× |
| **@testing-library/react** | 16+ | Тестирование компонентов по поведению |
| **@testing-library/user-event** | 14+ | Реалистичная имитация кликов / ввода |
| **@testing-library/jest-dom** | 6+ | Расширенные матчеры (`toBeInTheDocument`) |
| **MSW** (Mock Service Worker) | 2.7+ | Мок API на уровне сети |
| **happy-dom** | 15+ | Быстрая JSDOM-альтернатива |
| **@vitest/coverage-v8** | 2.1+ | Coverage report (V8 native) |
| **eslint** + **eslint-plugin-react** | 9+ | Линтер |
| **prettier** | 3+ | Format |

Добавить в `admin/package.json` под `devDependencies`:

```json
{
  "vitest": "^2.1.8",
  "@vitest/coverage-v8": "^2.1.8",
  "@testing-library/react": "^16.1.0",
  "@testing-library/user-event": "^14.5.2",
  "@testing-library/jest-dom": "^6.6.3",
  "msw": "^2.7.0",
  "happy-dom": "^15.11.7",
  "@types/node": "^22.10.5",
  "eslint": "^9.18.0",
  "eslint-plugin-react": "^7.37.4",
  "eslint-plugin-react-hooks": "^5.1.0",
  "prettier": "^3.4.2",
  "typescript": "^5.7.2"
}
```

## 2.2 Структура

```
admin/
├── app/                       # Next.js routes
├── components/
├── lib/
├── __tests__/
│   ├── setup.ts               # глобальный setup
│   ├── mocks/
│   │   ├── server.ts          # MSW server
│   │   ├── handlers.ts        # API-моки
│   │   └── fixtures/          # JSON-фикстуры от API
│   ├── components/
│   │   ├── Button.test.tsx
│   │   ├── Sheet.test.tsx
│   │   ├── UserPicker.test.tsx
│   │   └── ui.test.tsx
│   ├── lib/
│   │   └── api.test.ts
│   └── pages/                 # рендер целых страниц
│       ├── login.test.tsx
│       ├── products.test.tsx
│       ├── payments.test.tsx
│       └── sources.test.tsx
├── vitest.config.ts
└── tsconfig.json
```

## 2.3 `vitest.config.ts`

```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './'),
    },
  },
  test: {
    environment: 'happy-dom',
    setupFiles: ['./__tests__/setup.ts'],
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      exclude: [
        'node_modules/',
        '.next/',
        'next.config.mjs',
        'postcss.config.mjs',
        'tailwind.config.ts',
        '__tests__/',
      ],
      thresholds: {
        lines: 98,
        functions: 98,
        branches: 95,
        statements: 98,
      },
    },
    css: false,
    pool: 'threads',
  },
});
```

## 2.4 `__tests__/setup.ts`

```ts
import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from './mocks/server';
import { cleanup } from '@testing-library/react';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => { server.resetHandlers(); cleanup(); });
afterAll(() => server.close());

// next/navigation моки
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

// matchMedia stub для responsive-компонентов
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((q) => ({
    matches: false, media: q, onchange: null,
    addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// crypto.randomUUID на старом jsdom
if (!('randomUUID' in crypto)) {
  // @ts-ignore
  crypto.randomUUID = () => 'test-uuid-' + Math.random().toString(36).slice(2);
}
```

## 2.5 MSW — `__tests__/mocks/server.ts` и `handlers.ts`

### server.ts

```ts
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

### handlers.ts

```ts
import { http, HttpResponse } from 'msw';

const API = '/api';  // same-origin

export const handlers = [
  http.post(`${API}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string };
    if (body.username === 'admin' && body.password === 'goodpass') {
      return HttpResponse.json({ ok: true, username: 'admin' });
    }
    return HttpResponse.json({ detail: 'Неверный логин или пароль' }, { status: 401 });
  }),

  http.get(`${API}/auth/me`, () =>
    HttpResponse.json({ id: 1, username: 'admin' })
  ),

  http.get(`${API}/products`, () =>
    HttpResponse.json([
      { id: 1, code: 'p1', name: 'Product 1', channel_id: 1, channel_title: 'Channel A',
        price_3m: '1000', price_6m: '1800', price_12m: '3000', currency: 'RUB', is_active: true,
        description: null, cover_url: null },
    ])
  ),

  http.get(`${API}/tracking-links`, ({ request }) => {
    const url = new URL(request.url);
    const pid = url.searchParams.get('product_id');
    return HttpResponse.json([
      { id: 10, slug: 'abc12345', url: 'https://t.me/bot?start=abc12345',
        product: { id: Number(pid) || 1, code: 'p1', name: 'Product 1' },
        bot: { id: 1, username: 'bot' },
        utm_source: 'instagram', utm_medium: 'reels', utm_campaign: 'spring',
        utm_content: null, notes: null, is_active: true,
        click_count: 12, unique_users: 8, leads_count: 3, payments_count: 1, revenue: '1000',
        created_at: '2026-05-22T12:00:00Z',
      },
    ]);
  }),

  http.post(`${API}/tracking-links`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: 99, slug: 'newslug1', url: 'https://t.me/bot?start=newslug1',
      product: { id: body.product_id, code: 'p1', name: 'Product 1' },
      bot: { id: 1, username: 'bot' },
      utm_source: body.utm_source, utm_medium: body.utm_medium ?? null,
      utm_campaign: body.utm_campaign ?? null, utm_content: null, notes: null,
      is_active: true, click_count: 0, unique_users: 0,
      leads_count: 0, payments_count: 0, revenue: '0',
      created_at: new Date().toISOString(),
    }, { status: 201 });
  }),

  http.get(`${API}/stats/sources`, () =>
    HttpResponse.json({
      from: '2026-04-22T00:00:00Z', to: '2026-05-22T00:00:00Z',
      group_by: 'source',
      rows: [
        { source: 'instagram', clicks: 100, unique_users: 80, leads: 20, payments: 5,
          revenue: '5000', conv_click_to_lead: 0.2, conv_lead_to_payment: 0.25, avg_check: 1000 },
      ],
      totals: { clicks: 100, unique_users: 80, leads: 20, payments: 5, revenue: '5000' },
    })
  ),

  // catch-all 404 для непокрытых хендлеров
];
```

## 2.6 Примеры тестов

### 2.6.1 Компонент — Button

```tsx
// __tests__/components/Button.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from '@/components/ui';

describe('Button', () => {
  it('renders text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('calls onClick once when clicked', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(<Button onClick={onClick}>Press</Button>);
    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when prop is set', () => {
    render(<Button disabled>Off</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it.each([
    ['primary', /gradient-primary/],
    ['ghost',   /glass-soft/],
    ['danger',  /gradient-danger/],
  ])('applies %s variant class', (variant, regex) => {
    const { container } = render(<Button variant={variant as any}>X</Button>);
    expect(container.querySelector('button')!.className).toMatch(regex);
  });
});
```

### 2.6.2 Компонент с состоянием — UserPicker

```tsx
// __tests__/components/UserPicker.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { UserPicker } from '@/components/UserPicker';
import { useState } from 'react';

function Harness() {
  const [v, setV] = useState(null);
  return <UserPicker value={v} onChange={setV} />;
}

describe('UserPicker', () => {
  it('shows dropdown on focus', async () => {
    server.use(http.get('/api/users', () =>
      HttpResponse.json({
        total: 2,
        items: [
          { id: 1, telegram_user_id: 111, username: 'alice', first_name: 'Alice', last_name: null },
          { id: 2, telegram_user_id: 222, username: 'bob',   first_name: 'Bob',   last_name: null },
        ],
      }),
    ));
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByPlaceholderText(/имя/i));
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
    });
  });

  it('strips leading @ when querying', async () => {
    let capturedQ: string | null = null;
    server.use(http.get('/api/users', ({ request }) => {
      capturedQ = new URL(request.url).searchParams.get('q');
      return HttpResponse.json({ total: 0, items: [] });
    }));
    const user = userEvent.setup();
    render(<Harness />);
    const input = screen.getByPlaceholderText(/имя/i);
    await user.click(input);
    await user.type(input, '@alice');
    await waitFor(() => expect(capturedQ).toBe('@alice'));  // backend strips
  });

  it('selects user with keyboard ArrowDown + Enter', async () => {
    server.use(http.get('/api/users', () =>
      HttpResponse.json({
        total: 1,
        items: [{ id: 1, telegram_user_id: 111, username: 'alice', first_name: 'Alice', last_name: null }],
      })
    ));
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByPlaceholderText(/имя/i));
    await waitFor(() => screen.getByText('Alice'));
    await user.keyboard('{ArrowDown}{Enter}');
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
  });

  it('clears selection on ✕ click', async () => {
    const user = userEvent.setup();
    render(<UserPicker value={{ id: 1, telegram_user_id: 111, username: 'a', first_name: 'A', last_name: null }} onChange={vi.fn()} />);
    await user.click(screen.getByLabelText('Очистить'));
    // onChange called with null
  });
});
```

### 2.6.3 Страница — Login

```tsx
// __tests__/pages/login.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginPage from '@/app/login/page';

describe('LoginPage', () => {
  it('shows error on bad credentials', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByLabelText(/логин/i), 'admin');
    await user.type(screen.getByLabelText(/пароль/i), 'wrongpass');
    await user.click(screen.getByRole('button', { name: /войти/i }));
    expect(await screen.findByText(/неверный логин/i)).toBeInTheDocument();
  });

  it('redirects on successful login', async () => {
    const user = userEvent.setup();
    const { useRouter } = await import('next/navigation');
    const router = useRouter();
    render(<LoginPage />);
    await user.type(screen.getByLabelText(/логин/i), 'admin');
    await user.type(screen.getByLabelText(/пароль/i), 'goodpass');
    await user.click(screen.getByRole('button', { name: /войти/i }));
    await vi.waitFor(() => expect(router.push).toHaveBeenCalledWith('/'));
  });
});
```

### 2.6.4 API-клиент — `lib/api.ts`

```ts
// __tests__/lib/api.test.ts
import { api } from '@/lib/api';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';

describe('api client', () => {
  it('sends credentials and parses JSON', async () => {
    let credentials: string | undefined;
    server.use(http.get('/api/echo', ({ request }) => {
      credentials = request.credentials;
      return HttpResponse.json({ ok: true });
    }));
    const r = await api.get<{ ok: boolean }>('/echo');
    expect(r.ok).toBe(true);
    expect(credentials).toBe('include');
  });

  it('throws with detail on 4xx', async () => {
    server.use(http.post('/api/test', () =>
      HttpResponse.json({ detail: 'Validation failed' }, { status: 422 })
    ));
    await expect(api.post('/test', {})).rejects.toThrow('Validation failed');
  });

  it('redirects to /login on 401 (in browser)', async () => {
    const origLocation = window.location;
    // @ts-ignore
    delete window.location;
    window.location = { ...origLocation, pathname: '/payments', href: '' } as any;
    server.use(http.get('/api/protected', () =>
      HttpResponse.json({ detail: 'Not auth' }, { status: 401 })
    ));
    await expect(api.get('/protected')).rejects.toThrow('Unauthorized');
    expect(window.location.href).toBe('/login');
  });
});
```

## 2.7 Скрипты в `package.json`

```json
{
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:cov": "vitest run --coverage",
    "test:ui": "vitest --ui",
    "lint": "next lint",
    "type-check": "tsc --noEmit",
    "format": "prettier --write .",
    "format:check": "prettier --check ."
  }
}
```

## 2.8 Что обязательно покрыть

| Файл/компонент | Приоритет | Целевое покрытие |
|---|---|---|
| `lib/api.ts` | критичный | 100% |
| `components/ui.tsx` (Button, Card, Sheet, Input, Select, Pill) | критичный | 100% |
| `components/UserPicker.tsx` | критичный | 98% (KB-навигация, debounce, очистка) |
| `app/login/page.tsx` | критичный | 100% (login flow) |
| `app/(dash)/layout.tsx` | критичный | 95% (auth-redirect, navOpen) |
| `app/(dash)/payments/page.tsx` | критичный | 98% (auto-select period, валидация) |
| `app/(dash)/products/[id]/page.tsx` | критичный | 95% (создание ссылок, QR) |
| `app/(dash)/sources/page.tsx` | критичный | 95% (useMemo не зацикливается, фильтры) |
| Все остальные `app/(dash)/*` страницы | важный | 90% |

## 2.9 «Регрессионный тест для бага которого больше не будет»

Каждый раз когда вы чините **прод-баг**, обязательно пишется **failing test** в `__tests__/regressions/`. После фикса тест становится passing. Пример:

```tsx
// __tests__/regressions/2026_05_22_sources_infinite_loop.test.tsx
import { render, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import SourcesPage from '@/app/(dash)/sources/page';

describe('regression: /sources infinite loop (2026-05-22)', () => {
  it('does not fetch /stats/sources more than 2 times on initial render', async () => {
    let calls = 0;
    server.use(http.get('/api/stats/sources', () => {
      calls += 1;
      return HttpResponse.json({ from: '', to: '', group_by: 'source', rows: [], totals: {} });
    }));
    render(<SourcesPage />);
    await new Promise(r => setTimeout(r, 500));
    expect(calls).toBeLessThanOrEqual(2);  // 1 первый + max 1 revalidate
  });
});
```

Этот тест предотвращает повторное появление бага.

## 2.10 Чек-лист

- [ ] Установить deps + Vitest config
- [ ] Написать `__tests__/setup.ts` с MSW и Next.js моками
- [ ] Написать `mocks/server.ts` + базовые handlers
- [ ] Покрыть `components/ui.tsx` (все примитивы)
- [ ] Покрыть `components/UserPicker.tsx` с keyboard navigation
- [ ] Покрыть `lib/api.ts` (success/4xx/401-redirect)
- [ ] Покрыть `app/login/page.tsx`
- [ ] Покрыть `app/(dash)/layout.tsx`
- [ ] Покрыть каждую страницу `(dash)/*` (минимум — рендерится без ошибок при MSW-моке)
- [ ] Регрессионный тест для бага «sources infinite loop»
- [ ] CI блокирует при coverage < 98%

import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import { server } from './mocks/server';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

// next/navigation моки — большинство компонентов на это завязаны
vi.mock('next/navigation', () => {
  const push = vi.fn();
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    useRouter: () => ({ push, replace, refresh, back: vi.fn(), forward: vi.fn(), prefetch: vi.fn() }),
    usePathname: () => '/',
    useSearchParams: () => new URLSearchParams(),
    redirect: vi.fn(),
  };
});

// matchMedia stub для responsive-компонентов
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((q: string) => ({
    matches: false,
    media: q,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// crypto.randomUUID может отсутствовать в happy-dom
if (!('randomUUID' in crypto)) {
  // @ts-expect-error patch
  crypto.randomUUID = () => 'test-uuid-' + Math.random().toString(36).slice(2);
}

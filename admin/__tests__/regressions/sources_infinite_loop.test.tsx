/**
 * Регрессия 2026-05-22:
 *   /sources страница делала запросы бесконечно потому что from/to пересчитывались
 *   на каждом рендере (new Date() даёт новые миллисекунды → SWR-ключ меняется → новый fetch).
 *   Фикс: useMemo для swrKey + revalidateOnFocus: false.
 *
 * Этот тест: не более 2 запросов к /api/stats/sources за первые 500 мс рендера.
 */
import { render } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import SourcesPage from '@/app/(dash)/sources/page';
import { server } from '../mocks/server';

describe('regression: /sources infinite loop (2026-05-22)', () => {
  it('does not fetch /stats/sources more than 2 times on initial render', async () => {
    let calls = 0;
    server.use(
      http.get('/api/stats/sources', () => {
        calls += 1;
        return HttpResponse.json({
          from: '2026-04-22T00:00:00Z',
          to: '2026-05-22T00:00:00Z',
          group_by: 'source',
          rows: [],
          totals: { clicks: 0, unique_users: 0, leads: 0, payments: 0, revenue: '0' },
        });
      }),
    );
    render(<SourcesPage />);
    await new Promise((r) => setTimeout(r, 500));
    expect(calls).toBeLessThanOrEqual(2);
  });
});

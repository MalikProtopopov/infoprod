import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';

import { api } from '@/lib/api';
import { server } from '../mocks/server';

describe('api client', () => {
  it('GET parses JSON', async () => {
    server.use(http.get('/api/foo', () => HttpResponse.json({ ok: true })));
    const r = await api.get<{ ok: boolean }>('/foo');
    expect(r.ok).toBe(true);
  });

  it('POST sends JSON body', async () => {
    let received: unknown = null;
    server.use(
      http.post('/api/echo', async ({ request }) => {
        received = await request.json();
        return HttpResponse.json({ ok: true });
      }),
    );
    await api.post('/echo', { hello: 'world' });
    expect(received).toEqual({ hello: 'world' });
  });

  it('throws with detail on 4xx', async () => {
    server.use(
      http.post('/api/test', () =>
        HttpResponse.json({ detail: 'Validation failed' }, { status: 422 }),
      ),
    );
    await expect(api.post('/test', {})).rejects.toThrow('Validation failed');
  });

  it('throws with statusText when no detail', async () => {
    server.use(
      http.get('/api/empty', () => HttpResponse.json(null, { status: 500 })),
    );
    await expect(api.get('/empty')).rejects.toThrow();
  });

  it('returns undefined on 204', async () => {
    server.use(
      http.delete('/api/x/1', () => new HttpResponse(null, { status: 204 })),
    );
    const r = await api.del('/x/1');
    expect(r).toBeUndefined();
  });
});

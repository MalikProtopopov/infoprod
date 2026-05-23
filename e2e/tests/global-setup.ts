/**
 * Один раз логинимся, сохраняем cookie в .auth/state.json.
 * Все тесты переиспользуют — это обходит rate-limit на /api/auth/login.
 */
import { chromium, request } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

export default async function globalSetup() {
  const baseURL = process.env.E2E_BASE_URL || 'https://grammy.mediann.dev';
  const username = process.env.E2E_ADMIN_USER || 'admin';
  const password = process.env.E2E_ADMIN_PASS;
  if (!password) throw new Error('E2E_ADMIN_PASS env var обязателен');

  const ctx = await request.newContext({ baseURL, ignoreHTTPSErrors: true });
  const resp = await ctx.post('/api/auth/login', {
    data: { username, password },
  });
  if (!resp.ok()) {
    throw new Error(`globalSetup login failed: ${resp.status()} ${await resp.text()}`);
  }
  const state = await ctx.storageState();
  const dir = path.join(__dirname, '..', '.auth');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'state.json'), JSON.stringify(state));
  await ctx.dispose();
}

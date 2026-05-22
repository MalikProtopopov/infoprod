'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { api } from '@/lib/api';
import { Button, Field, Input } from '@/components/ui';

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.post('/auth/login', { username, password });
      router.push('/');
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md anim-rise">
        <div className="mb-6 flex items-center justify-center gap-3">
          <div className="size-11 rounded-2xl gradient-primary text-white font-bold flex items-center justify-center shadow-[0_12px_28px_-10px_rgba(124,58,237,0.55)]">
            i
          </div>
          <div>
            <div className="text-2xl font-bold tracking-tight">Infobizbot</div>
            <div className="text-[11px] uppercase tracking-widest text-zinc-500">admin panel</div>
          </div>
        </div>

        <div className="glass-strong rounded-2xl p-6 sm:p-8">
          <h1 className="text-xl font-semibold tracking-tight text-center">
            Вход в <span className="gradient-text">админ‑панель</span>
          </h1>
          <p className="mt-1 text-center text-sm text-zinc-500">
            Используйте логин и пароль администратора
          </p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <Field label="Логин">
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
                autoComplete="username"
              />
            </Field>
            <Field label="Пароль">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </Field>
            {error && (
              <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
                {error}
              </div>
            )}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Входим…' : 'Войти'}
            </Button>
          </form>
        </div>

        <div className="mt-6 text-center text-xs text-zinc-500">
          Безопасное соединение · TLS Let's Encrypt
        </div>
      </div>
    </main>
  );
}

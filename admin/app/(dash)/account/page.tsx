'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { Button, Card, Field, Input, PageHeader } from '@/components/ui';

type Me = { id: number; username: string };

export default function AccountPage() {
  const { data } = useSWR<Me>('/auth/me', fetcher);
  const [oldPwd, setOldPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [newPwd2, setNewPwd2] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function save() {
    setBusy(true); setError(null); setOk(false);
    try {
      if (newPwd.length < 6) throw new Error('Пароль должен быть не короче 6 символов');
      if (newPwd !== newPwd2) throw new Error('Пароли не совпадают');
      await api.post('/admin/password', { old_password: oldPwd, new_password: newPwd });
      setOk(true); setOldPwd(''); setNewPwd(''); setNewPwd2('');
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <PageHeader title="Профиль" subtitle="Управление учётной записью администратора" />

      <Card padded className="max-w-md anim-rise">
        <div className="flex items-center gap-4 mb-5">
          <div className="size-12 rounded-2xl gradient-primary text-white text-base font-bold flex items-center justify-center shadow-[0_10px_24px_-10px_rgba(124,58,237,0.55)]">
            {(data?.username?.[0] || 'A').toUpperCase()}
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-zinc-500">Логин</div>
            <div className="font-medium">{data?.username}</div>
          </div>
        </div>

        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-indigo-500" /> Смена пароля
        </h3>
        <div className="space-y-3">
          <Field label="Старый пароль" required>
            <Input type="password" value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} />
          </Field>
          <Field label="Новый пароль" required>
            <Input type="password" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} />
          </Field>
          <Field label="Повторите новый пароль" required>
            <Input type="password" value={newPwd2} onChange={(e) => setNewPwd2(e.target.value)} />
          </Field>
          {error && <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>}
          {ok && <div className="text-sm text-emerald-700">Пароль обновлён</div>}
          <Button onClick={save} disabled={busy || !oldPwd || !newPwd || !newPwd2}>
            {busy ? 'Сохраняем…' : 'Сменить пароль'}
          </Button>
        </div>
      </Card>
    </div>
  );
}

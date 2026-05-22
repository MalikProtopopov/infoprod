'use client';

import { use, useEffect, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { Button, Card, Empty, Field, Input, PageHeader, Pill, Textarea } from '@/components/ui';

type UserCard = {
  user: {
    id: number;
    telegram_user_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
    phone: string | null;
    email: string | null;
    notes: string | null;
    first_seen_at: string;
    last_seen_at: string;
  };
  leads: Array<{
    id: number;
    product_name: string;
    channel_title: string | null;
    status: string;
    created_at: string;
  }>;
  payments: Array<{
    id: number;
    product_name: string;
    channel_title: string | null;
    period_months: number;
    amount: string;
    currency: string;
    created_at: string;
  }>;
  subscriptions: Array<{
    id: number;
    channel_id: number;
    channel_title: string | null;
    product_id: number | null;
    product_name: string | null;
    starts_at: string;
    ends_at: string;
    status: string;
    invite_link: string | null;
  }>;
};

export default function UserPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, mutate } = useSWR<UserCard>(`/users/${id}`, fetcher);
  const [form, setForm] = useState({ phone: '', email: '', notes: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    if (data) setForm({ phone: data.user.phone ?? '', email: data.user.email ?? '', notes: data.user.notes ?? '' });
  }, [data]);

  if (!data) return <div className="text-sm text-zinc-500">Загрузка…</div>;
  const u = data.user;
  const fullName = [u.first_name, u.last_name].filter(Boolean).join(' ') || `Пользователь #${u.id}`;

  async function save() {
    setBusy(true); setError(null); setOk(false);
    try {
      await api.patch(`/users/${id}`, {
        phone: form.phone || null,
        email: form.email || null,
        notes: form.notes || null,
      });
      await mutate(); setOk(true);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <PageHeader
        title={fullName}
        subtitle={u.username ? '@' + u.username : `Telegram ID ${u.telegram_user_id}`}
        action={
          u.username && (
            <a href={`https://t.me/${u.username}`} target="_blank" rel="noreferrer">
              <Button variant="glass">Написать в Telegram ↗</Button>
            </a>
          )
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card padded className="anim-rise">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-indigo-500" /> Из Telegram
          </h3>
          <dl className="text-sm space-y-1.5">
            <Row label="TG ID" mono>{u.telegram_user_id}</Row>
            <Row label="Username">{u.username ? '@' + u.username : '—'}</Row>
            <Row label="Имя">{u.first_name || '—'}</Row>
            <Row label="Фамилия">{u.last_name || '—'}</Row>
            <Row label="Первый визит">{new Date(u.first_seen_at).toLocaleString('ru-RU')}</Row>
            <Row label="Последний визит">{new Date(u.last_seen_at).toLocaleString('ru-RU')}</Row>
          </dl>
        </Card>

        <Card padded className="anim-rise">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-violet-500" /> Данные администратора
          </h3>
          <div className="space-y-3">
            <Field label="Телефон">
              <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="Email">
              <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </Field>
            <Field label="Заметки">
              <Textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Field>
            {error && <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>}
            {ok && <div className="text-sm text-emerald-700">Сохранено</div>}
            <Button onClick={save} disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</Button>
          </div>
        </Card>
      </div>

      <Card padded className="mt-5 anim-rise">
        <h3 className="font-semibold mb-4">Подписки</h3>
        {data.subscriptions.length === 0 ? <Empty>Подписок нет</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[680px]">
              <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2 pr-3">Канал</th>
                  <th className="py-2 pr-3">Продукт</th>
                  <th className="py-2 pr-3">Статус</th>
                  <th className="py-2 pr-3">Начало</th>
                  <th className="py-2 pr-3">Окончание</th>
                  <th className="py-2">Ссылка</th>
                </tr>
              </thead>
              <tbody>
                {data.subscriptions.map((s) => (
                  <tr key={s.id} className="border-t border-zinc-100/80">
                    <td className="py-2.5 pr-3">{s.channel_title || '—'}</td>
                    <td className="py-2.5 pr-3 text-zinc-600">{s.product_name || '—'}</td>
                    <td className="py-2.5 pr-3"><SubStatus s={s.status} /></td>
                    <td className="py-2.5 pr-3">{new Date(s.starts_at).toLocaleDateString('ru-RU')}</td>
                    <td className="py-2.5 pr-3">{new Date(s.ends_at).toLocaleDateString('ru-RU')}</td>
                    <td className="py-2.5 truncate max-w-[200px]">
                      {s.invite_link ? <a className="text-indigo-600 hover:underline" href={s.invite_link} target="_blank" rel="noreferrer">link ↗</a> : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card padded className="mt-5 anim-rise">
        <h3 className="font-semibold mb-4">Платежи</h3>
        {data.payments.length === 0 ? <Empty>Платежей нет</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[680px]">
              <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2 pr-3">Дата</th>
                  <th className="py-2 pr-3">Канал</th>
                  <th className="py-2 pr-3">Продукт</th>
                  <th className="py-2 pr-3">Период</th>
                  <th className="py-2">Сумма</th>
                </tr>
              </thead>
              <tbody>
                {data.payments.map((p) => (
                  <tr key={p.id} className="border-t border-zinc-100/80">
                    <td className="py-2.5 pr-3">{new Date(p.created_at).toLocaleString('ru-RU')}</td>
                    <td className="py-2.5 pr-3 text-zinc-600">{p.channel_title || '—'}</td>
                    <td className="py-2.5 pr-3">{p.product_name}</td>
                    <td className="py-2.5 pr-3">{p.period_months} мес.</td>
                    <td className="py-2.5 font-medium">{p.amount} {p.currency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card padded className="mt-5 anim-rise">
        <h3 className="font-semibold mb-4">Заявки</h3>
        {data.leads.length === 0 ? <Empty>Заявок нет</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2 pr-3">Дата</th>
                  <th className="py-2 pr-3">Канал</th>
                  <th className="py-2 pr-3">Продукт</th>
                  <th className="py-2">Статус</th>
                </tr>
              </thead>
              <tbody>
                {data.leads.map((l) => (
                  <tr key={l.id} className="border-t border-zinc-100/80">
                    <td className="py-2.5 pr-3">{new Date(l.created_at).toLocaleString('ru-RU')}</td>
                    <td className="py-2.5 pr-3 text-zinc-600">{l.channel_title || '—'}</td>
                    <td className="py-2.5 pr-3">{l.product_name}</td>
                    <td className="py-2.5"><LeadStatus s={l.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Row({ label, children, mono }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3 border-b border-zinc-100/80 py-1.5">
      <dt className="text-zinc-500 text-xs uppercase tracking-wide">{label}</dt>
      <dd className={`text-zinc-900 text-right ${mono ? 'font-mono text-xs' : ''}`}>{children}</dd>
    </div>
  );
}

function SubStatus({ s }: { s: string }) {
  if (s === 'active') return <Pill color="green">активна</Pill>;
  if (s === 'expired') return <Pill color="amber">истекла</Pill>;
  if (s === 'revoked') return <Pill color="red">отозвана</Pill>;
  return <Pill color="gray">{s}</Pill>;
}

function LeadStatus({ s }: { s: string }) {
  if (s === 'new') return <Pill color="amber">новая</Pill>;
  if (s === 'contacted') return <Pill color="gray">связались</Pill>;
  if (s === 'paid') return <Pill color="green">оплачена</Pill>;
  if (s === 'closed') return <Pill color="red">закрыта</Pill>;
  return <Pill color="gray">{s}</Pill>;
}

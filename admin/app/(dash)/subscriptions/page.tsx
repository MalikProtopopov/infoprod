'use client';

import { useState } from 'react';
import useSWR from 'swr';
import clsx from 'clsx';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Sheet,
  TableHead, TableWrap, Td, Th, Tr,
} from '@/components/ui';

type Sub = {
  id: number;
  user_id: number;
  user_username: string | null;
  user_first_name: string | null;
  channel_id: number;
  channel_title: string | null;
  product_id: number | null;
  product_name: string | null;
  payment_id: number | null;
  starts_at: string;
  ends_at: string;
  status: string;
  invite_link: string | null;
};

const TABS = [
  { key: 'active', label: 'Активные' },
  { key: 'expired', label: 'Истёкшие' },
  { key: 'revoked', label: 'Отозванные' },
  { key: 'all', label: 'Все' },
] as const;

export default function SubscriptionsPage() {
  const [status, setStatus] = useState<typeof TABS[number]['key']>('active');
  const { data, mutate, isLoading } = useSWR<Sub[]>(`/subscriptions?status=${status}`, fetcher);

  const [extending, setExtending] = useState<Sub | null>(null);
  const [days, setDays] = useState('0');
  const [months, setMonths] = useState('1');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function revoke(s: Sub) {
    if (!confirm('Отозвать подписку? Пользователь будет удалён из канала.')) return;
    await api.post(`/subscriptions/${s.id}/revoke`); mutate();
  }
  async function extend() {
    if (!extending) return;
    setBusy(true); setError(null);
    try {
      await api.post(`/subscriptions/${extending.id}/extend`, {
        days: Number(days) || null,
        months: Number(months) || null,
      });
      setExtending(null); mutate();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <PageHeader title="Подписки" subtitle="Доступы пользователей в каналы — активные и истёкшие" />

      <div className="mb-4 inline-flex glass rounded-2xl p-1.5 overflow-x-auto max-w-full">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setStatus(t.key)}
            className={clsx(
              'px-3 sm:px-4 h-9 rounded-xl text-sm whitespace-nowrap transition',
              status === t.key ? 'bg-white shadow-soft text-ink' : 'text-zinc-600 hover:text-ink hover:bg-white/60',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Подписок нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[760px]">
              <TableHead>
                <Th>Пользователь</Th>
                <Th>Канал</Th>
                <Th>Продукт</Th>
                <Th>До</Th>
                <Th>Статус</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((s) => (
                  <Tr key={s.id}>
                    <Td>
                      {s.user_first_name || '—'}
                      {s.user_username && <span className="text-zinc-500 ml-1">@{s.user_username}</span>}
                    </Td>
                    <Td>{s.channel_title}</Td>
                    <Td className="text-zinc-600">{s.product_name || '—'}</Td>
                    <Td>{new Date(s.ends_at).toLocaleDateString('ru-RU')}</Td>
                    <Td><StatusPill s={s.status} /></Td>
                    <Td className="text-right">
                      <div className="inline-flex gap-2">
                        <Button size="sm" variant="ghost" onClick={() => { setExtending(s); setError(null); setDays('0'); setMonths('1'); }}>
                          Продлить
                        </Button>
                        {s.status === 'active' && (
                          <Button size="sm" variant="danger" onClick={() => revoke(s)}>Отозвать</Button>
                        )}
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>

      <Sheet
        open={!!extending}
        onClose={() => setExtending(null)}
        title="Продлить подписку"
        description="Без создания платежа — для исключительных случаев"
        footer={
          <>
            <Button variant="ghost" onClick={() => setExtending(null)}>Отмена</Button>
            <Button
              onClick={extend}
              disabled={busy || ((Number(days) || 0) + (Number(months) || 0) <= 0)}
            >
              {busy ? '…' : 'Продлить'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Месяцев">
              <Input type="number" min={0} value={months} onChange={(e) => setMonths(e.target.value)} />
            </Field>
            <Field label="Дней">
              <Input type="number" min={0} value={days} onChange={(e) => setDays(e.target.value)} />
            </Field>
          </div>
          {error && <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>}
        </div>
      </Sheet>
    </div>
  );
}

function StatusPill({ s }: { s: string }) {
  if (s === 'active') return <Pill color="green">активна</Pill>;
  if (s === 'expired') return <Pill color="amber">истекла</Pill>;
  if (s === 'revoked') return <Pill color="red">отозвана</Pill>;
  return <Pill color="gray">{s}</Pill>;
}

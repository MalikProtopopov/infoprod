'use client';

import Link from 'next/link';
import clsx from 'clsx';
import { use, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, PageHeader, Pill, TableHead, TableWrap, Td, Th, Tr,
} from '@/components/ui';

type Entry = {
  id: number;
  funnel_id: number;
  user_id: number;
  user_first_name: string | null;
  user_username: string | null;
  source: string;
  source_ref: number | null;
  started_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  status: string;
};

const TABS: Array<{ key: 'all' | 'active' | 'completed' | 'cancelled'; label: string }> = [
  { key: 'active', label: 'Активные' },
  { key: 'completed', label: 'Завершено' },
  { key: 'cancelled', label: 'Отменено' },
  { key: 'all', label: 'Все' },
];

export default function FunnelEntriesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [status, setStatus] = useState<'all' | 'active' | 'completed' | 'cancelled'>('active');
  const key = `/funnels/${id}/entries${status === 'all' ? '' : `?status=${status}`}`;
  const { data, mutate, isLoading } = useSWR<Entry[]>(key, fetcher);

  async function cancel(e: Entry) {
    if (!confirm(`Отменить воронку для пользователя ${e.user_first_name || e.user_id}?`)) return;
    try { await api.post(`/funnel-entries/${e.id}/cancel`); mutate(); }
    catch (err) { alert(err instanceof Error ? err.message : String(err)); }
  }

  return (
    <div>
      <PageHeader
        title={`Воронка #${id} — подписчики`}
        subtitle="Кто и когда попал в воронку"
        action={
          <Link href="/funnels"><Button variant="ghost">← К списку</Button></Link>
        }
      />

      <div className="mb-4 inline-flex glass rounded-2xl p-1.5 overflow-x-auto max-w-full">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setStatus(t.key)}
            className={clsx(
              'px-3 sm:px-4 h-9 rounded-xl text-sm whitespace-nowrap transition',
              status === t.key
                ? 'bg-white shadow-soft text-ink'
                : 'text-zinc-600 hover:text-ink hover:bg-white/60',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Подписчиков пока нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[800px]">
              <TableHead>
                <Th>Пользователь</Th>
                <Th>Источник</Th>
                <Th>Старт</Th>
                <Th>Статус</Th>
                <Th>Причина отмены</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((e) => (
                  <Tr key={e.id}>
                    <Td>
                      <Link href={`/users/${e.user_id}`} className="inline-flex items-center gap-2 text-ink hover:text-indigo-600 transition">
                        <span className="shrink-0 size-7 rounded-full gradient-primary text-white text-[11px] font-semibold flex items-center justify-center shadow-soft">
                          {(e.user_first_name || e.user_username || 'U').slice(0, 1).toUpperCase()}
                        </span>
                        <span className="font-medium">
                          {e.user_first_name || (e.user_username ? '@' + e.user_username : `#${e.user_id}`)}
                        </span>
                      </Link>
                    </Td>
                    <Td className="text-zinc-600 text-xs">
                      <SourcePill source={e.source} />
                      {e.source_ref && <span className="ml-2 text-zinc-400">#{e.source_ref}</span>}
                    </Td>
                    <Td className="text-xs text-zinc-500">
                      {new Date(e.started_at).toLocaleString('ru-RU')}
                    </Td>
                    <Td><StatusPill status={e.status} /></Td>
                    <Td className="text-xs text-zinc-500">{e.cancel_reason || '—'}</Td>
                    <Td className="text-right">
                      {e.status === 'active' && (
                        <Button size="sm" variant="danger" onClick={() => cancel(e)}>
                          Отменить
                        </Button>
                      )}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}


function SourcePill({ source }: { source: string }) {
  const map: Record<string, { label: string; color: 'indigo' | 'violet' | 'amber' | 'gray' }> = {
    tracking_link: { label: 'Ссылка', color: 'indigo' },
    code_word: { label: 'Слово', color: 'violet' },
    lead_created: { label: 'Заявка', color: 'amber' },
    manual: { label: 'Вручную', color: 'gray' },
  };
  const cfg = map[source] || { label: source, color: 'gray' as const };
  return <Pill color={cfg.color}>{cfg.label}</Pill>;
}

function StatusPill({ status }: { status: string }) {
  if (status === 'active') return <Pill color="green">активна</Pill>;
  if (status === 'completed') return <Pill color="indigo">завершена</Pill>;
  if (status === 'cancelled') return <Pill color="red">отменена</Pill>;
  return <Pill color="gray">{status}</Pill>;
}

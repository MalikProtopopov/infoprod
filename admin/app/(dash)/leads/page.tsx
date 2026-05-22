'use client';

import Link from 'next/link';
import { useState } from 'react';
import useSWR from 'swr';
import clsx from 'clsx';

import { fetcher } from '@/lib/api';
import { Card, Empty, PageHeader, Pill, TableHead, TableWrap, Td, Th, Tr } from '@/components/ui';

type Lead = {
  id: number;
  status: string;
  created_at: string;
  user_id: number;
  user_telegram_id: number;
  user_username: string | null;
  user_first_name: string | null;
  user_last_name: string | null;
  product_id: number;
  product_name: string;
  channel_title: string;
};

type Resp = { total: number; items: Lead[] };

const TABS: Array<{ key: 'new' | 'contacted' | 'paid' | 'closed' | 'all'; label: string }> = [
  { key: 'new', label: 'Новые' },
  { key: 'contacted', label: 'Связались' },
  { key: 'paid', label: 'Оплачены' },
  { key: 'closed', label: 'Закрытые' },
  { key: 'all', label: 'Все' },
];

export default function LeadsPage() {
  const [status, setStatus] = useState<'all' | 'new' | 'contacted' | 'paid' | 'closed'>('new');
  const { data, isLoading } = useSWR<Resp>(`/leads?status=${status}&limit=200`, fetcher);

  return (
    <div>
      <PageHeader title="Заявки" subtitle="Запросы от пользователей бота — обрабатываются вручную" />

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
        {!isLoading && (!data || data.items.length === 0) && <Empty>Заявок нет</Empty>}
        {data && data.items.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[820px]">
              <TableHead>
                <Th>Дата</Th>
                <Th>Пользователь</Th>
                <Th>Продукт</Th>
                <Th>Канал</Th>
                <Th>Статус</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.items.map((l) => (
                  <Tr key={l.id}>
                    <Td className="text-xs text-zinc-500">{new Date(l.created_at).toLocaleString('ru-RU')}</Td>
                    <Td>
                      <Link href={`/users/${l.user_id}`} className="inline-flex items-center gap-2 text-ink hover:text-indigo-600 transition">
                        <span className="shrink-0 size-7 rounded-full gradient-primary text-white text-[11px] font-semibold flex items-center justify-center shadow-soft">
                          {(l.user_first_name || l.user_username || 'U').slice(0,1).toUpperCase()}
                        </span>
                        <span>
                          {[l.user_first_name, l.user_last_name].filter(Boolean).join(' ') || '—'}
                          {l.user_username && <span className="text-zinc-500 ml-1">@{l.user_username}</span>}
                        </span>
                      </Link>
                    </Td>
                    <Td>{l.product_name}</Td>
                    <Td className="text-zinc-600">{l.channel_title}</Td>
                    <Td><LeadStatusPill s={l.status} /></Td>
                    <Td className="text-right">
                      <Link href={`/leads/${l.id}`} className="text-xs text-indigo-600 hover:text-indigo-800 transition">
                        Открыть →
                      </Link>
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

function LeadStatusPill({ s }: { s: string }) {
  if (s === 'new') return <Pill color="amber">новая</Pill>;
  if (s === 'contacted') return <Pill color="gray">связались</Pill>;
  if (s === 'paid') return <Pill color="green">оплачена</Pill>;
  if (s === 'closed') return <Pill color="red">закрыта</Pill>;
  return <Pill color="gray">{s}</Pill>;
}

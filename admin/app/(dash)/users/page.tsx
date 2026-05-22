'use client';

import Link from 'next/link';
import { useState } from 'react';
import useSWR from 'swr';

import { fetcher } from '@/lib/api';
import { Card, Empty, Input, PageHeader, TableHead, TableWrap, Td, Th, Tr } from '@/components/ui';

type User = {
  id: number;
  telegram_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  first_seen_at: string;
};

type Resp = { total: number; items: User[] };

export default function UsersPage() {
  const [q, setQ] = useState('');
  const { data, isLoading } = useSWR<Resp>(`/users?q=${encodeURIComponent(q)}&limit=100`, fetcher);

  return (
    <div>
      <PageHeader title="Пользователи" subtitle="Все, кто хоть раз нажал /start в боте" />

      <div className="mb-4 max-w-md relative">
        <Input
          placeholder="Поиск по имени, @username или Telegram ID…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="pl-9"
        />
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
        </svg>
      </div>

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.items.length === 0) && <Empty>Пользователи не найдены</Empty>}
        {data && data.items.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[680px]">
              <TableHead>
                <Th>Имя</Th>
                <Th>@username</Th>
                <Th>Telegram ID</Th>
                <Th>Первый визит</Th>
              </TableHead>
              <tbody>
                {data.items.map((u) => (
                  <Tr key={u.id}>
                    <Td>
                      <Link href={`/users/${u.id}`} className="flex items-center gap-3 text-ink hover:text-indigo-600 transition">
                        <span className="shrink-0 size-8 rounded-full gradient-primary text-white text-[11px] font-semibold flex items-center justify-center shadow-soft">
                          {initials(u)}
                        </span>
                        <span className="font-medium">
                          {[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}
                        </span>
                      </Link>
                    </Td>
                    <Td className="text-zinc-600">{u.username ? '@' + u.username : '—'}</Td>
                    <Td className="font-mono text-xs text-zinc-500">{u.telegram_user_id}</Td>
                    <Td className="text-xs text-zinc-500">{new Date(u.first_seen_at).toLocaleString('ru-RU')}</Td>
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

function initials(u: User): string {
  const a = (u.first_name || u.username || '').slice(0, 1).toUpperCase();
  const b = (u.last_name || '').slice(0, 1).toUpperCase();
  return (a + b) || 'U';
}

'use client';

import Link from 'next/link';
import { useState } from 'react';
import useSWR from 'swr';

import { fetcher } from '@/lib/api';
import { Card, Empty, Input, PageHeader, Select, TableHead, TableWrap, Td, Th, Tr } from '@/components/ui';

type UserBot = { bot_id: number; username: string | null; is_blocked: boolean };
type User = {
  id: number;
  telegram_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  first_seen_at: string;
  bots: UserBot[];
};

type Resp = { total: number; items: User[] };
type Bot = { id: number; username: string | null };

export default function UsersPage() {
  const [q, setQ] = useState('');
  const [botId, setBotId] = useState<string>('');
  const { data: bots } = useSWR<Bot[]>('/bots', fetcher);
  const url = `/users?q=${encodeURIComponent(q)}&limit=100${botId ? `&bot_id=${botId}` : ''}`;
  const { data, isLoading } = useSWR<Resp>(url, fetcher);

  return (
    <div>
      <PageHeader title="Пользователи" subtitle="Все, кто хоть раз нажал /start в боте" />

      <div className="mb-4 flex flex-wrap gap-3 items-center">
        <div className="max-w-md relative flex-1 min-w-[240px]">
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
        <div className="w-56">
          <Select value={botId} onChange={(e) => setBotId(e.target.value)}>
            <option value="">Все боты</option>
            {(bots || []).map((b) => (
              <option key={b.id} value={b.id}>{b.username ? '@' + b.username : `бот #${b.id}`}</option>
            ))}
          </Select>
        </div>
      </div>

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.items.length === 0) && <Empty>Пользователи не найдены</Empty>}
        {data && data.items.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[760px]">
              <TableHead>
                <Th>Имя</Th>
                <Th>@username</Th>
                <Th>Боты</Th>
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
                    <Td>
                      <div className="flex flex-wrap gap-1">
                        {(u.bots || []).length === 0 && <span className="text-zinc-400 text-xs">—</span>}
                        {(u.bots || []).map((b) => (
                          <span
                            key={b.bot_id}
                            title={b.is_blocked ? 'заблокировал этого бота' : undefined}
                            className={
                              'inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full ' +
                              (b.is_blocked
                                ? 'bg-rose-50 text-rose-600 line-through'
                                : 'bg-indigo-50 text-indigo-700')
                            }
                          >
                            {b.is_blocked && '🚫'}
                            {b.username ? '@' + b.username : `#${b.bot_id}`}
                          </span>
                        ))}
                      </div>
                    </Td>
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

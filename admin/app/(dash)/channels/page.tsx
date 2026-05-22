'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Select, Sheet,
  TableHead, TableWrap, Td, Th, Tr,
} from '@/components/ui';

type Channel = {
  id: number;
  telegram_chat_id: number;
  title: string;
  username: string | null;
  bot_id: number;
  bot_username: string | null;
  created_at: string;
  products_count: number;
  active_subs_count: number;
};

type Bot = { id: number; username: string; is_active: boolean };

export default function ChannelsPage() {
  const { data, mutate, isLoading } = useSWR<Channel[]>('/channels', fetcher);
  const { data: bots } = useSWR<Bot[]>('/bots', fetcher);

  const [open, setOpen] = useState(false);
  const [botId, setBotId] = useState<number | ''>('');
  const [chatId, setChatId] = useState('');
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeBots = (bots || []).filter((b) => b.is_active);

  async function add() {
    setBusy(true); setError(null);
    try {
      await api.post('/channels', { bot_id: Number(botId), telegram_chat_id: Number(chatId), title: title || null });
      setOpen(false); setBotId(''); setChatId(''); setTitle(''); mutate();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function remove(c: Channel) {
    if (!confirm(`Удалить канал «${c.title}»?`)) return;
    try { await api.del(`/channels/${c.id}`); mutate(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <PageHeader
        title="Каналы"
        subtitle="Закрытые Telegram-каналы, к которым продаётся доступ"
        action={
          <Button onClick={() => setOpen(true)} disabled={activeBots.length === 0}>
            + Добавить канал
          </Button>
        }
      />

      {activeBots.length === 0 && (
        <div className="mb-4 glass rounded-2xl px-4 py-3 text-sm text-amber-700 flex items-center gap-2">
          <span>⚠️</span>
          Сначала добавьте активного бота в разделе «Боты».
        </div>
      )}

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Каналов пока нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[820px]">
              <TableHead>
                <Th>Название</Th>
                <Th>Chat ID</Th>
                <Th>@username</Th>
                <Th>Бот</Th>
                <Th>Продукты</Th>
                <Th>Активных подписок</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((c) => (
                  <Tr key={c.id}>
                    <Td className="font-medium">{c.title}</Td>
                    <Td className="font-mono text-xs text-zinc-600">{c.telegram_chat_id}</Td>
                    <Td className="text-zinc-600">{c.username ? '@' + c.username : '—'}</Td>
                    <Td className="text-zinc-600">@{c.bot_username}</Td>
                    <Td>
                      <Pill color={c.products_count > 0 ? 'violet' : 'gray'}>{c.products_count}</Pill>
                    </Td>
                    <Td>
                      <Pill color={c.active_subs_count > 0 ? 'green' : 'gray'}>{c.active_subs_count}</Pill>
                    </Td>
                    <Td className="text-right">
                      <Button size="sm" variant="danger" onClick={() => remove(c)}>Удалить</Button>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>

      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title="Добавить канал"
        description="Бот должен быть админом канала с правом приглашать участников"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={add} disabled={busy || !botId || !chatId}>{busy ? '…' : 'Добавить'}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Бот" required>
            <Select value={botId} onChange={(e) => setBotId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">Выберите бота</option>
              {activeBots.map((b) => (
                <option key={b.id} value={b.id}>@{b.username}</option>
              ))}
            </Select>
          </Field>
          <Field label="ID канала" hint="Например, -1001234567890. Узнать через @userinfobot или у Telegram API." required>
            <Input value={chatId} onChange={(e) => setChatId(e.target.value)} placeholder="-1001234567890" />
          </Field>
          <Field label="Название" hint="Если оставить пустым — возьмём из Telegram">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          {error && <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>}
        </div>
      </Sheet>
    </div>
  );
}

'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button,
  Card,
  Empty,
  Field,
  Input,
  PageHeader,
  Pill,
  Sheet,
  TableHead,
  TableWrap,
  Td,
  Th,
  Tr,
} from '@/components/ui';

type Bot = {
  id: number;
  telegram_bot_id: number;
  username: string;
  title: string | null;
  is_active: boolean;
  created_at: string;
  token_mask: string;
  channels_count: number;
  products_count: number;
};

export default function BotsPage() {
  const { data, mutate, isLoading } = useSWR<Bot[]>('/bots', fetcher);
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function addBot() {
    setBusy(true); setError(null);
    try {
      await api.post('/bots', { token });
      setOpen(false); setToken(''); mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }
  async function toggle(b: Bot) { await api.patch(`/bots/${b.id}`, { is_active: !b.is_active }); mutate(); }
  async function remove(b: Bot) {
    if (!confirm(`Удалить бота @${b.username}?`)) return;
    try { await api.del(`/bots/${b.id}`); mutate(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <PageHeader
        title="Боты"
        subtitle="Подключённые Telegram‑боты. Один бот может обслуживать несколько каналов."
        action={<Button onClick={() => setOpen(true)}>+ Добавить бота</Button>}
      />

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Ботов пока нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[820px]">
              <TableHead>
                <Th>@username</Th>
                <Th>Telegram ID</Th>
                <Th>Токен</Th>
                <Th>Каналы</Th>
                <Th>Продукты</Th>
                <Th>Статус</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((b) => (
                  <Tr key={b.id}>
                    <Td className="font-medium">@{b.username}</Td>
                    <Td className="font-mono text-xs text-zinc-600">{b.telegram_bot_id}</Td>
                    <Td className="font-mono text-xs text-zinc-500">{b.token_mask}</Td>
                    <Td>
                      <Pill color={b.channels_count > 0 ? 'indigo' : 'gray'}>{b.channels_count}</Pill>
                    </Td>
                    <Td>
                      <Pill color={b.products_count > 0 ? 'violet' : 'gray'}>{b.products_count}</Pill>
                    </Td>
                    <Td>{b.is_active ? <Pill color="green">активен</Pill> : <Pill color="gray">выключен</Pill>}</Td>
                    <Td className="text-right">
                      <div className="inline-flex gap-2">
                        <Button size="sm" variant="ghost" onClick={() => toggle(b)}>
                          {b.is_active ? 'Выключить' : 'Включить'}
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => remove(b)}>Удалить</Button>
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
        open={open}
        onClose={() => setOpen(false)}
        title="Добавить бота"
        description="Создайте бота у @BotFather и вставьте полученный токен"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={addBot} disabled={busy || !token}>{busy ? 'Сохраняем…' : 'Добавить'}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Токен" hint="Формат: 123456:ABC..." required>
            <Input value={token} onChange={(e) => setToken(e.target.value)} placeholder="123456789:AA..." autoFocus />
          </Field>
          {error && <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>}
        </div>
      </Sheet>
    </div>
  );
}

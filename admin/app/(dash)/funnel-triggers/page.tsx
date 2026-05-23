'use client';

import Link from 'next/link';
import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Select, Sheet,
  TableHead, TableWrap, Td, Th, Tr,
} from '@/components/ui';

type Trigger = {
  id: number;
  word: string;
  funnel_id: number;
  funnel_name: string | null;
  is_active: boolean;
  use_count: number;
  created_at: string;
};

type Funnel = { id: number; name: string };

export default function FunnelTriggersPage() {
  const { data, mutate, isLoading } = useSWR<Trigger[]>('/funnel-triggers', fetcher);
  const { data: funnels } = useSWR<Funnel[]>('/funnels', fetcher);

  const [open, setOpen] = useState(false);
  const [word, setWord] = useState('');
  const [funnelId, setFunnelId] = useState<number | ''>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!word.trim() || !funnelId) return;
    setBusy(true); setError(null);
    try {
      await api.post('/funnel-triggers', {
        word: word.trim(),
        funnel_id: Number(funnelId),
      });
      setOpen(false); setWord(''); setFunnelId(''); mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  async function toggle(t: Trigger) {
    await api.patch(`/funnel-triggers/${t.id}`, { is_active: !t.is_active });
    mutate();
  }

  async function remove(t: Trigger) {
    if (!confirm(`Удалить триггер "${t.word}"?`)) return;
    try { await api.del(`/funnel-triggers/${t.id}`); mutate(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <PageHeader
        title="Кодовые слова"
        subtitle="Пользователь пишет слово боту → запускается воронка"
        action={<Button onClick={() => setOpen(true)}>+ Создать слово</Button>}
      />

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Кодовых слов пока нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[680px]">
              <TableHead>
                <Th>Слово</Th>
                <Th>Воронка</Th>
                <Th>Использовано</Th>
                <Th>Статус</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((t) => (
                  <Tr key={t.id}>
                    <Td>
                      <code className="px-2 py-0.5 bg-zinc-100/70 rounded-md text-xs font-medium">{t.word}</code>
                    </Td>
                    <Td>
                      <Link href={`/funnels/${t.funnel_id}/edit`} className="text-indigo-600 hover:underline">
                        {t.funnel_name || `#${t.funnel_id}`}
                      </Link>
                    </Td>
                    <Td>
                      <Pill color={t.use_count > 0 ? 'violet' : 'gray'}>{t.use_count}</Pill>
                    </Td>
                    <Td>
                      {t.is_active
                        ? <Pill color="green">активен</Pill>
                        : <Pill color="gray">выключен</Pill>}
                    </Td>
                    <Td className="text-right">
                      <div className="inline-flex gap-1.5 justify-end">
                        <Button size="sm" variant="ghost" onClick={() => toggle(t)}>
                          {t.is_active ? 'Выключить' : 'Включить'}
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => remove(t)}>Удалить</Button>
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
        title="Создать кодовое слово"
        description="Короткое слово без пробелов. Регистр не важен — система сохраняет в нижнем."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={create} disabled={busy || !word.trim() || !funnelId}>
              {busy ? 'Создаём…' : 'Создать'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Слово" required hint="Например: КЛУБ, ОБУЧЕНИЕ, СТАРТ">
            <Input
              value={word}
              onChange={(e) => setWord(e.target.value)}
              placeholder="старт"
              autoFocus
            />
          </Field>
          <Field label="Воронка" required hint="Какую воронку запустить при получении слова">
            <Select value={funnelId} onChange={(e) => setFunnelId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">— выберите —</option>
              {(funnels || []).map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </Select>
          </Field>
          {error && (
            <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
              {error}
            </div>
          )}
        </div>
      </Sheet>
    </div>
  );
}

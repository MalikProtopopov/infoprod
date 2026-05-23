'use client';

import Link from 'next/link';
import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Select, Sheet,
  TableHead, TableWrap, Td, Textarea, Th, Tr,
} from '@/components/ui';

type Funnel = {
  id: number;
  name: string;
  description: string | null;
  product_id: number;
  bot_id: number | null;
  is_active: boolean;
  ttl_days: number;
  cancel_on_payment: boolean;
  steps_count: number;
  active_entries: number;
  completed_entries: number;
};

type Product = { id: number; name: string; code: string };

export default function FunnelsPage() {
  const { data, mutate, isLoading } = useSWR<Funnel[]>('/funnels', fetcher);
  const { data: products } = useSWR<Product[]>('/products', fetcher);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: '', description: '', product_id: '' as number | '',
    ttl_days: 90, cancel_on_payment: true,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!form.product_id) return;
    setBusy(true); setError(null);
    try {
      const created = await api.post<Funnel>('/funnels', {
        name: form.name.trim(),
        description: form.description.trim() || null,
        product_id: Number(form.product_id),
        ttl_days: Number(form.ttl_days),
        cancel_on_payment: form.cancel_on_payment,
        steps: [],
      });
      setOpen(false);
      setForm({ name: '', description: '', product_id: '', ttl_days: 90, cancel_on_payment: true });
      mutate();
      // переходим в редактор
      window.location.href = `/funnels/${created.id}/edit`;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  async function remove(f: Funnel) {
    if (!confirm(`Удалить воронку "${f.name}"?`)) return;
    try { await api.del(`/funnels/${f.id}`); mutate(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <PageHeader
        title="Воронки"
        subtitle="Цепочки follow-up сообщений с лидмагнитами и кнопкой отписки"
        action={<Button onClick={() => setOpen(true)}>+ Создать воронку</Button>}
      />

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Воронок пока нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[860px]">
              <TableHead>
                <Th>Название</Th>
                <Th>Шагов</Th>
                <Th>Активных</Th>
                <Th>Завершено</Th>
                <Th>TTL</Th>
                <Th>Auto-cancel</Th>
                <Th>Статус</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((f) => (
                  <Tr key={f.id}>
                    <Td className="font-medium">
                      <Link href={`/funnels/${f.id}/edit`} className="hover:text-indigo-600 transition">
                        {f.name}
                      </Link>
                      {f.description && (
                        <div className="text-xs text-zinc-500 mt-0.5 truncate max-w-[260px]">{f.description}</div>
                      )}
                    </Td>
                    <Td><Pill color={f.steps_count > 0 ? 'indigo' : 'gray'}>{f.steps_count}</Pill></Td>
                    <Td><Pill color={f.active_entries > 0 ? 'green' : 'gray'}>{f.active_entries}</Pill></Td>
                    <Td className="text-zinc-600">{f.completed_entries}</Td>
                    <Td className="text-zinc-600">{f.ttl_days} дн.</Td>
                    <Td>
                      {f.cancel_on_payment
                        ? <Pill color="violet">да</Pill>
                        : <Pill color="gray">нет</Pill>}
                    </Td>
                    <Td>
                      {f.is_active
                        ? <Pill color="green">активна</Pill>
                        : <Pill color="gray">выключена</Pill>}
                    </Td>
                    <Td className="text-right">
                      <div className="inline-flex gap-1.5 flex-wrap justify-end">
                        <Link href={`/funnels/${f.id}/edit`}>
                          <Button size="sm" variant="ghost">Редакт.</Button>
                        </Link>
                        <Link href={`/funnels/${f.id}/entries`}>
                          <Button size="sm" variant="ghost">Подписчики</Button>
                        </Link>
                        <Button size="sm" variant="danger" onClick={() => remove(f)}>Удалить</Button>
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
        title="Создать воронку"
        description="Основные параметры — шаги добавляются в редакторе после создания"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={create} disabled={busy || !form.name.trim() || !form.product_id}>
              {busy ? 'Создаём…' : 'Создать'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Название" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Воронка А: Клиентский клуб" autoFocus />
          </Field>
          <Field label="Описание" hint="Внутренняя заметка для админа">
            <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} />
          </Field>
          <Field label="Продукт" required hint="Воронка привязана к одному продукту">
            <Select value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value ? Number(e.target.value) : '' })}>
              <option value="">— выберите —</option>
              {(products || []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="TTL, дней" hint="Сколько хранить активной">
              <Input
                type="number"
                min={1}
                max={365}
                value={form.ttl_days}
                onChange={(e) => setForm({ ...form, ttl_days: Number(e.target.value) })}
              />
            </Field>
            <Field label="Auto-cancel" hint="Отменять при оплате продукта">
              <Select
                value={form.cancel_on_payment ? 'yes' : 'no'}
                onChange={(e) => setForm({ ...form, cancel_on_payment: e.target.value === 'yes' })}
              >
                <option value="yes">Да</option>
                <option value="no">Нет</option>
              </Select>
            </Field>
          </div>
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

'use client';

import Link from 'next/link';
import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Select, Sheet,
  TableHead, TableWrap, Td, Textarea, Th, Tr,
} from '@/components/ui';
import { RichTextEditor } from '@/components/RichTextEditor';
import { ProductContentEditor } from '@/components/ProductContentEditor';

type Product = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  cover_url: string | null;
  channel_id: number;
  channel_title: string | null;
  price_3m: string;
  price_6m: string;
  price_12m: string;
  currency: string;
  is_active: boolean;
  default_funnel_id: number | null;
  card_text: string | null;
  thank_you_message: string | null;
  presentation_enabled: boolean;
};

type Channel = { id: number; title: string };
type Funnel = { id: number; name: string; product_id: number };

export default function ProductsPage() {
  const { data, mutate, isLoading } = useSWR<Product[]>('/products', fetcher);
  const { data: channels } = useSWR<Channel[]>('/channels', fetcher);
  const { data: funnels } = useSWR<Funnel[]>('/funnels', fetcher);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [contentFor, setContentFor] = useState<Product | null>(null);
  const [form, setForm] = useState({
    code: '', name: '', description: '', cover_url: '',
    channel_id: '' as number | '',
    price_3m: '0', price_6m: '0', price_12m: '0',
    currency: 'RUB', is_active: true,
    default_funnel_id: '' as number | '',
    card_text: '', thank_you_message: '', presentation_enabled: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function openCreate() {
    setEditing(null);
    setForm({
      code: '', name: '', description: '', cover_url: '',
      channel_id: '', price_3m: '0', price_6m: '0', price_12m: '0',
      currency: 'RUB', is_active: true, default_funnel_id: '',
      card_text: '', thank_you_message: '', presentation_enabled: true,
    });
    setError(null); setOpen(true);
  }

  function openEdit(p: Product) {
    setEditing(p);
    setForm({
      code: p.code, name: p.name, description: p.description ?? '',
      cover_url: p.cover_url ?? '', channel_id: p.channel_id,
      price_3m: p.price_3m, price_6m: p.price_6m, price_12m: p.price_12m,
      currency: p.currency, is_active: p.is_active,
      default_funnel_id: p.default_funnel_id ?? '',
      card_text: p.card_text ?? '', thank_you_message: p.thank_you_message ?? '',
      presentation_enabled: p.presentation_enabled,
    });
    setError(null); setOpen(true);
  }

  async function save() {
    setBusy(true); setError(null);
    const payload: Record<string, unknown> = {
      code: form.code,
      name: form.name,
      description: form.description || null,
      cover_url: form.cover_url || null,
      channel_id: Number(form.channel_id),
      price_3m: form.price_3m,
      price_6m: form.price_6m,
      price_12m: form.price_12m,
      currency: form.currency || 'RUB',
      is_active: form.is_active,
    };
    // default_funnel_id и контент-поля — только в update (на create продукта ещё нет)
    if (editing) {
      payload.default_funnel_id = form.default_funnel_id ? Number(form.default_funnel_id) : null;
      payload.card_text = form.card_text || null;
      payload.thank_you_message = form.thank_you_message || null;
      payload.presentation_enabled = form.presentation_enabled;
    }
    try {
      if (editing) await api.patch(`/products/${editing.id}`, payload);
      else await api.post('/products', payload);
      setOpen(false); mutate();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function remove(p: Product) {
    if (!confirm(`Удалить продукт «${p.name}»?`)) return;
    try { await api.del(`/products/${p.id}`); mutate(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  function formatPrices(p: Product): string {
    const parts: string[] = [];
    for (const [label, raw] of [['3м', p.price_3m], ['6м', p.price_6m], ['12м', p.price_12m]] as const) {
      const n = Number(raw);
      if (Number.isFinite(n) && n > 0) parts.push(`${label}: ${formatPriceShort(raw)}`);
    }
    return parts.length ? parts.join(' • ') + ' ' + p.currency : '— цена не указана';
  }

  return (
    <div>
      <PageHeader
        title="Продукты"
        subtitle="Карточки предложений с описанием и ценами по периодам"
        action={
          <Button onClick={openCreate} disabled={!channels || channels.length === 0}>
            + Добавить продукт
          </Button>
        }
      />

      {channels && channels.length === 0 && (
        <div className="mb-4 glass rounded-2xl px-4 py-3 text-sm text-amber-700 flex items-center gap-2">
          <span>⚠️</span>
          Сначала добавьте хотя бы один канал.
        </div>
      )}

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Продуктов пока нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[760px]">
              <TableHead>
                <Th>Код</Th>
                <Th>Название</Th>
                <Th>Канал</Th>
                <Th>Цены</Th>
                <Th>Активен</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((p) => (
                  <Tr key={p.id}>
                    <Td className="font-mono text-xs text-zinc-600">{p.code}</Td>
                    <Td className="font-medium">{p.name}</Td>
                    <Td className="text-zinc-600">{p.channel_title}</Td>
                    <Td className="text-xs text-zinc-600">{formatPrices(p)}</Td>
                    <Td>{p.is_active ? <Pill color="green">да</Pill> : <Pill color="gray">нет</Pill>}</Td>
                    <Td className="text-right">
                      <div className="inline-flex gap-2">
                        <Link href={`/products/${p.id}`}>
                          <Button size="sm" variant="ghost">Ссылки</Button>
                        </Link>
                        <Button size="sm" variant="ghost" onClick={() => openEdit(p)}>Изм.</Button>
                        <Button size="sm" variant="danger" onClick={() => remove(p)}>Удалить</Button>
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
        size="lg"
        title={editing ? 'Редактировать продукт' : 'Новый продукт'}
        description="Цены за период; 0 означает «период не для продажи»."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={save} disabled={busy || !form.code || !form.name || !form.channel_id}>
              {busy ? '…' : 'Сохранить'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Код" hint="A–Z, 0–9, -, _" required>
              <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </Field>
            <Field label="Канал" required>
              <Select
                value={form.channel_id}
                onChange={(e) => setForm({ ...form, channel_id: e.target.value ? Number(e.target.value) : '' })}
              >
                <option value="">Выберите канал</option>
                {(channels || []).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Название" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Описание">
            <Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <Field label="URL обложки" hint="Прямая ссылка на картинку (необязательно)">
            <Input value={form.cover_url} onChange={(e) => setForm({ ...form, cover_url: e.target.value })} placeholder="https://…" />
          </Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="3 мес.">
              <Input value={form.price_3m} onChange={(e) => setForm({ ...form, price_3m: e.target.value })} />
            </Field>
            <Field label="6 мес.">
              <Input value={form.price_6m} onChange={(e) => setForm({ ...form, price_6m: e.target.value })} />
            </Field>
            <Field label="12 мес.">
              <Input value={form.price_12m} onChange={(e) => setForm({ ...form, price_12m: e.target.value })} />
            </Field>
          </div>
          <Field label="Валюта">
            <Input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} />
          </Field>

          {editing && (
            <Field label="Воронка по умолчанию" hint="Запустится автоматически когда пользователь оставит заявку на этот продукт">
              <Select
                value={form.default_funnel_id}
                onChange={(e) => setForm({ ...form, default_funnel_id: e.target.value ? Number(e.target.value) : '' })}
              >
                <option value="">— нет —</option>
                {(funnels || [])
                  .filter((f) => f.product_id === editing.id)
                  .map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
              </Select>
            </Field>
          )}

          <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="size-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-400"
            />
            <span>Активен</span>
          </label>

          {editing && (
            <div className="space-y-4 pt-3 border-t border-zinc-100">
              <div className="text-xs uppercase tracking-wide text-zinc-500 font-medium">Контент в боте</div>
              <Field label="Текст карточки" hint="Стили: жирный, цитата (в т.ч. раскрывающаяся), спойлер. Если пусто — авто-карточка с ценами.">
                <RichTextEditor rows={4} value={form.card_text} onChange={(v) => setForm({ ...form, card_text: v })} placeholders={['first_name', 'username']} />
              </Field>
              <Field label="Благодарственное сообщение" hint="Отправится после успешной покупки">
                <RichTextEditor rows={3} value={form.thank_you_message} onChange={(v) => setForm({ ...form, thank_you_message: v })} placeholders={['first_name', 'username']} />
              </Field>
              <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.presentation_enabled}
                  onChange={(e) => setForm({ ...form, presentation_enabled: e.target.checked })}
                  className="size-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-400" />
                <span>Показывать презентацию (блоки) при открытии продукта</span>
              </label>
              <div>
                <Button variant="glass" onClick={() => setContentFor(editing)}>🎬 Блоки презентации</Button>
                <p className="mt-1 text-xs text-zinc-500">Кружок, видео, галерея фото, голос + текст — последовательно, как «живой» менеджер.</p>
              </div>
            </div>
          )}

          {error && <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>}
        </div>
      </Sheet>

      {contentFor && (
        <Sheet
          open
          onClose={() => setContentFor(null)}
          title={`Блоки презентации — ${contentFor.name}`}
          description="Последовательность сообщений при открытии продукта в боте. Перетаскивайте порядок стрелками."
          footer={<Button variant="ghost" onClick={() => setContentFor(null)}>Закрыть</Button>}
        >
          <ProductContentEditor productId={contentFor.id} />
        </Sheet>
      )}
    </div>
  );
}

function formatPriceShort(s: string): string {
  const n = Number(s);
  if (!Number.isFinite(n)) return s;
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

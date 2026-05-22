'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Sheet,
  TableHead, TableWrap, Td, Textarea, Th, Tr, Select,
} from '@/components/ui';

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
};

type Bot = { id: number; username: string };

type TrackingLink = {
  id: number;
  slug: string;
  url: string;
  product: { id: number; code: string; name: string };
  bot: { id: number; username: string } | null;
  utm_source: string;
  utm_medium: string | null;
  utm_campaign: string | null;
  utm_content: string | null;
  notes: string | null;
  is_active: boolean;
  click_count: number;
  unique_users: number;
  leads_count: number;
  payments_count: number;
  revenue: string;
  created_at: string;
};

const MEDIUM_PRESETS = ['reels', 'post', 'story', 'story_ads', 'video', 'email', 'другое'];

export default function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: product } = useSWR<Product>(`/products/${id}`, fetcher);
  const { data: links, mutate: mutateLinks } = useSWR<TrackingLink[]>(
    `/tracking-links?product_id=${id}&limit=200`,
    fetcher,
  );
  const { data: bots } = useSWR<Bot[]>('/bots', fetcher);

  const [createOpen, setCreateOpen] = useState(false);
  const [createdLink, setCreatedLink] = useState<TrackingLink | null>(null);
  const [copyMsg, setCopyMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    utm_source: '',
    utm_medium: '',
    utm_campaign: '',
    notes: '',
    custom_slug: '',
    bot_id: '' as number | '',
    show_advanced: false,
  });

  if (!product) return <div className="text-sm text-zinc-500">Загрузка…</div>;

  const directUrl = bots && bots.length > 0
    ? `https://t.me/${bots[0].username}?start=${product.code}`
    : `https://t.me/<bot>?start=${product.code}`;

  function resetForm() {
    setForm({
      utm_source: '', utm_medium: '', utm_campaign: '', notes: '', custom_slug: '',
      bot_id: bots && bots.length === 1 ? bots[0].id : '',
      show_advanced: false,
    });
    setError(null);
    setCreatedLink(null);
  }

  function openCreate() {
    resetForm();
    setCreateOpen(true);
  }

  async function createLink() {
    setBusy(true); setError(null);
    try {
      const body: Record<string, unknown> = {
        product_id: Number(id),
        utm_source: form.utm_source.trim(),
      };
      if (form.utm_medium) body.utm_medium = form.utm_medium;
      if (form.utm_campaign) body.utm_campaign = form.utm_campaign;
      if (form.notes) body.notes = form.notes;
      if (form.bot_id) body.bot_id = Number(form.bot_id);
      if (form.show_advanced && form.custom_slug) body.custom_slug = form.custom_slug;
      const link = await api.post<TrackingLink>('/tracking-links', body);
      setCreatedLink(link);
      mutateLinks();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function copy(text: string, msg = 'Скопировано') {
    try {
      await navigator.clipboard.writeText(text);
      setCopyMsg(msg);
      setTimeout(() => setCopyMsg(null), 2000);
    } catch {
      setCopyMsg('Не получилось скопировать');
      setTimeout(() => setCopyMsg(null), 2000);
    }
  }

  async function deactivate(l: TrackingLink) {
    if (!confirm(`Деактивировать ссылку ${l.slug}? Существующая атрибуция в leads/payments сохранится.`)) return;
    await api.del(`/tracking-links/${l.id}`);
    mutateLinks();
  }

  return (
    <div>
      <PageHeader
        title={product.name}
        subtitle={`Код: ${product.code} · Канал: ${product.channel_title}`}
        action={
          <Link href="/products"><Button variant="ghost">← К списку</Button></Link>
        }
      />

      {/* Прямая ссылка */}
      <Card padded className="mb-5 anim-rise">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-indigo-500" /> Прямая ссылка (без отслеживания)
        </h3>
        <div className="flex flex-col sm:flex-row gap-2 items-stretch">
          <Input value={directUrl} readOnly className="font-mono text-xs flex-1" />
          <Button variant="ghost" onClick={() => copy(directUrl, 'Прямая ссылка скопирована')}>Скопировать</Button>
        </div>
        <p className="mt-2 text-xs text-zinc-500">Используйте для прямого шеринга. Без UTM, без источника.</p>
      </Card>

      {/* Трекинговые ссылки */}
      <Card padded className="anim-rise">
        <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
          <h3 className="font-semibold flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-violet-500" /> Трекинговые ссылки
          </h3>
          <Button onClick={openCreate}>+ Создать ссылку с источником</Button>
        </div>

        {!links && <div className="p-4 text-sm text-zinc-500">Загрузка…</div>}
        {links && links.length === 0 && <Empty>Ссылок ещё нет</Empty>}
        {links && links.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[860px]">
              <TableHead>
                <Th>Slug</Th>
                <Th>Источник</Th>
                <Th>Кампания</Th>
                <Th>Клики</Th>
                <Th>Уник.</Th>
                <Th>Заявок</Th>
                <Th>Оплат</Th>
                <Th>Выручка</Th>
                <Th>Статус</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {links.map((l) => (
                  <Tr key={l.id}>
                    <Td className="font-mono text-xs">{l.slug}</Td>
                    <Td>{l.utm_source}{l.utm_medium && <span className="text-zinc-500"> / {l.utm_medium}</span>}</Td>
                    <Td className="text-zinc-600">{l.utm_campaign || '—'}</Td>
                    <Td>{l.click_count}</Td>
                    <Td>{l.unique_users}</Td>
                    <Td>{l.leads_count}</Td>
                    <Td>{l.payments_count}</Td>
                    <Td className="font-medium">{Number(l.revenue).toLocaleString('ru-RU')}</Td>
                    <Td>{l.is_active ? <Pill color="green">активна</Pill> : <Pill color="gray">выключена</Pill>}</Td>
                    <Td className="text-right">
                      <div className="inline-flex gap-1.5 flex-wrap justify-end">
                        <Button size="sm" variant="ghost" onClick={() => copy(l.url, `URL ${l.slug} скопирован`)}>
                          Копировать
                        </Button>
                        <a
                          href={`/api/tracking-links/${l.id}/qr.png`}
                          target="_blank"
                          rel="noreferrer"
                          download={`qr-${l.slug}.png`}
                          className="inline-flex items-center justify-center h-8 px-3 text-xs font-medium rounded-xl glass-soft text-ink hover:bg-white/80 transition"
                        >
                          QR
                        </a>
                        {l.is_active && (
                          <Button size="sm" variant="danger" onClick={() => deactivate(l)}>Деакт.</Button>
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

      {copyMsg && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 glass-strong rounded-xl px-4 py-2 text-sm anim-fade">
          {copyMsg}
        </div>
      )}

      {/* Sheet — создание ссылки / результат */}
      <Sheet
        open={createOpen}
        onClose={() => { setCreateOpen(false); resetForm(); }}
        title={createdLink ? 'Ссылка создана' : 'Новая трекинговая ссылка'}
        description={createdLink ? undefined : 'UTM-поля и slug нельзя будет изменить после создания'}
        footer={
          createdLink ? (
            <>
              <Button variant="ghost" onClick={() => { resetForm(); }}>+ Ещё одну</Button>
              <Button onClick={() => { setCreateOpen(false); resetForm(); }}>Закрыть</Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>Отмена</Button>
              <Button onClick={createLink} disabled={busy || !form.utm_source.trim()}>
                {busy ? '…' : 'Сгенерировать'}
              </Button>
            </>
          )
        }
      >
        {createdLink ? (
          <div className="space-y-4">
            <div className="glass rounded-xl p-4">
              <div className="text-xs text-zinc-500 uppercase tracking-wide mb-1">URL</div>
              <div className="font-mono text-sm break-all">{createdLink.url}</div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Button onClick={() => copy(createdLink.url, 'URL скопирован')}>Скопировать ссылку</Button>
              <a
                href={`/api/tracking-links/${createdLink.id}/qr.png`}
                target="_blank"
                rel="noreferrer"
                download={`qr-${createdLink.slug}.png`}
              >
                <Button variant="glass" className="w-full">Скачать QR-код</Button>
              </a>
            </div>
            <div className="text-xs text-zinc-500 space-y-0.5">
              <div>Slug: <code>{createdLink.slug}</code></div>
              <div>Источник: <code>{createdLink.utm_source}</code>{createdLink.utm_medium && <> / <code>{createdLink.utm_medium}</code></>}</div>
              {createdLink.utm_campaign && <div>Кампания: <code>{createdLink.utm_campaign}</code></div>}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Field label="Источник (utm_source)" hint="Например: instagram, youtube, tg_chat_marketing" required>
              <Input
                list="utm-sources"
                value={form.utm_source}
                onChange={(e) => setForm({ ...form, utm_source: e.target.value })}
                autoFocus
                placeholder="instagram"
              />
              <datalist id="utm-sources">
                {Array.from(new Set((links || []).map((l) => l.utm_source))).map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </Field>
            <Field label="Канал/способ (utm_medium)">
              <Select
                value={form.utm_medium}
                onChange={(e) => setForm({ ...form, utm_medium: e.target.value })}
              >
                <option value="">— не указан —</option>
                {MEDIUM_PRESETS.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </Select>
            </Field>
            <Field label="Кампания (utm_campaign)">
              <Input
                value={form.utm_campaign}
                onChange={(e) => setForm({ ...form, utm_campaign: e.target.value })}
                placeholder="spring_2026, black_friday, launch_day_1"
              />
            </Field>
            <Field label="Заметка">
              <Textarea
                rows={2}
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </Field>
            {bots && bots.length > 1 && (
              <Field label="Бот">
                <Select
                  value={form.bot_id}
                  onChange={(e) => setForm({ ...form, bot_id: e.target.value ? Number(e.target.value) : '' })}
                >
                  <option value="">— по умолчанию —</option>
                  {bots.map((b) => <option key={b.id} value={b.id}>@{b.username}</option>)}
                </Select>
              </Field>
            )}

            <button
              type="button"
              className="text-xs text-indigo-600 hover:text-indigo-800 transition"
              onClick={() => setForm({ ...form, show_advanced: !form.show_advanced })}
            >
              {form.show_advanced ? '− Скрыть' : '+ Расширенные настройки'}
            </button>
            {form.show_advanced && (
              <Field label="Custom slug" hint="[A-Za-z0-9_-]{4,64}. Пусто = автогенерация">
                <Input
                  value={form.custom_slug}
                  onChange={(e) => setForm({ ...form, custom_slug: e.target.value })}
                  placeholder="например, yogasale"
                />
              </Field>
            )}

            {error && (
              <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
                {error}
              </div>
            )}
          </div>
        )}
      </Sheet>
    </div>
  );
}

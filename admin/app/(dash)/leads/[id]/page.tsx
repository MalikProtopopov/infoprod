'use client';

import Link from 'next/link';
import { use, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { Button, Card, PageHeader, Pill, Select } from '@/components/ui';

type LeadDetail = {
  id: number;
  status: string;
  created_at: string;
  user_id: number;
  user_telegram_id: number;
  user_username: string | null;
  user_first_name: string | null;
  user_last_name: string | null;
  user_language: string | null;
  user_phone: string | null;
  user_email: string | null;
  user_notes: string | null;
  product_id: number;
  product_code: string;
  product_name: string;
  product_description: string | null;
  product_currency: string;
  product_price_3m: string;
  product_price_6m: string;
  product_price_12m: string;
  channel_id: number;
  channel_title: string;
};

export default function LeadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, mutate } = useSWR<LeadDetail>(`/leads/${id}`, fetcher);
  const [busy, setBusy] = useState(false);

  if (!data) return <div className="text-sm text-zinc-500">Загрузка…</div>;

  async function setStatus(next: string) {
    setBusy(true);
    try { await api.patch(`/leads/${id}`, { status: next }); await mutate(); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!confirm(`Удалить заявку #${id}?`)) return;
    await api.del(`/leads/${id}`);
    window.location.href = '/leads';
  }

  const fullName = [data.user_first_name, data.user_last_name].filter(Boolean).join(' ') || '—';
  const prices = formatPrices(data);

  return (
    <div>
      <PageHeader
        title={`Заявка #${data.id}`}
        subtitle={`От ${fullName}${data.user_username ? ' · @' + data.user_username : ''} · ${new Date(data.created_at).toLocaleString('ru-RU')}`}
        action={
          <>
            <Select
              value={data.status}
              onChange={(e) => setStatus(e.target.value)}
              disabled={busy}
              className="!w-auto"
            >
              <option value="new">новая</option>
              <option value="contacted">связались</option>
              <option value="paid">оплачена</option>
              <option value="closed">закрыта</option>
            </Select>
            <Button variant="danger" onClick={remove}>Удалить</Button>
          </>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card padded className="anim-rise">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-indigo-500" /> Сводка
          </h3>
          <dl className="text-sm space-y-1.5">
            <Row label="Статус"><StatusPill s={data.status} /></Row>
            <Row label="Создана">{new Date(data.created_at).toLocaleString('ru-RU')}</Row>
            <Row label="Канал">{data.channel_title}</Row>
            <Row label="Продукт">
              <Link className="text-indigo-600 hover:underline" href={`/products`}>{data.product_name}</Link>
            </Row>
            <Row label="Код продукта"><code className="text-xs">{data.product_code}</code></Row>
          </dl>
        </Card>

        <Card padded className="anim-rise">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-violet-500" /> Пользователь Telegram
          </h3>
          <dl className="text-sm space-y-1.5">
            <Row label="Имя">{fullName}</Row>
            <Row label="@username">{data.user_username ? '@' + data.user_username : '—'}</Row>
            <Row label="Telegram ID"><code className="text-xs">{data.user_telegram_id}</code></Row>
            <Row label="Язык">{data.user_language || '—'}</Row>
            <Row label="Телефон">{data.user_phone || '—'}</Row>
            <Row label="Email">{data.user_email || '—'}</Row>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href={`/users/${data.user_id}`}>
              <Button size="sm" variant="ghost">Открыть карточку</Button>
            </Link>
            {data.user_username && (
              <a href={`https://t.me/${data.user_username}`} target="_blank" rel="noreferrer">
                <Button size="sm" variant="glass">Telegram ↗</Button>
              </a>
            )}
          </div>
        </Card>
      </div>

      <Card padded className="mt-5 anim-rise">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-rose-500" /> Продукт
        </h3>
        <div className="text-sm space-y-2">
          <div className="font-medium text-base">{data.product_name}</div>
          {data.product_description && (
            <div className="text-zinc-700 whitespace-pre-line">{data.product_description}</div>
          )}
          <div className="pt-1">
            <span className="text-xs uppercase tracking-wide text-zinc-500 mr-2">Цены:</span>
            {prices.length > 0 ? (
              <span className="text-ink font-medium">{prices.join(' · ')} {data.product_currency}</span>
            ) : (
              <span className="text-zinc-500">не указаны</span>
            )}
          </div>
        </div>
      </Card>

      {data.user_notes && (
        <Card padded className="mt-5 anim-rise">
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-teal-500" /> Заметки администратора о пользователе
          </h3>
          <div className="text-sm whitespace-pre-line text-zinc-700">{data.user_notes}</div>
        </Card>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 border-b border-zinc-100/80 py-1.5">
      <dt className="text-zinc-500 text-xs uppercase tracking-wide">{label}</dt>
      <dd className="text-zinc-900 text-right">{children}</dd>
    </div>
  );
}

function StatusPill({ s }: { s: string }) {
  if (s === 'new') return <Pill color="amber">новая</Pill>;
  if (s === 'contacted') return <Pill color="gray">связались</Pill>;
  if (s === 'paid') return <Pill color="green">оплачена</Pill>;
  if (s === 'closed') return <Pill color="red">закрыта</Pill>;
  return <Pill color="gray">{s}</Pill>;
}

function formatPrices(d: LeadDetail): string[] {
  const out: string[] = [];
  const pairs: Array<[string, string]> = [
    ['3 мес', d.product_price_3m],
    ['6 мес', d.product_price_6m],
    ['12 мес', d.product_price_12m],
  ];
  for (const [label, raw] of pairs) {
    const n = Number(raw);
    if (Number.isFinite(n) && n > 0) out.push(`${label}: ${n.toLocaleString('ru-RU')}`);
  }
  return out;
}

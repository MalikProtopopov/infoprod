'use client';

import Link from 'next/link';
import { use, useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { Button, Card, Field, Input, PageHeader, Pill, Select, Sheet } from '@/components/ui';
import { MediaThumb, UploadProgress } from '@/components/MediaThumb';

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
  product_id: number | null;
  product_code: string | null;
  product_name: string | null;
  product_description: string | null;
  product_currency: string | null;
  product_price_3m: string | null;
  product_price_6m: string | null;
  product_price_12m: string | null;
  extra_data: Record<string, unknown> | null;
  channel_id: number | null;
  channel_title: string | null;
  payment_id: number | null;
  payment_amount: string | null;
  payment_currency: string | null;
  cancel_reason: string | null;
  cancelled_at: string | null;
};

type Payment = {
  id: number;
  amount: string;
  currency: string;
  period_months: number;
  created_at: string;
};

const STATUS_LABELS: Record<string, string> = {
  new: 'новая', contacted: 'связались', paid: 'оплачена', closed: 'завершена', cancelled: 'отменена',
};
const PAYMENT_STATUSES = ['paid', 'closed'];

export default function LeadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, mutate } = useSWR<LeadDetail>(`/leads/${id}`, fetcher);
  const [busy, setBusy] = useState(false);
  const [payModal, setPayModal] = useState<null | 'paid' | 'closed'>(null);
  const [cancelOpen, setCancelOpen] = useState(false);

  if (!data) return <div className="text-sm text-zinc-500">Загрузка…</div>;

  async function patchStatus(next: string, extra: Record<string, unknown> = {}) {
    setBusy(true);
    try { await api.patch(`/leads/${id}`, { status: next, ...extra }); await mutate(); }
    finally { setBusy(false); }
  }

  function onStatusSelect(next: string) {
    if (next === data!.status) return;
    if (PAYMENT_STATUSES.includes(next)) {
      // уже есть привязанный платёж — статус можно сменить сразу
      if (data!.payment_id) patchStatus(next);
      else setPayModal(next as 'paid' | 'closed');
    } else if (next === 'cancelled') {
      setCancelOpen(true);
    } else {
      patchStatus(next);
    }
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
            <Select value={data.status} onChange={(e) => onStatusSelect(e.target.value)} disabled={busy} className="!w-auto">
              <option value="new">новая</option>
              <option value="contacted">связались</option>
              <option value="paid">оплачена</option>
              <option value="closed">завершена</option>
              <option value="cancelled">отменена</option>
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
            <Row label="Канал">{data.channel_title ?? <span className="text-zinc-400">— без канала —</span>}</Row>
            <Row label="Продукт">
              {data.product_id
                ? <Link className="text-indigo-600 hover:underline" href={`/products/${data.product_id}`}>{data.product_name}</Link>
                : <span className="text-zinc-400">— без продукта —</span>}
            </Row>
            {data.product_code && <Row label="Код продукта"><code className="text-xs">{data.product_code}</code></Row>}
            {typeof data.extra_data?.text === 'string' && data.extra_data?.source === 'free_text' && (
              <Row label="Сообщение">
                <span className="text-zinc-900">{data.extra_data.text as string}</span>
              </Row>
            )}
            {data.payment_id && (
              <Row label="Платёж">
                <span className="text-emerald-700 font-medium">
                  {data.payment_amount} {data.payment_currency}
                </span>{' '}
                <span className="text-xs text-zinc-500">#{data.payment_id}</span>
              </Row>
            )}
            {data.status === 'cancelled' && data.cancel_reason && (
              <Row label="Причина отмены"><span className="text-rose-700">{data.cancel_reason}</span></Row>
            )}
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
            <Row label="Телефон">{data.user_phone || '—'}</Row>
            <Row label="Email">{data.user_email || '—'}</Row>
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href={`/users/${data.user_id}`}><Button size="sm" variant="ghost">Открыть карточку</Button></Link>
            {data.user_username && (
              <a href={`https://t.me/${data.user_username}`} target="_blank" rel="noreferrer">
                <Button size="sm" variant="glass">Telegram ↗</Button>
              </a>
            )}
          </div>
        </Card>
      </div>

      {data.product_id && (
      <Card padded className="mt-5 anim-rise">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <span className="size-1.5 rounded-full bg-rose-500" /> Продукт
        </h3>
        <div className="text-sm space-y-2">
          <div className="font-medium text-base">{data.product_name}</div>
          {data.product_description && <div className="text-zinc-700 whitespace-pre-line">{data.product_description}</div>}
          <div className="pt-1">
            <span className="text-xs uppercase tracking-wide text-zinc-500 mr-2">Цены:</span>
            {prices.length > 0
              ? <span className="text-ink font-medium">{prices.join(' · ')} {data.product_currency}</span>
              : <span className="text-zinc-500">не указаны</span>}
          </div>
        </div>
      </Card>
      )}

      {payModal && (
        <PaymentModal
          targetStatus={payModal}
          lead={data}
          onClose={() => setPayModal(null)}
          onDone={async () => { setPayModal(null); await mutate(); }}
        />
      )}
      {cancelOpen && (
        <CancelModal
          leadId={data.id}
          onClose={() => setCancelOpen(false)}
          onDone={async () => { setCancelOpen(false); await mutate(); }}
        />
      )}
    </div>
  );
}

/* ---------- Модалка: привязка/создание платежа для paid/closed ---------- */
function PaymentModal({
  targetStatus, lead, onClose, onDone,
}: {
  targetStatus: 'paid' | 'closed';
  lead: LeadDetail;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const { data: payments } = useSWR<Payment[]>(
    `/payments?user_id=${lead.user_id}&product_id=${lead.product_id}`, fetcher,
  );
  const has = (payments?.length ?? 0) > 0;
  const [mode, setMode] = useState<'link' | 'create'>('link');
  const [linkId, setLinkId] = useState<number | ''>('');
  const [period, setPeriod] = useState<3 | 6 | 12>(3);
  const [amount, setAmount] = useState('');
  const [receipt, setReceipt] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const receiptPreview = useMemo(() => (receipt ? URL.createObjectURL(receipt) : null), [receipt]);
  useEffect(() => () => { if (receiptPreview) URL.revokeObjectURL(receiptPreview); }, [receiptPreview]);

  // если платежей нет — сразу режим создания
  const effMode = has ? mode : 'create';
  const statusLabel = targetStatus === 'paid' ? 'оплачена' : 'завершена';

  async function confirm() {
    setBusy(true); setError(null);
    try {
      let paymentId: number;
      if (effMode === 'link') {
        if (!linkId) { setError('Выберите платёж'); setBusy(false); return; }
        paymentId = Number(linkId);
      } else {
        if (!receipt) { setError('Приложите чек — он обязателен'); setBusy(false); return; }
        const form = new FormData();
        form.append('user_id', String(lead.user_id));
        form.append('product_id', String(lead.product_id));
        form.append('period_months', String(period));
        if (amount.trim()) form.append('amount', amount.trim());
        form.append('receipts', receipt);
        setProgress(0);
        const created = await api.postFormProgress<Payment>('/payments', form, setProgress);
        paymentId = created.id;
      }
      await api.patch(`/leads/${lead.id}`, { status: targetStatus, payment_id: paymentId });
      await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); setProgress(null); }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title={`Статус «${statusLabel}» требует платёж`}
      description="Привяжите существующий платёж или создайте новый. Новый платёж выдаёт доступ в канал и отправляет ссылку пользователю."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button onClick={confirm} disabled={busy || (effMode === 'create' && !receipt)}>{busy ? '…' : 'Подтвердить'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        {has && (
          <div className="inline-flex rounded-xl bg-zinc-100/80 p-1 text-sm">
            <button type="button" onClick={() => setMode('link')}
              className={'px-3 h-8 rounded-lg ' + (effMode === 'link' ? 'bg-white shadow-soft font-medium' : 'text-zinc-500')}>
              Привязать существующий
            </button>
            <button type="button" onClick={() => setMode('create')}
              className={'px-3 h-8 rounded-lg ' + (effMode === 'create' ? 'bg-white shadow-soft font-medium' : 'text-zinc-500')}>
              Создать платёж
            </button>
          </div>
        )}

        {effMode === 'link' ? (
          <Field label="Существующий платёж этого пользователя">
            <Select value={linkId === '' ? '' : String(linkId)} onChange={(e) => setLinkId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">— выберите платёж —</option>
              {(payments || []).map((p) => (
                <option key={p.id} value={p.id}>
                  #{p.id} · {p.amount} {p.currency} · {p.period_months} мес. · {new Date(p.created_at).toLocaleDateString('ru-RU')}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <>
            <Field label="Период">
              <Select value={String(period)} onChange={(e) => setPeriod(Number(e.target.value) as 3 | 6 | 12)}>
                <option value="3">3 мес — {lead.product_price_3m} {lead.product_currency}</option>
                <option value="6">6 мес — {lead.product_price_6m} {lead.product_currency}</option>
                <option value="12">12 мес — {lead.product_price_12m} {lead.product_currency}</option>
              </Select>
            </Field>
            <Field label="Сумма" hint="Пусто = цена продукта за период">
              <Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="напр. 2990" inputMode="decimal" />
            </Field>
            <Field label="Чек" hint="Обязательно — подтверждение оплаты" required>
              {receipt ? (
                <div className="flex items-center gap-2 text-sm bg-zinc-100 rounded-lg p-1.5 w-fit">
                  <MediaThumb url={receiptPreview} mime={receipt.type} filename={receipt.name} size={40} />
                  <span className="max-w-[200px] truncate">{receipt.name}</span>
                  <button type="button" onClick={() => setReceipt(null)} className="size-4 inline-flex items-center justify-center rounded-full text-zinc-500 hover:bg-zinc-200" aria-label="Убрать">×</button>
                </div>
              ) : (
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <span className="inline-flex items-center justify-center h-9 px-4 rounded-xl glass-soft text-ink text-sm font-medium hover:bg-white/80 transition">+ Прикрепить чек</span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) setReceipt(f); e.target.value = ''; }}
                  />
                </label>
              )}
            </Field>
          </>
        )}

        {progress !== null && <UploadProgress percent={progress} />}
        {error && (
          <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>
        )}
      </div>
    </Sheet>
  );
}

/* ---------- Модалка: причина отмены ---------- */
function CancelModal({
  leadId, onClose, onDone,
}: {
  leadId: number;
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const { data } = useSWR<{ presets: string[] }>('/leads/cancel-reasons', fetcher);
  const presets = useMemo(() => data?.presets ?? [], [data]);
  const [choice, setChoice] = useState<string>('');
  const [custom, setCustom] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reason = choice === '__custom__' ? custom.trim() : choice;

  async function confirm() {
    if (!reason) { setError('Выберите или укажите причину'); return; }
    setBusy(true); setError(null);
    try {
      await api.patch(`/leads/${leadId}`, { status: 'cancelled', cancel_reason: reason });
      await onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title="Причина отмены"
      description="Выберите частую причину или укажите свою — это поможет видеть статистику отказов в дашборде."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button variant="danger" onClick={confirm} disabled={busy}>{busy ? '…' : 'Отменить заявку'}</Button>
        </>
      }
    >
      <div className="space-y-2">
        {presets.map((p) => (
          <label key={p} className="flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-white/60 cursor-pointer text-sm">
            <input type="radio" name="reason" value={p} checked={choice === p} onChange={() => setChoice(p)} />
            <span>{p}</span>
          </label>
        ))}
        <label className="flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-white/60 cursor-pointer text-sm">
          <input type="radio" name="reason" value="__custom__" checked={choice === '__custom__'} onChange={() => setChoice('__custom__')} />
          <span>Своя причина</span>
        </label>
        {choice === '__custom__' && (
          <Input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="Укажите причину" autoFocus maxLength={500} />
        )}
        {error && (
          <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>
        )}
      </div>
    </Sheet>
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
  if (s === 'closed') return <Pill color="green">завершена</Pill>;
  if (s === 'cancelled') return <Pill color="red">отменена</Pill>;
  return <Pill color="gray">{STATUS_LABELS[s] || s}</Pill>;
}

function formatPrices(d: LeadDetail): string[] {
  const out: string[] = [];
  const pairs: Array<[string, string | null]> = [
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

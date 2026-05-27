'use client';

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Select, Sheet,
  TableHead, TableWrap, Td, Th, Tr,
} from '@/components/ui';
import { UserPicker, type PickedUser } from '@/components/UserPicker';

type Receipt = {
  id: number;
  mime_type: string;
  is_image: boolean;
  original_filename: string | null;
  created_at: string;
};

type Payment = {
  id: number;
  user_id: number;
  user_username: string | null;
  user_first_name: string | null;
  product_id: number;
  product_name: string | null;
  period_months: number;
  amount: string;
  currency: string;
  comment: string | null;
  created_at: string;
  receipts: Receipt[];
};

type Product = {
  id: number;
  name: string;
  price_3m: string;
  price_6m: string;
  price_12m: string;
  currency: string;
};

const receiptUrl = (paymentId: number, receiptId: number) =>
  `/api/payments/${paymentId}/receipts/${receiptId}/file`;

const MAX_RECEIPTS = 3;

export default function PaymentsPage() {
  const { data, mutate, isLoading } = useSWR<Payment[]>('/payments', fetcher);
  const { data: products } = useSWR<Product[]>('/products', fetcher);

  const [open, setOpen] = useState(false);
  const [pickedUser, setPickedUser] = useState<PickedUser | null>(null);
  const [productId, setProductId] = useState<number | ''>('');
  const [period, setPeriod] = useState<3 | 6 | 12>(3);
  const [amount, setAmount] = useState<string>('');
  const [comment, setComment] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receiptsFor, setReceiptsFor] = useState<Payment | null>(null);
  const [newReceipts, setNewReceipts] = useState<File[]>([]); // чеки, выбранные при создании

  const selectedProduct = useMemo(
    () => (products || []).find((p) => p.id === productId),
    [products, productId],
  );

  useEffect(() => {
    if (!selectedProduct) return;
    const priceField = `price_${period}m` as 'price_3m' | 'price_6m' | 'price_12m';
    if (Number(selectedProduct[priceField]) <= 0) {
      for (const m of [3, 6, 12] as const) {
        const f = `price_${m}m` as 'price_3m' | 'price_6m' | 'price_12m';
        if (Number(selectedProduct[f]) > 0) {
          setPeriod(m); setAmount(String(selectedProduct[f]));
          return;
        }
      }
    }
    setAmount(String(selectedProduct[priceField]));
  }, [selectedProduct, period]);

  // держим открытую шторку чеков в синхроне со свежими данными
  const liveReceiptsFor = useMemo(
    () => (receiptsFor ? (data || []).find((p) => p.id === receiptsFor.id) ?? receiptsFor : null),
    [receiptsFor, data],
  );

  function openModal() {
    setPickedUser(null); setProductId(''); setPeriod(3);
    setAmount(''); setComment(''); setError(null); setNewReceipts([]); setOpen(true);
  }

  async function save() {
    if (!pickedUser) return;
    setBusy(true); setError(null);
    try {
      const created = await api.post<{ id: number }>('/payments', {
        user_id: pickedUser.id,
        product_id: Number(productId),
        period_months: period,
        amount: amount || null,
        comment: comment || null,
      });
      // Платёж создан — теперь подгружаем выбранные чеки (нужен payment_id).
      let failed = 0;
      for (const f of newReceipts.slice(0, MAX_RECEIPTS)) {
        try {
          const form = new FormData();
          form.append('file', f);
          await api.postForm(`/payments/${created.id}/receipts`, form);
        } catch { failed += 1; }
      }
      setOpen(false); mutate();
      if (failed > 0) {
        alert(`Платёж создан, но ${failed} чек(ов) не загрузились. Добавьте их через колонку «Чек».`);
      }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function remove(p: Payment) {
    if (!confirm(`Удалить платёж #${p.id}? Связанная подписка будет отозвана.`)) return;
    await api.del(`/payments/${p.id}`); mutate();
  }

  return (
    <div>
      <PageHeader
        title="Платежи"
        subtitle="Фиксация оплат — автоматически выдаёт invite-ссылку клиенту"
        action={<Button onClick={openModal}>+ Добавить платёж</Button>}
      />

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Платежей пока нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[940px]">
              <TableHead>
                <Th>Дата</Th>
                <Th>Пользователь</Th>
                <Th>Продукт</Th>
                <Th>Период</Th>
                <Th>Сумма</Th>
                <Th>Чек</Th>
                <Th>Комментарий</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((p) => (
                  <Tr key={p.id}>
                    <Td className="text-xs text-zinc-500">{new Date(p.created_at).toLocaleString('ru-RU')}</Td>
                    <Td>
                      {p.user_first_name || '—'}
                      {p.user_username && <span className="text-zinc-500 ml-1">@{p.user_username}</span>}
                    </Td>
                    <Td>{p.product_name}</Td>
                    <Td>{p.period_months} мес.</Td>
                    <Td className="font-semibold">
                      {Number(p.amount).toLocaleString('ru-RU')}
                      <span className="text-zinc-500 text-xs ml-1">{p.currency}</span>
                    </Td>
                    <Td><ReceiptCell payment={p} onOpen={() => setReceiptsFor(p)} /></Td>
                    <Td className="text-xs text-zinc-500 max-w-[200px] truncate">{p.comment || '—'}</Td>
                    <Td className="text-right">
                      <Button size="sm" variant="danger" onClick={() => remove(p)}>Удалить</Button>
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
        title="Новый платёж"
        description="После сохранения бот пришлёт клиенту одноразовую invite-ссылку"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={save} disabled={busy || !pickedUser || !productId}>
              {busy ? '…' : 'Сохранить'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Пользователь" hint="Начните вводить имя, @username или Telegram ID" required>
            <UserPicker value={pickedUser} onChange={setPickedUser} autoFocus />
          </Field>
          <Field label="Продукт" required>
            <Select value={productId} onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">Выберите продукт</option>
              {(products || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
          </Field>
          <Field label="Период" hint="Периоды без цены у продукта (= 0) скрыты">
            <Select value={period} onChange={(e) => setPeriod(Number(e.target.value) as 3 | 6 | 12)}>
              {(['3', '6', '12'] as const).map((m) => {
                const priceField = `price_${m}m` as 'price_3m' | 'price_6m' | 'price_12m';
                const price = selectedProduct ? Number(selectedProduct[priceField]) : 0;
                const labelTxt = `${m} ${m === '3' ? 'месяца' : 'месяцев'}`;
                if (!selectedProduct) return <option key={m} value={Number(m)}>{labelTxt}</option>;
                if (!Number.isFinite(price) || price <= 0) return null;
                return (
                  <option key={m} value={Number(m)}>
                    {labelTxt} — {price.toLocaleString('ru-RU')} {selectedProduct.currency}
                  </option>
                );
              })}
            </Select>
          </Field>
          <Field label="Сумма" hint="По умолчанию подставится цена продукта за выбранный период">
            <Input value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
          <Field label="Комментарий">
            <Input value={comment} onChange={(e) => setComment(e.target.value)} />
          </Field>
          <Field label="Чек (необязательно)" hint="До 3 файлов: jpg/png/webp/gif или PDF. Можно добавить и позже из колонки «Чек».">
            {newReceipts.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {newReceipts.map((f, i) => (
                  <span key={i} className="inline-flex items-center gap-1.5 bg-zinc-100 rounded-lg pl-2 pr-1 py-1 text-xs">
                    <span className="max-w-[160px] truncate">{f.name}</span>
                    <button
                      type="button"
                      onClick={() => setNewReceipts((prev) => prev.filter((_, idx) => idx !== i))}
                      className="size-4 inline-flex items-center justify-center rounded-full text-zinc-500 hover:bg-zinc-200"
                      aria-label="Убрать"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
            {newReceipts.length < MAX_RECEIPTS && (
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <span className="inline-flex items-center justify-center h-9 px-4 rounded-xl glass-soft text-ink text-sm font-medium hover:bg-white/80 transition">
                  + Прикрепить чек
                </span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    const picked = Array.from(e.target.files ?? []);
                    setNewReceipts((prev) => [...prev, ...picked].slice(0, MAX_RECEIPTS));
                    e.target.value = '';
                  }}
                />
              </label>
            )}
          </Field>
          {error && (
            <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
              {error}
            </div>
          )}
        </div>
      </Sheet>

      {liveReceiptsFor && (
        <ReceiptsSheet
          payment={liveReceiptsFor}
          onClose={() => setReceiptsFor(null)}
          onChanged={mutate}
        />
      )}
    </div>
  );
}

/* ---------- Ячейка чеков в строке: мини-превью + счётчик ---------- */
function ReceiptCell({ payment, onOpen }: { payment: Payment; onOpen: () => void }) {
  const list = payment.receipts ?? [];
  const images = list.filter((r) => r.is_image);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="inline-flex items-center gap-1.5 rounded-lg px-1.5 py-1 hover:bg-white/70 transition"
      title="Чеки платежа"
    >
      {list.length === 0 ? (
        <span className="text-xs text-indigo-600">+ чек</span>
      ) : (
        <>
          {images.slice(0, 2).map((r) => (
            <img
              key={r.id}
              src={receiptUrl(payment.id, r.id)}
              alt="чек"
              className="size-8 rounded-md object-cover border border-zinc-200"
            />
          ))}
          <span className="inline-flex items-center justify-center min-w-[18px] h-5 px-1 rounded-full bg-zinc-100 text-[11px] font-medium">
            {list.length}
          </span>
        </>
      )}
    </button>
  );
}

/* ---------- Шторка: чеки платежа (загрузка + галерея) ---------- */
function ReceiptsSheet({
  payment, onClose, onChanged,
}: {
  payment: Payment;
  onClose: () => void;
  onChanged: () => void;
}) {
  const receipts = payment.receipts ?? [];
  const images = receipts.filter((r) => r.is_image);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<number | null>(null);

  async function upload(file: File) {
    setBusy(true); setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      await api.postForm(`/payments/${payment.id}/receipts`, form);
      onChanged();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title={`Чеки платежа #${payment.id}`}
      description="Чеки можно только загрузить (до 3). Редактирование и удаление не предусмотрены."
      footer={<Button variant="ghost" onClick={onClose}>Закрыть</Button>}
    >
      <div className="space-y-4">
        {receipts.length === 0 && <Empty>Чеков пока нет</Empty>}

        {receipts.length > 0 && (
          <div className="grid grid-cols-3 gap-3">
            {receipts.map((r) => (
              <ReceiptTile
                key={r.id}
                paymentId={payment.id}
                receipt={r}
                onOpen={() => {
                  const idx = images.findIndex((im) => im.id === r.id);
                  if (idx >= 0) setLightbox(idx);
                }}
              />
            ))}
          </div>
        )}

        {receipts.length < MAX_RECEIPTS && (
          <div>
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <span className="inline-flex items-center justify-center h-9 px-4 rounded-xl gradient-primary text-white text-sm font-medium shadow-soft">
                {busy ? 'Загрузка…' : '+ Загрузить чек'}
              </span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
                className="hidden"
                disabled={busy}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) upload(f);
                  e.target.value = '';
                }}
              />
            </label>
            <p className="mt-1.5 text-xs text-zinc-500">
              Изображение (jpg/png/webp/gif) или PDF, до 10 МБ. Осталось слотов: {MAX_RECEIPTS - receipts.length}.
            </p>
          </div>
        )}

        {error && (
          <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
            {error}
          </div>
        )}
      </div>

      {lightbox !== null && images.length > 0 && (
        <Lightbox
          images={images.map((r) => receiptUrl(payment.id, r.id))}
          index={lightbox}
          onIndex={setLightbox}
          onClose={() => setLightbox(null)}
        />
      )}
    </Sheet>
  );
}

/* ---------- Плитка чека: превью с hover-зумом / PDF-чип ---------- */
function ReceiptTile({
  paymentId, receipt, onOpen,
}: {
  paymentId: number;
  receipt: Receipt;
  onOpen: () => void;
}) {
  const url = receiptUrl(paymentId, receipt.id);
  if (!receipt.is_image) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="flex flex-col items-center justify-center h-24 rounded-xl border border-zinc-200 bg-zinc-50 hover:bg-white transition text-zinc-600"
        title={receipt.original_filename || 'PDF'}
      >
        <span className="text-2xl">📄</span>
        <span className="text-[11px] mt-1">PDF · открыть</span>
      </a>
    );
  }
  return (
    <div className="relative group">
      <button type="button" onClick={onOpen} className="block w-full" title="Открыть на весь экран">
        <img
          src={url}
          alt="чек"
          className="h-24 w-full rounded-xl object-cover border border-zinc-200 transition group-hover:brightness-95"
        />
        <span className="absolute bottom-1 right-1 text-[10px] bg-black/50 text-white px-1.5 py-0.5 rounded-md opacity-0 group-hover:opacity-100 transition">
          🔍 во весь экран
        </span>
      </button>
      {/* hover-превью покрупнее, по центру экрана */}
      <img
        src={url}
        alt=""
        aria-hidden
        className="hidden group-hover:block fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-40 max-h-[70vh] max-w-[70vw] rounded-xl shadow-2xl pointer-events-none border-4 border-white"
      />
    </div>
  );
}

/* ---------- Полноэкранная галерея ---------- */
function Lightbox({
  images, index, onIndex, onClose,
}: {
  images: string[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
}) {
  const prev = () => onIndex((index - 1 + images.length) % images.length);
  const next = () => onIndex((index + 1) % images.length);
  return (
    <div
      className="fixed inset-0 z-[60] bg-black/85 backdrop-blur-sm flex items-center justify-center anim-fade"
      onClick={onClose}
    >
      <button
        className="absolute top-4 right-4 size-10 rounded-full bg-white/10 text-white text-xl hover:bg-white/20"
        onClick={onClose}
        aria-label="Закрыть"
      >
        ✕
      </button>
      {images.length > 1 && (
        <>
          <button
            className="absolute left-4 size-12 rounded-full bg-white/10 text-white text-2xl hover:bg-white/20"
            onClick={(e) => { e.stopPropagation(); prev(); }}
            aria-label="Назад"
          >
            ‹
          </button>
          <button
            className="absolute right-4 size-12 rounded-full bg-white/10 text-white text-2xl hover:bg-white/20"
            onClick={(e) => { e.stopPropagation(); next(); }}
            aria-label="Вперёд"
          >
            ›
          </button>
        </>
      )}
      <img
        src={images[index]}
        alt="чек"
        className="max-h-[90vh] max-w-[92vw] object-contain rounded-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
      {images.length > 1 && (
        <div className="absolute bottom-5 text-white/80 text-sm">{index + 1} / {images.length}</div>
      )}
    </div>
  );
}

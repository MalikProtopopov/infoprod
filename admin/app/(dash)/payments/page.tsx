'use client';

import { useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Select, Sheet,
  TableHead, TableWrap, Td, Th, Tr,
} from '@/components/ui';
import { UserPicker, type PickedUser } from '@/components/UserPicker';

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
};

type Product = {
  id: number;
  name: string;
  price_3m: string;
  price_6m: string;
  price_12m: string;
  currency: string;
};

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

  function openModal() {
    setPickedUser(null); setProductId(''); setPeriod(3);
    setAmount(''); setComment(''); setError(null); setOpen(true);
  }

  async function save() {
    if (!pickedUser) return;
    setBusy(true); setError(null);
    try {
      await api.post('/payments', {
        user_id: pickedUser.id,
        product_id: Number(productId),
        period_months: period,
        amount: amount || null,
        comment: comment || null,
      });
      setOpen(false); mutate();
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
            <table className="w-full text-sm min-w-[860px]">
              <TableHead>
                <Th>Дата</Th>
                <Th>Пользователь</Th>
                <Th>Продукт</Th>
                <Th>Период</Th>
                <Th>Сумма</Th>
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

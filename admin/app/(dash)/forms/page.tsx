'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Select, Sheet,
  TableHead, TableWrap, Td, Textarea, Th, Tr,
} from '@/components/ui';

type FormBrief = {
  id: number;
  name: string;
  description: string | null;
  product_id: number | null;
  fields_count: number;
  submissions_total: number;
  submissions_completed: number;
  leads_created: number;
  created_at: string;
};

type Product = { id: number; name: string };

export default function FormsPage() {
  const router = useRouter();
  const { data, mutate, isLoading } = useSWR<FormBrief[]>('/forms', fetcher);
  const { data: products } = useSWR<Product[]>('/products', fetcher);

  const productNameById = new Map((products || []).map((p) => [p.id, p.name]));

  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [productId, setProductId] = useState<number | ''>('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    if (!name.trim()) {
      setErr('Введите название');
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const created = await api.post<{ id: number }>('/forms', {
        name: name.trim(),
        description: description.trim() || null,
        product_id: productId === '' ? null : productId,
        fields: [],
      });
      setOpen(false);
      setName('');
      setDescription('');
      setProductId('');
      mutate();
      router.push(`/forms/${created.id}`);
    } catch (e: any) {
      setErr(e?.message || 'Ошибка');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Формы"
        subtitle="Сбор данных от юзера через серию вопросов. Завершение создаёт Lead с extra_data."
        action={<Button onClick={() => setOpen(true)}>+ Новая форма</Button>}
      />

      <Card>
        {isLoading ? (
          <Empty>Загрузка…</Empty>
        ) : !data || data.length === 0 ? (
          <Empty>Пока нет форм. Создайте первую — например, «заявка на разбор».</Empty>
        ) : (
          <TableWrap>
            <table className="w-full text-sm">
              <TableHead>
                <Th>Название</Th>
                <Th>Продукт</Th>
                <Th className="text-right">Полей</Th>
                <Th className="text-right">Начато</Th>
                <Th className="text-right">Завершено</Th>
                <Th className="text-right">Lead'ов</Th>
                <Th className="text-right">% завершения</Th>
              </TableHead>
              <tbody>
                {data.map((f) => {
                  const pct =
                    f.submissions_total > 0
                      ? Math.round((f.submissions_completed / f.submissions_total) * 100)
                      : null;
                  return (
                    <Tr key={f.id} className="cursor-pointer" onClick={() => router.push(`/forms/${f.id}`)}>
                      <Td>
                        <div className="font-medium text-ink">{f.name}</div>
                        {f.description && (
                          <div className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{f.description}</div>
                        )}
                      </Td>
                      <Td>
                        {f.product_id == null ? (
                          <span className="text-zinc-400">—</span>
                        ) : (
                          <span className="text-xs">
                            {productNameById.get(f.product_id) || `#${f.product_id}`}
                          </span>
                        )}
                      </Td>
                      <Td className="text-right tabular-nums">{f.fields_count}</Td>
                      <Td className="text-right tabular-nums">{f.submissions_total}</Td>
                      <Td className="text-right tabular-nums">{f.submissions_completed}</Td>
                      <Td className="text-right tabular-nums">{f.leads_created}</Td>
                      <Td className="text-right">
                        {pct == null ? (
                          <span className="text-zinc-400">—</span>
                        ) : (
                          <Pill color={pct >= 70 ? 'green' : pct >= 40 ? 'amber' : 'red'}>{pct}%</Pill>
                        )}
                      </Td>
                    </Tr>
                  );
                })}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>

      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title="Новая форма"
        description="Создадим пустую — поля можно добавить сразу после."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>
              Отмена
            </Button>
            <Button onClick={create} disabled={busy}>
              {busy ? 'Создаём…' : 'Создать и открыть'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Название" required>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="заявка на разбор"
              autoFocus
            />
          </Field>
          <Field label="Описание" hint="Видно только в админке">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="ФИО, контакт, описание проекта"
            />
          </Field>
          <Field label="Продукт" hint="Опционально — на какой продукт пойдёт Lead">
            <Select
              value={productId === '' ? '' : String(productId)}
              onChange={(e) => setProductId(e.target.value === '' ? '' : Number(e.target.value))}
            >
              <option value="">— без продукта —</option>
              {(products || []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </Field>
          {err && (
            <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
              {err}
            </div>
          )}
        </div>
      </Sheet>
    </div>
  );
}

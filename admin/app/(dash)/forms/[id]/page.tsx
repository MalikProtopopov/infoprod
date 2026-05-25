'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { use, useEffect, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, IconButton, Input, PageHeader, Pill, Select, Skeleton, Textarea,
} from '@/components/ui';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { useToast } from '@/components/Toast';

type FormField = {
  id?: number;
  order_idx?: number;
  key: string;
  question: string;
  prefix: string | null;
  field_type: string;
  required: boolean;
  max_length: number;
};

type FormDetail = {
  id: number;
  name: string;
  description: string | null;
  product_id: number | null;
  success_message: string | null;
  cancel_message: string | null;
  completion_buttons: { text: string; url?: string; callback_data?: string }[][] | null;
  fields: FormField[];
  created_at: string;
  updated_at: string;
};

type Product = { id: number; name: string };

const FIELD_TYPES = [
  { value: 'text', label: 'Текст' },
  { value: 'phone', label: 'Телефон' },
  { value: 'email', label: 'Email' },
  { value: 'url', label: 'Ссылка' },
  { value: 'number', label: 'Число' },
];

export default function FormEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { showToast } = useToast();
  const { data, mutate, isLoading } = useSWR<FormDetail>(`/forms/${id}`, fetcher);
  const { data: products } = useSWR<Product[]>('/products', fetcher);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [productId, setProductId] = useState<number | null>(null);
  const [successMessage, setSuccessMessage] = useState('');
  const [cancelMessage, setCancelMessage] = useState('');
  const [fields, setFields] = useState<FormField[]>([]);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!data) return;
    setName(data.name);
    setDescription(data.description || '');
    setProductId(data.product_id);
    setSuccessMessage(data.success_message || '');
    setCancelMessage(data.cancel_message || '');
    setFields(data.fields);
    setDirty(false);
  }, [data]);

  function markDirty() {
    setDirty(true);
  }

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      const cleanFields = fields.map((f, i) => ({
        key: f.key,
        question: f.question,
        prefix: f.prefix,
        field_type: f.field_type,
        required: f.required,
        max_length: Number(f.max_length) || 500,
        order_idx: i,
      }));
      await api.patch(`/forms/${id}`, {
        name,
        description: description || null,
        product_id: productId,
        success_message: successMessage || null,
        cancel_message: cancelMessage || null,
        fields: cleanFields,
      });
      await mutate();
      setDirty(false);
      showToast('Форма сохранена');
    } catch (e: any) {
      setErr(e?.message || 'Не удалось сохранить');
      showToast(e?.message || 'Не удалось сохранить', { type: 'error' });
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      await api.del(`/forms/${id}`);
      showToast('Форма удалена');
      router.push('/forms');
    } catch (e: any) {
      showToast(e?.message || 'Не удалось удалить', { type: 'error' });
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  function addField() {
    setFields((fs) => [
      ...fs,
      {
        key: `field_${fs.length + 1}`,
        question: '',
        prefix: null,
        field_type: 'text',
        required: true,
        max_length: 500,
      },
    ]);
    markDirty();
  }

  function updateField(idx: number, patch: Partial<FormField>) {
    setFields((fs) => fs.map((f, i) => (i === idx ? { ...f, ...patch } : f)));
    markDirty();
  }

  function removeField(idx: number) {
    setFields((fs) => fs.filter((_, i) => i !== idx));
    markDirty();
  }

  function moveField(idx: number, dir: -1 | 1) {
    setFields((fs) => {
      const j = idx + dir;
      if (j < 0 || j >= fs.length) return fs;
      const next = fs.slice();
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
    markDirty();
  }

  if (isLoading || !data) {
    return <FormEditorSkeleton />;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={name || 'Без названия'}
        subtitle={`Полей: ${fields.length}${productId ? ` · продукт #${productId}` : ' · без продукта'}`}
        action={
          <div className="flex gap-2">
            <Link href="/forms" className="text-sm text-zinc-500 hover:text-ink self-center">
              ← К списку
            </Link>
            <Button variant="danger" onClick={() => setConfirmDelete(true)} disabled={saving}>
              Удалить
            </Button>
            <Button onClick={save} disabled={saving || !dirty}>
              {saving ? 'Сохраняем…' : dirty ? 'Сохранить' : 'Сохранено'}
            </Button>
          </div>
        }
      />

      {err && (
        <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
          {err}
        </div>
      )}

      <Card padded className="space-y-4">
        <Field label="Название" required>
          <Input
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              markDirty();
            }}
          />
        </Field>
        <Field label="Описание" hint="Видно только в админке">
          <Textarea
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              markDirty();
            }}
            rows={2}
          />
        </Field>
        <Field label="Продукт" hint="Опционально — Lead создастся с этой привязкой">
          <Select
            value={productId == null ? '' : String(productId)}
            onChange={(e) => {
              setProductId(e.target.value === '' ? null : Number(e.target.value));
              markDirty();
            }}
          >
            <option value="">— без продукта —</option>
            {(products || []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </Field>
      </Card>

      {/* Fields */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Поля</h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              Бот спросит их по очереди. Юзер отвечает текстом в чате.
            </p>
          </div>
          <Button size="sm" variant="ghost" onClick={addField}>
            + Поле
          </Button>
        </div>

        {fields.length === 0 ? (
          <Card padded>
            <Empty>Без полей форма не работает. Добавь хотя бы одно.</Empty>
          </Card>
        ) : (
          fields.map((f, fi) => (
            <Card key={fi} padded className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <Pill color="indigo">Поле {fi + 1}</Pill>
                <div className="flex gap-1">
                  <IconButton onClick={() => moveField(fi, -1)} disabled={fi === 0}>↑</IconButton>
                  <IconButton onClick={() => moveField(fi, 1)} disabled={fi === fields.length - 1}>↓</IconButton>
                  <IconButton onClick={() => removeField(fi)} className="hover:text-rose-600">✕</IconButton>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Field
                  label="Ключ"
                  required
                  hint="Латиница, цифры, _; используется в Lead.extra_data"
                >
                  <Input
                    value={f.key}
                    onChange={(e) => updateField(fi, { key: e.target.value })}
                    placeholder="name"
                  />
                </Field>
                <Field label="Тип">
                  <Select
                    value={f.field_type}
                    onChange={(e) => updateField(fi, { field_type: e.target.value })}
                  >
                    {FIELD_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Max длина">
                  <Input
                    type="number"
                    value={f.max_length}
                    onChange={(e) =>
                      updateField(fi, { max_length: Number(e.target.value) || 500 })
                    }
                  />
                </Field>
              </div>

              <Field label="Вопрос" required>
                <Textarea
                  value={f.question}
                  onChange={(e) => updateField(fi, { question: e.target.value })}
                  rows={2}
                />
              </Field>

              <div className="flex items-center justify-between flex-wrap gap-3">
                <Field label="Префикс" hint="Опционально, выводится над вопросом">
                  <Input
                    value={f.prefix || ''}
                    onChange={(e) => updateField(fi, { prefix: e.target.value || null })}
                    placeholder="например: расскажи о себе"
                  />
                </Field>
                <label className="flex items-center gap-2 cursor-pointer pt-5">
                  <input
                    type="checkbox"
                    checked={f.required}
                    onChange={(e) => updateField(fi, { required: e.target.checked })}
                    className="size-4 rounded accent-indigo-600"
                  />
                  <span className="text-sm">Обязательное</span>
                </label>
              </div>
            </Card>
          ))
        )}
      </section>

      {/* Messages */}
      <Card padded className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">Сообщения бота</h2>
        <Field
          label="Success — после успешной заявки"
          hint="Если пусто — отправится «готово, заявка принята.»"
        >
          <Textarea
            value={successMessage}
            onChange={(e) => {
              setSuccessMessage(e.target.value);
              markDirty();
            }}
            rows={4}
          />
        </Field>
        <Field
          label="Cancel — если юзер нажал «отменить»"
          hint="Если пусто — отправится «Отменено. Когда будешь готов — наберёшь /start.»"
        >
          <Textarea
            value={cancelMessage}
            onChange={(e) => {
              setCancelMessage(e.target.value);
              markDirty();
            }}
            rows={3}
          />
        </Field>
      </Card>

      {dirty && (
        <div className="sticky bottom-3 z-20 flex justify-center">
          <div className="glass-strong rounded-2xl px-4 py-2 shadow-lg flex items-center gap-3">
            <span className="text-sm text-zinc-600">есть несохранённые изменения</span>
            <Button size="sm" onClick={save} disabled={saving}>
              {saving ? 'Сохраняем…' : 'Сохранить'}
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={remove}
        busy={deleting}
        title="Удалить форму?"
        description={
          <>
            Уже созданные <b>Lead'ы и история заявок</b> сохранятся —
            мы храним <code>extra_data</code> на каждом лиде. Но новые попытки
            заполнить форму будут отказаны, и привязки шагов воронок к этой форме оборвутся.
          </>
        }
        confirmText="Да, удалить"
      />
    </div>
  );
}


function FormEditorSkeleton() {
  return (
    <div className="space-y-5 anim-fade">
      <div className="flex items-end justify-between gap-3">
        <div className="space-y-2">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-3 w-72" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-20" />
          <Skeleton className="h-10 w-24" />
        </div>
      </div>

      <Card padded className="space-y-3">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-3 w-24 mt-2" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-3 w-20 mt-2" />
        <Skeleton className="h-10 w-full" />
      </Card>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-8 w-20" />
        </div>
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} padded className="space-y-3">
            <Skeleton className="h-5 w-20" />
            <div className="grid grid-cols-3 gap-3">
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
            </div>
            <Skeleton className="h-16 w-full" />
          </Card>
        ))}
      </div>

      <Card padded className="space-y-3">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-3 w-32 mt-2" />
        <Skeleton className="h-20 w-full" />
      </Card>
    </div>
  );
}

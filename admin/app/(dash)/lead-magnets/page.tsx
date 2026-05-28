'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Select, Sheet,
  TableHead, TableWrap, Td, Textarea, Th, Tr,
} from '@/components/ui';
import { MediaThumb, UploadProgress } from '@/components/MediaThumb';

type LeadMagnet = {
  id: number;
  name: string;
  description: string | null;
  file_type: string;
  file_size: number | null;
  product_id: number | null;
  is_active: boolean;
  download_count: number;
  has_telegram_file_id: boolean;
  created_at: string;
};

type Product = { id: number; name: string };

function fmtSize(b: number | null): string {
  if (!b) return '—';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}

const TYPE_EMOJI: Record<string, string> = {
  pdf: '📄',
  image: '🖼️',
  video: '🎬',
  document: '📎',
};

export default function LeadMagnetsPage() {
  const { data, mutate, isLoading } = useSWR<LeadMagnet[]>('/lead-magnets', fetcher);
  const { data: products } = useSWR<Product[]>('/products', fetcher);

  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [productId, setProductId] = useState<number | ''>('');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  function openSheet() {
    setError(null);
    setOpen(true);
  }

  function reset() {
    setFile(null);
    setName('');
    setDescription('');
    setProductId('');
  }

  function pickFile(f: File) {
    setFile(f);
    if (!name) {
      // авто-имя из файла
      const base = f.name.replace(/\.[^/.]+$/, '');
      setName(base);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  }

  async function upload() {
    if (!file || !name.trim()) return;
    setBusy(true); setError(null); setProgress(0);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('name', name.trim());
      if (description.trim()) form.append('description', description.trim());
      if (productId) form.append('product_id', String(productId));
      await api.postFormProgress<LeadMagnet>('/lead-magnets', form, setProgress);
      setOpen(false);
      reset();
      mutate();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); setProgress(null); }
  }

  async function toggle(lm: LeadMagnet) {
    await api.patch(`/lead-magnets/${lm.id}`, { is_active: !lm.is_active });
    mutate();
  }

  async function remove(lm: LeadMagnet) {
    if (!confirm(`Удалить лидмагнит "${lm.name}"?`)) return;
    try { await api.del(`/lead-magnets/${lm.id}`); mutate(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <PageHeader
        title="Лидмагниты"
        subtitle="Файлы, которые бот отправляет пользователям внутри воронок"
        action={<Button onClick={openSheet}>+ Загрузить файл</Button>}
      />

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.length === 0) && <Empty>Лидмагнитов пока нет</Empty>}
        {data && data.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[760px]">
              <TableHead>
                <Th>Файл</Th>
                <Th>Тип</Th>
                <Th>Размер</Th>
                <Th>Продукт</Th>
                <Th>Загрузок</Th>
                <Th>TG cache</Th>
                <Th>Статус</Th>
                <Th className="text-right">Действия</Th>
              </TableHead>
              <tbody>
                {data.map((lm) => (
                  <Tr key={lm.id}>
                    <Td>
                      <div className="flex items-center gap-2.5">
                        <span className="text-xl shrink-0">{TYPE_EMOJI[lm.file_type] || '📎'}</span>
                        <div>
                          <div className="font-medium">{lm.name}</div>
                          {lm.description && (
                            <div className="text-xs text-zinc-500 truncate max-w-[260px]">{lm.description}</div>
                          )}
                        </div>
                      </div>
                    </Td>
                    <Td className="text-xs text-zinc-500 uppercase">{lm.file_type}</Td>
                    <Td className="text-xs text-zinc-600">{fmtSize(lm.file_size)}</Td>
                    <Td className="text-zinc-600">
                      {lm.product_id
                        ? ((products || []).find((p) => p.id === lm.product_id)?.name || `#${lm.product_id}`)
                        : <span className="text-xs text-zinc-400">универсальный</span>}
                    </Td>
                    <Td>
                      <Pill color={lm.download_count > 0 ? 'violet' : 'gray'}>{lm.download_count}</Pill>
                    </Td>
                    <Td>
                      {lm.has_telegram_file_id
                        ? <Pill color="green">кеш</Pill>
                        : <Pill color="gray">нет</Pill>}
                    </Td>
                    <Td>
                      {lm.is_active
                        ? <Pill color="green">активен</Pill>
                        : <Pill color="gray">выкл.</Pill>}
                    </Td>
                    <Td className="text-right">
                      <div className="inline-flex gap-1.5 flex-wrap justify-end">
                        <a href={`/api/lead-magnets/${lm.id}/download`} target="_blank" rel="noreferrer">
                          <Button size="sm" variant="ghost">Скачать</Button>
                        </a>
                        <Button size="sm" variant="ghost" onClick={() => toggle(lm)}>
                          {lm.is_active ? 'Выключить' : 'Включить'}
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => remove(lm)}>Удалить</Button>
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
        title="Загрузить лидмагнит"
        description="PDF, изображение, видео или документ — до 50 МБ"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={upload} disabled={busy || !file || !name.trim()}>
              {busy ? 'Загружаем…' : 'Загрузить'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition ${drag ? 'border-indigo-500 bg-indigo-50/40' : 'border-zinc-300 hover:border-zinc-400'}`}
          >
            {file ? (
              <div className="flex items-center gap-3 text-left">
                <MediaThumb url={previewUrl} mime={file.type} filename={file.name} size={56} />
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate" title={file.name}>{file.name}</div>
                  <div className="text-xs text-zinc-500 mt-0.5">{fmtSize(file.size)} · нажмите, чтобы заменить</div>
                </div>
              </div>
            ) : (
              <div>
                <div className="text-2xl mb-1">📤</div>
                <div className="text-sm">Перетащите файл сюда или кликните</div>
                <div className="text-xs text-zinc-500 mt-0.5">PDF / JPG / PNG / MP4 / документ</div>
              </div>
            )}
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) pickFile(f); }}
            />
          </div>

          {progress !== null && <UploadProgress percent={progress} />}

          <Field label="Название" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Чек-лист утреннего ухода" />
          </Field>
          <Field label="Описание (опц.)">
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </Field>
          <Field label="Привязка к продукту" hint="Если не указано — доступен любой воронке">
            <Select value={productId} onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">— универсальный —</option>
              {(products || []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
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

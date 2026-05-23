'use client';

import { useRef, useState } from 'react';

import { api } from '@/lib/api';
import { Button, Field, Input, Sheet } from '@/components/ui';

type LeadMagnet = { id: number; name: string; file_type: string };

/**
 * Мини-Sheet «Загрузить лидмагнит прямо здесь».
 * Не уходит со страницы воронки — после загрузки колл-бек onUploaded
 * с новым лидмагнитом, чтобы вызывающий код мог сразу его выбрать.
 */
export function QuickLeadMagnetUpload({
  open,
  onClose,
  productId,
  onUploaded,
}: {
  open: boolean;
  onClose: () => void;
  productId?: number;
  onUploaded: (lm: LeadMagnet) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function pickFile(f: File) {
    setFile(f);
    if (!name) setName(f.name.replace(/\.[^/.]+$/, ''));
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  }

  async function upload() {
    if (!file || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('name', name.trim());
      if (productId) form.append('product_id', String(productId));
      const created = await api.postForm<LeadMagnet>('/lead-magnets', form);
      onUploaded(created);
      reset();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setFile(null);
    setName('');
    setError(null);
  }

  return (
    <Sheet
      open={open}
      onClose={() => { reset(); onClose(); }}
      title="Загрузить лидмагнит"
      description="PDF, изображение, видео или документ. До 50 МБ. После загрузки сразу подключится к шагу."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button onClick={upload} disabled={busy || !file || !name.trim()}>
            {busy ? 'Загружаем…' : 'Загрузить и подключить'}
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
          className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition ${
            drag ? 'border-indigo-500 bg-indigo-50/40' : 'border-zinc-300 hover:border-zinc-400'
          }`}
        >
          {file ? (
            <div>
              <div className="text-2xl mb-1">📎</div>
              <div className="text-sm font-medium">{file.name}</div>
              <div className="text-xs text-zinc-500 mt-0.5">{formatSize(file.size)}</div>
            </div>
          ) : (
            <div>
              <div className="text-2xl mb-1">📤</div>
              <div className="text-sm">Перетащите файл или кликните</div>
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

        <Field label="Название" required>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Чек-лист утреннего ухода" />
        </Field>

        {productId && (
          <div className="text-xs text-zinc-500">
            💡 Файл привяжется к продукту этой воронки. Если оставить «универсальным» — будет
            доступен из других воронок тоже. Сейчас по умолчанию привязываем.
          </div>
        )}

        {error && (
          <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
            {error}
          </div>
        )}
      </div>
    </Sheet>
  );
}

function formatSize(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}

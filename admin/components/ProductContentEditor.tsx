'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { Button, Empty, Field, Select } from '@/components/ui';
import { RichTextEditor } from '@/components/RichTextEditor';

type Media = {
  id: number;
  media_type: string;
  is_image: boolean;
  original_filename: string | null;
  caption: string | null;
  order_idx: number;
};
type Block = {
  id: number;
  product_id: number;
  order_idx: number;
  kind: 'text' | 'media' | 'video_note' | 'voice';
  text: string | null;
  delay_ms: number;
  is_active: boolean;
  media: Media[];
};

const KIND_LABEL: Record<Block['kind'], string> = {
  text: '💬 Текст', media: '🖼 Медиа / галерея', video_note: '⭕ Кружок', voice: '🎤 Голос',
};
const ACCEPT: Record<Block['kind'], string> = {
  text: '', media: 'image/*,video/*', video_note: 'video/mp4,video/quicktime', voice: 'audio/*',
};
const mediaUrl = (id: number) => `/api/content-block-media/${id}/file`;

export function ProductContentEditor({ productId }: { productId: number }) {
  const key = `/products/${productId}/content-blocks`;
  const { data: blocks, mutate } = useSWR<Block[]>(key, fetcher);
  const [adding, setAdding] = useState<Block['kind']>('text');
  const [busy, setBusy] = useState(false);

  async function addBlock() {
    setBusy(true);
    try { await api.post(key, { kind: adding, text: adding === 'text' ? '' : null }); await mutate(); }
    finally { setBusy(false); }
  }

  async function move(idx: number, dir: -1 | 1) {
    if (!blocks) return;
    const next = [...blocks];
    const j = idx + dir;
    if (j < 0 || j >= next.length) return;
    [next[idx], next[j]] = [next[j], next[idx]];
    await api.post(`${key}/reorder`, { ordered_ids: next.map((b) => b.id) });
    await mutate();
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Select value={adding} onChange={(e) => setAdding(e.target.value as Block['kind'])} className="!w-auto">
          {(Object.keys(KIND_LABEL) as Block['kind'][]).map((k) => (
            <option key={k} value={k}>{KIND_LABEL[k]}</option>
          ))}
        </Select>
        <Button size="sm" onClick={addBlock} disabled={busy}>+ Добавить блок</Button>
      </div>

      {(!blocks || blocks.length === 0) && <Empty>Блоков ещё нет. Добавьте первый — он отправится при открытии продукта.</Empty>}

      {blocks?.map((b, i) => (
        <BlockCard
          key={b.id}
          block={b}
          isFirst={i === 0}
          isLast={i === blocks.length - 1}
          onMoveUp={() => move(i, -1)}
          onMoveDown={() => move(i, 1)}
          onChanged={mutate}
        />
      ))}
    </div>
  );
}

function BlockCard({
  block, isFirst, isLast, onMoveUp, onMoveDown, onChanged,
}: {
  block: Block; isFirst: boolean; isLast: boolean;
  onMoveUp: () => void; onMoveDown: () => void; onChanged: () => void;
}) {
  const [text, setText] = useState(block.text ?? '');
  const [delay, setDelay] = useState(block.delay_ms);
  const [busy, setBusy] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const dirty = text !== (block.text ?? '') || delay !== block.delay_ms;
  const mediaLimit = block.kind === 'media' ? 10 : 1;

  async function save() {
    setBusy(true);
    try { await api.patch(`/content-blocks/${block.id}`, { text, delay_ms: delay }); await onChanged(); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!confirm('Удалить блок?')) return;
    await api.del(`/content-blocks/${block.id}`); await onChanged();
  }
  async function upload(file: File) {
    setBusy(true); setUploadErr(null);
    try {
      const form = new FormData(); form.append('file', file);
      await api.postForm(`/content-blocks/${block.id}/media`, form);
      await onChanged();
    } catch (e) { setUploadErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  async function removeMedia(mid: number) {
    await api.del(`/content-block-media/${mid}`); await onChanged();
  }

  return (
    <div className="glass rounded-xl p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{KIND_LABEL[block.kind]}</span>
        <div className="flex items-center gap-1">
          <button type="button" disabled={isFirst} onClick={onMoveUp} className="size-7 rounded-lg hover:bg-white/70 disabled:opacity-30">↑</button>
          <button type="button" disabled={isLast} onClick={onMoveDown} className="size-7 rounded-lg hover:bg-white/70 disabled:opacity-30">↓</button>
          <Button size="sm" variant="danger" onClick={remove}>Удалить</Button>
        </div>
      </div>

      {block.kind === 'text' && (
        <RichTextEditor rows={4} value={text} onChange={setText} placeholders={['first_name', 'username']} />
      )}

      {block.kind !== 'text' && (
        <div>
          <div className="flex flex-wrap gap-2 mb-2">
            {block.media.map((m) => (
              <div key={m.id} className="relative">
                {m.is_image ? (
                  <img src={mediaUrl(m.id)} alt="" className="size-16 rounded-lg object-cover border border-zinc-200" />
                ) : (
                  <a href={mediaUrl(m.id)} target="_blank" rel="noreferrer" className="flex size-16 items-center justify-center rounded-lg border border-zinc-200 bg-zinc-50 text-[10px] text-center px-1">
                    {m.media_type}
                  </a>
                )}
                <button type="button" onClick={() => removeMedia(m.id)} className="absolute -top-1.5 -right-1.5 size-5 rounded-full bg-rose-500 text-white text-xs">×</button>
              </div>
            ))}
          </div>
          {block.media.length < mediaLimit && (
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <span className="inline-flex items-center justify-center h-8 px-3 rounded-lg glass-soft text-sm hover:bg-white/80">+ Загрузить файл</span>
              <input type="file" accept={ACCEPT[block.kind]} className="hidden" disabled={busy}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ''; }} />
            </label>
          )}
          {block.kind === 'video_note' && (
            <p className="text-xs text-zinc-500 mt-1">Кружок: загрузите любое видео — оно автоматически обрежется до квадрата и ≤ 60 сек. Без подписи: текст добавьте отдельным текстовым блоком.</p>
          )}
          {(block.kind === 'media' || block.kind === 'voice') && (
            <div className="mt-2">
              <Field label="Подпись (опционально)">
                <RichTextEditor rows={2} value={text} onChange={setText} placeholders={['first_name', 'username']} />
              </Field>
            </div>
          )}
          {uploadErr && <div className="text-xs text-rose-600 mt-1">{uploadErr}</div>}
        </div>
      )}

      <div className="flex items-center gap-3">
        <label className="text-xs text-zinc-500">Задержка, мс:
          <input type="number" min={0} max={10000} value={delay}
            onChange={(e) => setDelay(Number(e.target.value))}
            className="ml-1 w-20 rounded-md border border-zinc-200 px-1.5 py-0.5 text-sm" />
        </label>
        {dirty && <Button size="sm" onClick={save} disabled={busy}>Сохранить блок</Button>}
      </div>
    </div>
  );
}

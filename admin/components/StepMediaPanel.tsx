'use client';

import { useCallback, useRef, useState } from 'react';
import useSWR from 'swr';
import clsx from 'clsx';

import { api, fetcher } from '@/lib/api';
import { useToast } from '@/components/Toast';

/**
 * Панель медиа для одного шага воронки.
 *
 * - Drag-n-drop зона + клик-выбор файла.
 * - Список загруженных медиа с миниатюрами (фото — превью с диска через
 *   /api/funnel-step-media/{id}/file, видео/аудио/документ — иконка по типу).
 * - Reorder через drag-n-drop кнопок в списке.
 * - Per-item caption через инлайн-textarea.
 * - Удаление с подтверждением.
 * - Валидация лимитов на клиенте: ≤10 файлов на шаг, фото ≤10 MB,
 *   остальное ≤50 MB. Backend проверит ещё раз.
 */

export type StepMedia = {
  id: number;
  funnel_step_id: number;
  media_type: 'photo' | 'video' | 'animation' | 'audio' | 'document' | 'voice';
  mime_type: string;
  file_size: number;
  width: number | null;
  height: number | null;
  duration: number | null;
  order_idx: number;
  caption: string | null;
  has_telegram_file_id: boolean;
  has_thumbnail: boolean;
  original_filename: string | null;
  created_at: string;
};

const MEDIA_GROUP_MAX = 10;
const PHOTO_LIMIT = 10 * 1024 * 1024;
const GENERIC_LIMIT = 50 * 1024 * 1024;

const IMAGE_MIMES = new Set(['image/jpeg', 'image/png', 'image/webp']);
const ANIM_MIMES = new Set(['image/gif']);
const VIDEO_MIMES = new Set(['video/mp4', 'video/quicktime', 'video/webm']);
const AUDIO_MIMES = new Set(['audio/mpeg', 'audio/mp4', 'audio/ogg', 'audio/wav']);

function inferType(mime: string): StepMedia['media_type'] {
  if (IMAGE_MIMES.has(mime)) return 'photo';
  if (ANIM_MIMES.has(mime)) return 'animation';
  if (VIDEO_MIMES.has(mime)) return 'video';
  if (AUDIO_MIMES.has(mime)) return 'audio';
  return 'document';
}

function validateFileBeforeUpload(file: File, currentCount: number): string | null {
  if (currentCount >= MEDIA_GROUP_MAX) {
    return `На шаге уже ${MEDIA_GROUP_MAX} медиа — это лимит Telegram media-group`;
  }
  const mediaType = inferType(file.type || '');
  if (mediaType === 'photo' && file.size > PHOTO_LIMIT) {
    return `Фото больше 10 MB не примет Telegram. Загрузите как документ (PDF/архив) или сожмите.`;
  }
  if (file.size > GENERIC_LIMIT) {
    return `Файл больше 50 MB — Telegram Bot API не примет.`;
  }
  return null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function typeIcon(t: StepMedia['media_type']): string {
  return ({
    photo: '🖼',
    video: '🎬',
    animation: '🎞',
    audio: '🎵',
    voice: '🎙',
    document: '📎',
  } as const)[t];
}

function typeBgClass(t: StepMedia['media_type']): string {
  return ({
    photo: 'bg-teal-50 text-teal-700',
    video: 'bg-rose-50 text-rose-700',
    animation: 'bg-fuchsia-50 text-fuchsia-700',
    audio: 'bg-amber-50 text-amber-700',
    voice: 'bg-amber-50 text-amber-700',
    document: 'bg-zinc-100 text-zinc-700',
  } as const)[t];
}

export function StepMediaPanel({ stepId }: { stepId: number }) {
  const { data: media, mutate } = useSWR<StepMedia[]>(
    `/funnel-steps/${stepId}/media`,
    fetcher,
  );
  const { showToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(0);
  const [dragId, setDragId] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<number | null>(null);

  const list = media || [];
  const remaining = MEDIA_GROUP_MAX - list.length;

  const uploadFile = useCallback(
    async (file: File) => {
      const err = validateFileBeforeUpload(file, list.length);
      if (err) {
        showToast(err, { type: 'error', durationMs: 4500 });
        return;
      }
      setUploading((n) => n + 1);
      try {
        const form = new FormData();
        form.append('file', file);
        await api.postForm<StepMedia>(`/funnel-steps/${stepId}/media`, form);
        await mutate();
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Не удалось загрузить файл';
        showToast(msg, { type: 'error', durationMs: 5000 });
      } finally {
        setUploading((n) => n - 1);
      }
    },
    [stepId, list.length, mutate, showToast],
  );

  async function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const files = Array.from(e.dataTransfer.files || []);
    for (const f of files) {
      await uploadFile(f);
    }
  }

  async function onFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    for (const f of files) {
      await uploadFile(f);
    }
    e.target.value = '';
  }

  async function removeMedia(m: StepMedia) {
    if (!confirm(`Удалить ${m.original_filename || 'медиа'}?`)) return;
    try {
      await api.del(`/funnel-step-media/${m.id}`);
      await mutate();
      showToast('Медиа удалено');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Не удалось удалить', { type: 'error' });
    }
  }

  async function updateCaption(m: StepMedia, caption: string) {
    try {
      await api.patch(`/funnel-step-media/${m.id}`, { caption: caption || null });
      await mutate();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Caption не сохранён', { type: 'error' });
    }
  }

  async function reorder(targetId: number) {
    if (dragId === null || dragId === targetId) return;
    const ids = list.map((m) => m.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) return;
    const newIds = [...ids];
    newIds.splice(from, 1);
    newIds.splice(to, 0, dragId);
    setDragId(null);
    setDropTarget(null);
    // Optimistic update
    const next = newIds.map((id, idx) => {
      const m = list.find((mm) => mm.id === id)!;
      return { ...m, order_idx: idx };
    });
    await mutate(next, false);
    try {
      await api.patch(`/funnel-steps/${stepId}/media/reorder`, { ordered_ids: newIds });
      await mutate();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Reorder не удался', { type: 'error' });
      await mutate(); // откат
    }
  }

  return (
    <div className="space-y-3">
      {/* Drop-zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (remaining > 0) setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => remaining > 0 && inputRef.current?.click()}
        className={clsx(
          'border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition text-sm',
          remaining === 0 && 'opacity-50 cursor-not-allowed',
          drag ? 'border-indigo-500 bg-indigo-50/40' : 'border-zinc-300 hover:border-zinc-400',
        )}
      >
        {remaining === 0 ? (
          <div className="text-zinc-500">
            Достигнут лимит {MEDIA_GROUP_MAX} файлов на шаг (Telegram media-group)
          </div>
        ) : (
          <>
            <div className="text-lg mb-0.5">📤</div>
            <div className="text-zinc-700">
              {drag ? 'Отпустите файл' : 'Перетащите файл или кликните'}
            </div>
            <div className="text-[11px] text-zinc-400 mt-1">
              JPG / PNG / WEBP до 10 MB · MP4 / MOV / MP3 / PDF до 50 MB · ещё {remaining} файлов
            </div>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept="image/*,video/*,audio/*,application/*"
          multiple
          onChange={onFileInput}
        />
      </div>

      {uploading > 0 && (
        <div className="text-xs text-zinc-500 text-center">
          Загружаю {uploading}…
        </div>
      )}

      {/* Список медиа */}
      {list.length > 0 && (
        <ul className="space-y-2">
          {list.map((m) => {
            const isImage = m.media_type === 'photo' || m.media_type === 'animation';
            const isVideo = m.media_type === 'video';
            const isDropOver = dropTarget === m.id && dragId !== m.id;
            return (
              <li
                key={m.id}
                draggable
                onDragStart={() => setDragId(m.id)}
                onDragEnd={() => { setDragId(null); setDropTarget(null); }}
                onDragOver={(e) => { e.preventDefault(); setDropTarget(m.id); }}
                onDragLeave={() => { if (dropTarget === m.id) setDropTarget(null); }}
                onDrop={() => reorder(m.id)}
                className={clsx(
                  'glass rounded-xl p-2.5 transition',
                  isDropOver && 'border-t-4 border-indigo-500',
                )}
              >
                <div className="flex items-start gap-3">
                  {/* Превью */}
                  <div className="shrink-0 cursor-grab active:cursor-grabbing">
                    {isImage ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={`/api/funnel-step-media/${m.id}/file`}
                        alt=""
                        className="size-16 rounded-lg object-cover bg-zinc-100"
                      />
                    ) : isVideo && m.has_thumbnail ? (
                      <div className="relative size-16 rounded-lg overflow-hidden bg-zinc-900">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`/api/funnel-step-media/${m.id}/thumbnail`}
                          alt=""
                          className="size-16 object-cover"
                        />
                        <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                          <span className="text-white text-lg drop-shadow">▶</span>
                        </div>
                      </div>
                    ) : isVideo ? (
                      <div className="size-16 rounded-lg bg-zinc-900 flex items-center justify-center text-white text-xl">
                        ▶
                      </div>
                    ) : (
                      <div className={clsx('size-16 rounded-lg flex items-center justify-center text-2xl', typeBgClass(m.media_type))}>
                        {typeIcon(m.media_type)}
                      </div>
                    )}
                  </div>

                  {/* Инфо + caption + actions */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate" title={m.original_filename || ''}>
                        {m.original_filename || `Медиа #${m.id}`}
                      </span>
                      {m.has_telegram_file_id && (
                        <span className="shrink-0 text-[9px] uppercase tracking-wider text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
                          tg-cache
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">
                      #{m.order_idx + 1} · {m.media_type} · {formatSize(m.file_size)}
                      {m.width && m.height && ` · ${m.width}×${m.height}`}
                    </div>
                    <textarea
                      defaultValue={m.caption || ''}
                      onBlur={(e) => {
                        if ((e.target.value || '') !== (m.caption || '')) {
                          updateCaption(m, e.target.value);
                        }
                      }}
                      placeholder="Подпись к медиа (опционально)"
                      rows={1}
                      maxLength={1024}
                      className="mt-1.5 w-full text-xs px-2 py-1 rounded-md border border-zinc-200 bg-white/60 resize-y focus:outline-none focus:border-indigo-400"
                    />
                  </div>

                  <button
                    type="button"
                    onClick={() => removeMedia(m)}
                    className="shrink-0 size-7 inline-flex items-center justify-center rounded-md text-zinc-400 hover:text-rose-600 hover:bg-rose-50 transition"
                    title="Удалить медиа"
                  >
                    ✕
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

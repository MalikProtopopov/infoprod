'use client';

import clsx from 'clsx';

/**
 * Универсальное превью медиа + полоса прогресса загрузки.
 *
 * MediaThumb: картинка → <img>; видео (вкл. кружок) → <video> с первым кадром
 * (preload=metadata + #t=0.1); аудио/голос → иконка ноты; остальное → 📎.
 * Работает и для уже загруженных файлов (url с бэкенда, cookie шлётся
 * автоматически), и для только что выбранных локально (URL.createObjectURL).
 */

type Kind = 'image' | 'video' | 'audio' | 'doc';

function classify(type?: string | null, mime?: string | null, filename?: string | null): Kind {
  const t = (type || '').toLowerCase();
  if (t === 'photo' || t === 'image' || t === 'animation') return 'image';
  if (t === 'video' || t === 'video_note') return 'video';
  if (t === 'audio' || t === 'voice') return 'audio';
  const m = (mime || '').toLowerCase();
  if (m.startsWith('image/')) return 'image';
  if (m.startsWith('video/')) return 'video';
  if (m.startsWith('audio/')) return 'audio';
  const ext = (filename || '').toLowerCase().split('.').pop() || '';
  if (['jpg', 'jpeg', 'png', 'webp', 'gif', 'heic', 'bmp'].includes(ext)) return 'image';
  if (['mp4', 'mov', 'webm', 'm4v', 'avi', 'mkv'].includes(ext)) return 'video';
  if (['mp3', 'ogg', 'wav', 'm4a', 'oga', 'opus'].includes(ext)) return 'audio';
  return 'doc';
}

export function MediaThumb({
  url,
  type,
  mime,
  filename,
  size = 64,
  rounded = 'lg',
  className,
}: {
  url?: string | null;
  type?: string | null;
  mime?: string | null;
  filename?: string | null;
  size?: number;
  rounded?: 'lg' | 'full';
  className?: string;
}) {
  const kind = classify(type, mime, filename);
  const isNote = (type || '').toLowerCase() === 'video_note';
  const radius = rounded === 'full' || isNote ? 'rounded-full' : 'rounded-lg';
  const box = clsx('relative overflow-hidden shrink-0 bg-zinc-100', radius, className);
  const style = { width: size, height: size } as const;

  if (kind === 'image' && url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt={filename || ''} className={clsx(box, 'object-cover')} style={style} />;
  }
  if (kind === 'video' && url) {
    return (
      <div className={clsx(box, 'bg-zinc-900')} style={style}>
        <video
          src={`${url}#t=0.1`}
          muted
          playsInline
          preload="metadata"
          className="size-full object-cover"
        />
        <div className="absolute inset-0 flex items-center justify-center bg-black/25 pointer-events-none">
          <span className="text-white text-lg drop-shadow">▶</span>
        </div>
      </div>
    );
  }
  return (
    <div
      className={clsx(box, 'flex items-center justify-center text-2xl', kind === 'audio' ? 'bg-amber-50' : 'bg-zinc-100')}
      style={style}
      title={filename || undefined}
    >
      {kind === 'audio' ? '🎵' : '📎'}
    </div>
  );
}

/**
 * Полоса прогресса загрузки. percent 0..100 — отправка байт; на 100% переходим
 * в «Обработка…» (сервер ещё работает: напр. ffmpeg-квадрат кружка).
 */
export function UploadProgress({ percent, className }: { percent: number; className?: string }) {
  const processing = percent >= 100;
  return (
    <div className={clsx('space-y-1', className)}>
      <div className="flex justify-between text-[11px] text-zinc-500">
        <span>{processing ? 'Обработка на сервере…' : 'Загрузка…'}</span>
        <span>{processing ? '' : `${percent}%`}</span>
      </div>
      <div className="h-1.5 rounded-full bg-zinc-200 overflow-hidden">
        <div
          className={clsx('h-full bg-indigo-500 transition-all duration-150', processing && 'animate-pulse')}
          style={{ width: `${Math.max(4, percent)}%` }}
        />
      </div>
    </div>
  );
}

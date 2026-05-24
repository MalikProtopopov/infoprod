'use client';

import { useMemo } from 'react';

/**
 * Реалтайм-превью того, как сообщение выглядит в Telegram.
 *
 * Рендерит безопасное подмножество Telegram HTML:
 *   <b> <i> <u> <s> <code> <pre> <blockquote> <blockquote expandable>
 *   <tg-spoiler> <a href="…"> <br>
 *
 * - Подставляет {first_name} / {username}
 * - Показывает блок-attachment если указан lead_magnet
 * - Inline-кнопки рендерятся как в TG
 * - Внизу автоматическая «🔕 Не присылать напоминания» (бэкенд добавляет)
 */
type LeadMagnetPreview = { name: string; file_type: string; size?: number | null };

type Btn = { text: string; url?: string; callback_data?: string };
type ButtonRows = Btn[][];

type StepMediaForPreview = {
  id: number;
  media_type: 'photo' | 'video' | 'animation' | 'audio' | 'document' | 'voice';
  original_filename: string | null;
  caption: string | null;
  file_size: number;
};

export function TelegramPreview({
  text,
  leadMagnet,
  buttons,
  botUsername,
  previewName = 'Иван',
  stepMedia,
}: {
  text: string;
  leadMagnet?: LeadMagnetPreview | null;
  buttons?: ButtonRows | null;
  botUsername?: string;
  previewName?: string;
  stepMedia?: StepMediaForPreview[];
}) {
  const rendered = useMemo(() => renderHtml(text, previewName), [text, previewName]);

  return (
    <div className="rounded-2xl bg-[#f1f5f9] dark:bg-[#0f172a] p-3 sm:p-4 ring-1 ring-zinc-200/60">
      {/* Заголовок-имитация чата */}
      <div className="flex items-center gap-2 mb-3">
        <div className="size-7 rounded-full gradient-primary text-white text-[10px] font-bold flex items-center justify-center shadow-soft">
          🤖
        </div>
        <div className="min-w-0">
          <div className="text-xs font-semibold text-ink truncate">
            {botUsername ? `@${botUsername}` : 'YourBot'}
          </div>
          <div className="text-[10px] text-zinc-500">бот · онлайн</div>
        </div>
      </div>

      {/* Bubble: текст */}
      <div className="space-y-2">
        {/* Step media — рендерится первым: 1 медиа = превью + caption,
            ≥2 = grid-альбом, после альбома — текст-сообщение отдельным bubble */}
        {stepMedia && stepMedia.length > 0 && (
          <MediaGroupBubble items={stepMedia} />
        )}

        <div className="bg-white rounded-2xl rounded-tl-md p-3 max-w-[88%] shadow-soft">
          <div
            className="tg-message text-[13.5px] leading-snug text-ink whitespace-pre-wrap break-words"
            dangerouslySetInnerHTML={{ __html: rendered }}
          />
        </div>

        {/* Lead magnet attachment — показываем только если нет step_media (легаси) */}
        {leadMagnet && (!stepMedia || stepMedia.length === 0) && (
          <div className="bg-white rounded-2xl rounded-tl-md p-2.5 max-w-[88%] shadow-soft flex items-center gap-2.5">
            <div className="size-9 rounded-xl bg-indigo-100 flex items-center justify-center text-base shrink-0">
              {EMOJI[leadMagnet.file_type] || '📎'}
            </div>
            <div className="min-w-0">
              <div className="text-[12.5px] font-medium truncate">{leadMagnet.name}</div>
              <div className="text-[10.5px] text-zinc-500">
                {leadMagnet.size ? formatSize(leadMagnet.size) : leadMagnet.file_type.toUpperCase()}
              </div>
            </div>
          </div>
        )}

        {/* Inline-кнопки */}
        {buttons && buttons.length > 0 && (
          <div className="bg-white rounded-2xl rounded-tl-md p-2 max-w-[88%] shadow-soft space-y-1">
            {buttons.map((row, ri) => (
              <div key={ri} className="flex gap-1">
                {row.map((b, bi) => (
                  <div
                    key={bi}
                    className="flex-1 text-center text-[12px] text-indigo-600 py-1.5 px-2 rounded-lg bg-indigo-50/70 truncate"
                    title={b.url || b.callback_data || ''}
                  >
                    {b.text || '(пусто)'}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Кнопка отписки (всегда добавляется системой) */}
        <div className="bg-white/80 rounded-2xl rounded-tl-md p-2 max-w-[88%] shadow-soft">
          <div
            className="text-center text-[12px] text-zinc-500 py-1.5 px-2 rounded-lg bg-zinc-100/80 truncate"
            title="Системная кнопка — добавляется автоматически"
          >
            🔕 Не присылать напоминания
          </div>
        </div>
      </div>

      <div className="mt-3 text-[10.5px] text-zinc-500 text-center">
        Так это увидит пользователь. Имя подставлено из вашего профиля.
      </div>

      <style jsx>{`
        :global(.tg-message b),
        :global(.tg-message strong) { font-weight: 700; }
        :global(.tg-message i),
        :global(.tg-message em) { font-style: italic; }
        :global(.tg-message u) { text-decoration: underline; }
        :global(.tg-message s) { text-decoration: line-through; }
        :global(.tg-message code) {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 0.92em;
          background: #eef2ff;
          color: #3730a3;
          padding: 0 4px;
          border-radius: 4px;
        }
        :global(.tg-message pre) {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 0.86em;
          background: #f1f5f9;
          color: #1e293b;
          padding: 8px 10px;
          border-radius: 8px;
          overflow-x: auto;
          margin: 6px 0;
          white-space: pre;
        }
        :global(.tg-message blockquote) {
          border-left: 3px solid #6366f1;
          padding: 2px 0 2px 10px;
          margin: 4px 0;
          color: #3730a3;
          background: linear-gradient(to right, rgba(99,102,241,0.06), transparent 60%);
          border-radius: 0 6px 6px 0;
        }
        :global(.tg-message blockquote[data-expandable]) {
          position: relative;
        }
        :global(.tg-message blockquote[data-expandable]::after) {
          content: "▾ развернуть";
          display: block;
          margin-top: 2px;
          font-size: 10.5px;
          color: #6366f1;
          opacity: 0.7;
        }
        :global(.tg-message .tg-spoiler) {
          background: linear-gradient(90deg, #475569, #334155);
          color: transparent;
          border-radius: 3px;
          padding: 0 2px;
          cursor: pointer;
          transition: color 0.2s;
        }
        :global(.tg-message .tg-spoiler:hover) {
          color: white;
          background: #475569;
        }
        :global(.tg-message a) {
          color: #6366f1;
          text-decoration: underline;
        }
      `}</style>
    </div>
  );
}

const EMOJI: Record<string, string> = {
  pdf: '📄', image: '🖼️', video: '🎬', document: '📎',
};

const MEDIA_ICON: Record<string, string> = {
  photo: '🖼️',
  video: '🎬',
  animation: '🎞',
  audio: '🎵',
  voice: '🎙',
  document: '📎',
};


/**
 * Превью media-group в стиле Telegram-альбома.
 * - 1 элемент: один большой блок с превью.
 * - 2 элемента: горизонтальная пара.
 * - 3-4 элемента: 2x2 сетка.
 * - 5-10 элементов: 3-колоночный grid.
 *
 * Реальные превью фото мы НЕ грузим (это превью в редакторе — миниатюра
 * подгрузилась бы /api/funnel-step-media/{id}/file, но в TelegramPreview
 * мы абстрактны от backend и держим компонент простым). Используем
 * стилизованные плитки с иконкой типа.
 */
function MediaGroupBubble({ items }: { items: StepMediaForPreview[] }) {
  const n = items.length;
  const cols = n === 1 ? 1 : n === 2 ? 2 : n <= 4 ? 2 : 3;
  const firstCaption = items.find((m) => m.caption)?.caption || null;
  return (
    <div className="bg-white rounded-2xl rounded-tl-md p-2 max-w-[88%] shadow-soft">
      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {items.map((m) => (
          <div
            key={m.id}
            className="aspect-square rounded-md flex items-center justify-center text-2xl bg-gradient-to-br from-zinc-100 to-zinc-200"
            title={`${m.media_type}${m.original_filename ? ' · ' + m.original_filename : ''}`}
          >
            {MEDIA_ICON[m.media_type] || '📎'}
          </div>
        ))}
      </div>
      {firstCaption && (
        <div className="mt-1.5 px-1 text-[12.5px] leading-snug text-ink whitespace-pre-wrap">
          {firstCaption}
        </div>
      )}
    </div>
  );
}

function formatSize(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}

const PLACEHOLDER_VALUES: Record<string, string> = {
  first_name: 'Иван',
  username: 'ivan',
};

/* ─────────── HTML renderer ─────────── */

function renderHtml(text: string, previewName: string): string {
  // 1) escape всё сначала
  let out = escapeHtml(text);

  // 2) re-allow whitelisted simple tags: b, i, u, s, code, pre, br
  out = out.replace(
    /&lt;(\/?(?:b|i|u|s|code|pre|br))&gt;/gi,
    (_, inner: string) => `<${inner}>`,
  );

  // 3) blockquote с опциональным "expandable" атрибутом
  out = out.replace(
    /&lt;blockquote(\s+expandable)?&gt;/gi,
    (_, exp: string | undefined) => (exp ? '<blockquote data-expandable="1">' : '<blockquote>'),
  );
  out = out.replace(/&lt;\/blockquote&gt;/gi, '</blockquote>');

  // 4) tg-spoiler → <span class="tg-spoiler">
  out = out.replace(/&lt;tg-spoiler&gt;/gi, '<span class="tg-spoiler">');
  out = out.replace(/&lt;\/tg-spoiler&gt;/gi, '</span>');
  // также поддержим <span class="tg-spoiler">
  out = out.replace(
    /&lt;span\s+class=&quot;tg-spoiler&quot;&gt;/gi,
    '<span class="tg-spoiler">',
  );

  // 5) <a href="..."> — отдельно, разрешаем только http(s) и tg://
  out = out.replace(/&lt;a\s+href=&quot;([^&]+)&quot;&gt;/gi, (_, url: string) => {
    const cleaned = url.replace(/[<>"']/g, '');
    const safe = /^(https?:|tg:|mailto:)/i.test(cleaned) ? cleaned : '#';
    return `<a href="${safe}">`;
  });
  out = out.replace(/&lt;\/a&gt;/gi, '</a>');

  // 6) подставить плейсхолдеры
  const values: Record<string, string> = { ...PLACEHOLDER_VALUES, first_name: previewName };
  out = out.replace(/\{(\w+)\}/g, (_, key: string) => values[key] || `{${key}}`);

  // 7) перевод строк
  out = out.replace(/\n/g, '<br/>');

  return out;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

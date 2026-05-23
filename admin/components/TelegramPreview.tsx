'use client';

import clsx from 'clsx';
import { useMemo } from 'react';

/**
 * Реалтайм-превью того, как сообщение выглядит в Telegram.
 *
 * - Рендерит безопасное подмножество HTML (b, i, u, s, code, a, br)
 * - Подставляет {first_name} / {username} — берётся из `previewName`
 * - Показывает блок-attachment если указан lead_magnet (имя + emoji-type)
 * - Inline-кнопки рендерятся как в TG
 * - Внизу автоматическая «🔕 Не присылать напоминания» (бэкенд добавляет)
 */
type LeadMagnetPreview = { name: string; file_type: string; size?: number | null };

type Btn = { text: string; url?: string; callback_data?: string };
type ButtonRows = Btn[][];

export function TelegramPreview({
  text,
  leadMagnet,
  buttons,
  botUsername,
  previewName = 'Иван',
}: {
  text: string;
  leadMagnet?: LeadMagnetPreview | null;
  buttons?: ButtonRows | null;
  botUsername?: string;
  previewName?: string;
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
        <div className="bg-white rounded-2xl rounded-tl-md p-3 max-w-[88%] shadow-soft">
          <div
            className="text-[13.5px] leading-snug text-ink whitespace-pre-wrap break-words"
            dangerouslySetInnerHTML={{ __html: rendered }}
          />
        </div>

        {/* Lead magnet attachment */}
        {leadMagnet && (
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
    </div>
  );
}

const EMOJI: Record<string, string> = {
  pdf: '📄', image: '🖼️', video: '🎬', document: '📎',
};

function formatSize(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}

const PLACEHOLDER_VALUES: Record<string, string> = {
  first_name: 'Иван',
  username: 'ivan',
};

const ALLOWED_TAGS_RE = /<\/?(b|i|u|s|code|br|a)(\s[^>]*)?>/gi;

function renderHtml(text: string, previewName: string): string {
  // 1) escape все < и > сначала
  let out = escapeHtml(text);
  // 2) re-allow whitelisted tags
  out = out.replace(/&lt;(\/?(b|i|u|s|code|br)(\s[^&]*)?)&gt;/gi, (_, inner: string) => `<${inner}>`);
  // 3) <a href="..."> — отдельно, разрешаем url-only
  out = out.replace(/&lt;a\s+href=&quot;([^&]+)&quot;&gt;/gi, (_, url: string) => {
    const safe = url.replace(/[<>"']/g, '');
    return `<a href="${safe}" class="text-indigo-600 underline">`;
  });
  out = out.replace(/&lt;\/a&gt;/gi, '</a>');
  // 4) placeholder подстановка
  const values: Record<string, string> = { ...PLACEHOLDER_VALUES, first_name: previewName };
  out = out.replace(/\{(\w+)\}/g, (_, key: string) => values[key] || `{${key}}`);
  // 5) перевод строк
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

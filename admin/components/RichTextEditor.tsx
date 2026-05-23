'use client';

import { useCallback, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';

/**
 * Редактор текста с тулбаром форматирования под Telegram HTML.
 *
 * Поддерживает все теги, которые Telegram умеет в parse_mode=HTML:
 *   <b> <i> <u> <s> <code> <pre> <blockquote> <blockquote expandable>
 *   <tg-spoiler> <a href="…">
 *
 * Работает поверх обычного <textarea>: оборачивает выделение в теги через
 * document.execCommand('insertText', …) — это сохраняет нативный undo/redo стек
 * браузера. Если execCommand недоступен — fallback на setRangeText + input event.
 */

export type RichTextEditorProps = {
  value: string;
  onChange: (next: string) => void;
  rows?: number;
  placeholder?: string;
  /** Плейсхолдеры, которые можно вставить через «{ }» меню. По умолчанию first_name/username. */
  placeholders?: string[];
  className?: string;
  disabled?: boolean;
  id?: string;
};

type Wrap = { open: string; close: string };

const WRAPS: Record<string, Wrap> = {
  bold: { open: '<b>', close: '</b>' },
  italic: { open: '<i>', close: '</i>' },
  underline: { open: '<u>', close: '</u>' },
  strike: { open: '<s>', close: '</s>' },
  code: { open: '<code>', close: '</code>' },
  pre: { open: '<pre>', close: '</pre>' },
  quote: { open: '<blockquote>', close: '</blockquote>' },
  quoteExp: { open: '<blockquote expandable>', close: '</blockquote>' },
  spoiler: { open: '<tg-spoiler>', close: '</tg-spoiler>' },
};

export function RichTextEditor({
  value,
  onChange,
  rows = 6,
  placeholder,
  placeholders = ['first_name', 'username'],
  className,
  disabled,
  id,
}: RichTextEditorProps) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const [placeholderOpen, setPlaceholderOpen] = useState(false);

  /** Записывает в textarea с сохранением undo-стека. Возвращает true при успехе. */
  const insertText = useCallback((text: string): boolean => {
    const ta = taRef.current;
    if (!ta) return false;
    ta.focus();
    try {
      // execCommand сохраняет нативный undo. Deprecated, но поддерживается всеми.
      const ok = document.execCommand('insertText', false, text);
      if (ok) {
        // React не получит input event от execCommand на controlled textarea —
        // принудительно синхронизируем value.
        onChange(ta.value);
        return true;
      }
    } catch {
      /* ignore */
    }
    // Fallback: setRangeText (ломает undo, но текст вставится)
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const next = ta.value.slice(0, start) + text + ta.value.slice(end);
    ta.value = next;
    const caret = start + text.length;
    ta.setSelectionRange(caret, caret);
    onChange(next);
    return false;
  }, [onChange]);

  /** Обернуть выделение тегами. Если выделения нет — вставить пустую пару и поставить курсор между. */
  const wrap = useCallback((w: Wrap) => {
    const ta = taRef.current;
    if (!ta) return;
    ta.focus();
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = ta.value.slice(start, end);
    const text = `${w.open}${selected}${w.close}`;
    const ok = insertText(text);
    // позиционируем курсор: внутрь тегов
    requestAnimationFrame(() => {
      const t = taRef.current;
      if (!t) return;
      const innerStart = start + w.open.length;
      const innerEnd = innerStart + selected.length;
      t.setSelectionRange(innerStart, innerEnd);
    });
    void ok;
  }, [insertText]);

  const insertLink = useCallback(() => {
    const ta = taRef.current;
    if (!ta) return;
    const selected = ta.value.slice(ta.selectionStart, ta.selectionEnd);
    const url = window.prompt('URL:', 'https://');
    if (!url) return;
    const safeUrl = url.replace(/"/g, '&quot;');
    const linkText = selected || 'ссылка';
    insertText(`<a href="${safeUrl}">${linkText}</a>`);
  }, [insertText]);

  const insertPlaceholder = useCallback((name: string) => {
    insertText(`{${name}}`);
    setPlaceholderOpen(false);
  }, [insertText]);

  const insertParagraph = useCallback(() => {
    insertText('\n\n');
  }, [insertText]);

  /** Снять всю HTML-разметку с выделения (или со всего текста, если ничего не выделено). */
  const clearFormat = useCallback(() => {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const hasSelection = end > start;
    const target = hasSelection ? ta.value.slice(start, end) : ta.value;
    const stripped = target
      .replace(/<\/?(b|i|u|s|code|pre|blockquote|tg-spoiler)(\s[^>]*)?>/gi, '')
      .replace(/<a\s+[^>]*>([\s\S]*?)<\/a>/gi, '$1');
    if (hasSelection) {
      ta.setSelectionRange(start, end);
      insertText(stripped);
    } else {
      ta.setSelectionRange(0, ta.value.length);
      insertText(stripped);
    }
  }, [insertText]);

  // Hotkeys: Cmd/Ctrl + B / I / U / K
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!(e.metaKey || e.ctrlKey)) return;
    const k = e.key.toLowerCase();
    if (k === 'b') { e.preventDefault(); wrap(WRAPS.bold); }
    else if (k === 'i') { e.preventDefault(); wrap(WRAPS.italic); }
    else if (k === 'u') { e.preventDefault(); wrap(WRAPS.underline); }
    else if (k === 'k') { e.preventDefault(); insertLink(); }
    else if (k === 'e') { e.preventDefault(); wrap(WRAPS.code); }
  };

  return (
    <div className={clsx('rounded-xl border border-zinc-200/70 bg-white/70 backdrop-blur-sm overflow-hidden', className)}>
      <Toolbar
        disabled={disabled}
        onBold={() => wrap(WRAPS.bold)}
        onItalic={() => wrap(WRAPS.italic)}
        onUnderline={() => wrap(WRAPS.underline)}
        onStrike={() => wrap(WRAPS.strike)}
        onCode={() => wrap(WRAPS.code)}
        onPre={() => wrap(WRAPS.pre)}
        onQuote={() => wrap(WRAPS.quote)}
        onQuoteExpandable={() => wrap(WRAPS.quoteExp)}
        onSpoiler={() => wrap(WRAPS.spoiler)}
        onLink={insertLink}
        onParagraph={insertParagraph}
        onClear={clearFormat}
        placeholders={placeholders}
        placeholderOpen={placeholderOpen}
        onPlaceholderToggle={() => setPlaceholderOpen((v) => !v)}
        onPlaceholderPick={insertPlaceholder}
      />
      <textarea
        ref={taRef}
        id={id}
        rows={rows}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        className="block w-full px-3 py-3 text-sm leading-relaxed bg-transparent focus:outline-none resize-y font-mono"
        spellCheck
      />
      <HintBar />
    </div>
  );
}

/* ─────────────── Toolbar ─────────────── */

function Toolbar(props: {
  disabled?: boolean;
  onBold: () => void;
  onItalic: () => void;
  onUnderline: () => void;
  onStrike: () => void;
  onCode: () => void;
  onPre: () => void;
  onQuote: () => void;
  onQuoteExpandable: () => void;
  onSpoiler: () => void;
  onLink: () => void;
  onParagraph: () => void;
  onClear: () => void;
  placeholders: string[];
  placeholderOpen: boolean;
  onPlaceholderToggle: () => void;
  onPlaceholderPick: (name: string) => void;
}) {
  const isMac = useMemo(
    () => typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform),
    [],
  );
  const mod = isMac ? '⌘' : 'Ctrl';

  return (
    <div className="flex flex-wrap items-center gap-0.5 px-1.5 py-1.5 border-b border-zinc-200/70 bg-zinc-50/70">
      <TBtn onClick={props.onBold} title={`Жирный (${mod}+B)`} disabled={props.disabled}>
        <span className="font-bold">B</span>
      </TBtn>
      <TBtn onClick={props.onItalic} title={`Курсив (${mod}+I)`} disabled={props.disabled}>
        <span className="italic font-serif">I</span>
      </TBtn>
      <TBtn onClick={props.onUnderline} title={`Подчёркнутый (${mod}+U)`} disabled={props.disabled}>
        <span className="underline">U</span>
      </TBtn>
      <TBtn onClick={props.onStrike} title="Зачёркнутый" disabled={props.disabled}>
        <span className="line-through">S</span>
      </TBtn>

      <Sep />

      <TBtn onClick={props.onCode} title={`Моноширинный (${mod}+E)`} disabled={props.disabled}>
        <span className="font-mono text-[12px]">{'<>'}</span>
      </TBtn>
      <TBtn onClick={props.onPre} title="Блок кода (pre)" disabled={props.disabled}>
        <span className="font-mono text-[10px] tracking-tight">{'{ }'}</span>
      </TBtn>

      <Sep />

      <TBtn onClick={props.onQuote} title="Цитата" disabled={props.disabled}>
        <QuoteIcon />
      </TBtn>
      <TBtn onClick={props.onQuoteExpandable} title="Раскрывающаяся цитата" disabled={props.disabled}>
        <QuoteIcon expandable />
      </TBtn>
      <TBtn onClick={props.onSpoiler} title="Спойлер" disabled={props.disabled}>
        <SpoilerIcon />
      </TBtn>

      <Sep />

      <TBtn onClick={props.onLink} title={`Ссылка (${mod}+K)`} disabled={props.disabled}>
        <LinkIcon />
      </TBtn>
      <TBtn onClick={props.onParagraph} title="Пустая строка между абзацами" disabled={props.disabled}>
        <span className="font-serif">¶</span>
      </TBtn>

      <Sep />

      <div className="relative">
        <TBtn
          onClick={props.onPlaceholderToggle}
          title="Вставить плейсхолдер"
          disabled={props.disabled}
          active={props.placeholderOpen}
        >
          <span className="text-[11px]">{'{ }'}<span className="ml-0.5 opacity-60">▾</span></span>
        </TBtn>
        {props.placeholderOpen && (
          <div className="absolute z-20 mt-1 left-0 min-w-[180px] rounded-lg border border-zinc-200/80 bg-white shadow-xl py-1">
            <div className="px-3 py-1 text-[10px] uppercase tracking-widest text-zinc-400">Плейсхолдеры</div>
            {props.placeholders.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => props.onPlaceholderPick(p)}
                className="w-full text-left px-3 py-1.5 text-sm font-mono hover:bg-indigo-50 transition"
              >
                {'{' + p + '}'}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="ml-auto">
        <TBtn onClick={props.onClear} title="Снять форматирование" disabled={props.disabled} variant="ghost">
          <span className="text-[11px] text-zinc-500">очистить</span>
        </TBtn>
      </div>
    </div>
  );
}

function TBtn({
  onClick, title, disabled, children, active, variant,
}: {
  onClick: () => void;
  title: string;
  disabled?: boolean;
  children: React.ReactNode;
  active?: boolean;
  variant?: 'ghost';
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()}
      className={clsx(
        'min-w-[28px] h-7 px-1.5 inline-flex items-center justify-center rounded-md text-sm transition select-none',
        variant === 'ghost'
          ? 'hover:bg-zinc-100 text-zinc-500 hover:text-zinc-700'
          : active
            ? 'bg-indigo-100 text-indigo-700'
            : 'hover:bg-white text-zinc-700 hover:shadow-soft',
        'disabled:opacity-40 disabled:cursor-not-allowed',
      )}
    >
      {children}
    </button>
  );
}

function Sep() {
  return <div className="w-px h-5 bg-zinc-200/80 mx-1" aria-hidden />;
}

function HintBar() {
  return (
    <div className="px-3 py-1.5 border-t border-zinc-200/70 bg-zinc-50/40 text-[10.5px] text-zinc-500 flex items-center gap-3 flex-wrap">
      <span>Telegram HTML</span>
      <span className="opacity-60">·</span>
      <span>Двойной перенос строки = новый абзац</span>
      <span className="opacity-60">·</span>
      <span><kbd className="px-1 py-0.5 rounded bg-white border border-zinc-200 text-[10px]">⌘B</kbd> жирный</span>
      <span><kbd className="px-1 py-0.5 rounded bg-white border border-zinc-200 text-[10px]">⌘I</kbd> курсив</span>
      <span><kbd className="px-1 py-0.5 rounded bg-white border border-zinc-200 text-[10px]">⌘K</kbd> ссылка</span>
      <span><kbd className="px-1 py-0.5 rounded bg-white border border-zinc-200 text-[10px]">⌘E</kbd> код</span>
    </div>
  );
}

/* ─────────────── Icons ─────────────── */

function QuoteIcon({ expandable }: { expandable?: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 5v14" />
      <path d="M9 8h11M9 12h8M9 16h11" />
      {expandable && <path d="M19 19l2 2-2 2" transform="translate(-1 -2)" />}
    </svg>
  );
}

function SpoilerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
      <circle cx="12" cy="12" r="3" />
      <path d="M3 3l18 18" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" />
      <path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" />
    </svg>
  );
}

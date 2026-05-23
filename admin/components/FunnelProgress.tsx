'use client';

import clsx from 'clsx';

export type SectionStatus = 'ok' | 'warn' | 'todo' | 'off';

export type ProgressStep = {
  key: string;
  label: string;
  count?: number;
  status: SectionStatus;
};

const STATUS_ICON: Record<SectionStatus, string> = {
  ok: '✅',
  warn: '❗',
  todo: '⚪',
  off: '🔘',
};

const STATUS_DOT: Record<SectionStatus, string> = {
  ok: 'bg-emerald-500',
  warn: 'bg-amber-500',
  todo: 'bg-zinc-300',
  off: 'bg-zinc-300',
};

/** Sticky прогресс-бар студии воронки.
 *
 * - На desktop: горизонтальный flow с separator'ами
 * - На mobile: collapsed pill с текущим шагом + раскрытие по тапу
 */
export function FunnelProgress({
  steps,
  currentKey,
  onJump,
  savingState,
}: {
  steps: ProgressStep[];
  currentKey?: string;
  onJump?: (key: string) => void;
  savingState?: 'idle' | 'saving' | 'saved';
}) {
  const allOk = steps.every((s) => s.status === 'ok' || s.status === 'off');
  const todoStep = steps.find((s) => s.status === 'warn') || steps.find((s) => s.status === 'todo');

  return (
    <div className="sticky top-0 sm:top-3 z-30 -mx-4 sm:mx-0 mb-4">
      <div className="glass-strong sm:rounded-2xl px-4 sm:px-5 py-3 sm:py-3.5">
        {/* Desktop flow */}
        <div className="hidden sm:flex items-center gap-1.5">
          {steps.map((s, i) => (
            <div key={s.key} className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => onJump?.(s.key)}
                className={clsx(
                  'inline-flex items-center gap-2 px-2.5 h-8 rounded-lg text-xs font-medium transition',
                  currentKey === s.key
                    ? 'bg-white shadow-soft text-ink'
                    : 'text-zinc-600 hover:bg-white/60 hover:text-ink',
                )}
              >
                <span>{STATUS_ICON[s.status]}</span>
                <span>{s.label}</span>
                {s.count != null && (
                  <span className="text-zinc-400">({s.count})</span>
                )}
              </button>
              {i < steps.length - 1 && (
                <span className="text-zinc-300 select-none">─</span>
              )}
            </div>
          ))}

          <div className="ml-auto text-xs">
            {savingState === 'saving' && <span className="text-zinc-500">Сохраняем…</span>}
            {savingState === 'saved' && <span className="text-emerald-600">Сохранено ✓</span>}
          </div>
        </div>

        {/* Mobile: одна строка с current step + раскрытие */}
        <details className="sm:hidden">
          <summary className="flex items-center gap-2 cursor-pointer text-sm font-medium list-none">
            <span>{STATUS_ICON[(todoStep || steps[0]).status]}</span>
            <span className="flex-1 truncate">
              {todoStep ? `Следующий: ${todoStep.label}` : 'Все шаги готовы 🎉'}
            </span>
            <span className="text-zinc-400 text-xs">
              {steps.filter((s) => s.status === 'ok').length}/{steps.length}
            </span>
            <svg className="size-4 text-zinc-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </summary>
          <div className="mt-3 space-y-1.5 border-t border-white/40 pt-3">
            {steps.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => onJump?.(s.key)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/60 text-left"
              >
                <span className={clsx('size-2 rounded-full shrink-0', STATUS_DOT[s.status])} />
                <span className="text-sm flex-1">{s.label}</span>
                <span className="text-xs text-zinc-500">{STATUS_ICON[s.status]}</span>
              </button>
            ))}
          </div>
        </details>

        {/* Подсказка снизу */}
        {!allOk && todoStep && (
          <div className="mt-1.5 hidden sm:block text-[11px] text-zinc-500">
            ↓ Чтобы воронка заработала — закончи «{todoStep.label}»
          </div>
        )}
      </div>
    </div>
  );
}

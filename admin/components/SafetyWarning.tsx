'use client';

import { ReactNode } from 'react';

import { Button } from '@/components/ui';

/**
 * Жёлтая плашка-warning при правке шагов активной воронки.
 *
 * Показывается когда:
 *   funnel.is_active && funnel.active_entries > 0 && admin начал editing шага
 */
export function ActiveFunnelWarning({
  activeEntries,
  estimatedAffected,
  onShowDiff,
  onUndoChanges,
  children,
}: {
  activeEntries: number;
  estimatedAffected?: number;
  onShowDiff?: () => void;
  onUndoChanges?: () => void;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-xl border-2 border-amber-300/70 bg-amber-50/60 backdrop-blur p-3 sm:p-4 mb-3">
      <div className="flex items-start gap-3">
        <div className="text-xl shrink-0">⚠️</div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm text-amber-900">Это активная воронка</div>
          <div className="text-sm text-amber-800 mt-1 leading-snug">
            Сейчас в ней <b>{activeEntries}</b> {pluralize(activeEntries, 'активный', 'активных', 'активных')} подписчик
            {pluralize(activeEntries, '', 'а', 'ов')}.
            {estimatedAffected != null && estimatedAffected > 0 && (
              <>
                {' '}Изменения коснутся <b>~{estimatedAffected}</b> {pluralize(estimatedAffected, 'человека', 'человек', 'человек')},
                кто получит этот шаг в ближайшие сутки.
              </>
            )}
          </div>
          {children && <div className="mt-2 text-xs text-amber-800">{children}</div>}
          <div className="mt-2.5 flex flex-wrap gap-2">
            {onShowDiff && (
              <button
                type="button"
                onClick={onShowDiff}
                className="text-xs text-amber-700 hover:text-amber-900 underline"
              >
                ⌄ Показать diff
              </button>
            )}
            {onUndoChanges && (
              <button
                type="button"
                onClick={onUndoChanges}
                className="text-xs text-amber-700 hover:text-amber-900 underline"
              >
                Отменить мои правки
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


/**
 * Confirm-modal перед сохранением правок активной воронки.
 */
export function ActiveFunnelConfirm({
  open,
  activeEntries,
  estimatedAffected,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  activeEntries: number;
  estimatedAffected?: number;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  const remaining = activeEntries - (estimatedAffected || 0);
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 anim-fade">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="relative glass-strong rounded-2xl max-w-md w-full p-6 anim-rise">
        <div className="flex items-start gap-3">
          <div className="text-2xl shrink-0">⚠️</div>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold tracking-tight">Применить изменения?</h3>
            <div className="mt-2 text-sm text-zinc-700 leading-relaxed space-y-2">
              <p>
                В этой воронке сейчас <b>{activeEntries}</b> активных подписчиков.
              </p>
              {estimatedAffected != null && (
                <>
                  <p>
                    Изменения шага коснутся примерно <b>{estimatedAffected}</b>{' '}
                    {pluralize(estimatedAffected, 'человека', 'человек', 'человек')},
                    которые получат этот шаг в ближайшие сутки.
                  </p>
                  {remaining > 0 && (
                    <p className="text-zinc-500">
                      Остальные {remaining} уже прошли этот шаг — на них не повлияет.
                    </p>
                  )}
                </>
              )}
            </div>
            <div className="mt-5 flex gap-2 justify-end flex-wrap">
              <Button variant="ghost" onClick={onCancel}>Отмена</Button>
              <Button onClick={onConfirm}>
                {estimatedAffected != null
                  ? `Применить для ${estimatedAffected} пользователей`
                  : 'Применить изменения'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


function pluralize(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}

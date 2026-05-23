'use client';

import { useState } from 'react';

import { api } from '@/lib/api';
import { Button, Sheet } from '@/components/ui';

/**
 * Заглушка под A/B-тестирование. Tab-bar в редакторе шага:
 * [Вариант A] [Вариант B 🔒]
 *
 * Tap на 🔒 → открывает CTA для feature request.
 */
export function AbTestPlaceholder({ stepId }: { stepId: number }) {
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function vote() {
    setBusy(true);
    try {
      await api.post('/feature-requests', {
        feature_key: 'ab_testing',
        context: `Хочу A/B-тестирование для шагов воронки. step_id=${stepId}`,
      });
      setSent(true);
    } catch {
      // tihi
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="inline-flex items-center gap-1 mb-3 text-xs">
        <button
          type="button"
          className="px-2.5 h-7 rounded-lg bg-white/80 shadow-soft font-medium text-ink"
        >
          Вариант A
        </button>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="px-2.5 h-7 rounded-lg text-zinc-500 hover:text-ink hover:bg-white/60 transition"
          title="A/B-тестирование — coming soon"
        >
          + Вариант B 🔒
        </button>
      </div>

      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title="A/B-тестирование шага"
        description="Эта фича в планах — пока недоступна"
        footer={
          <Button onClick={() => setOpen(false)}>Понятно</Button>
        }
      >
        <div className="space-y-4 text-sm">
          <div className="text-2xl">🧪</div>
          <p className="text-zinc-700 leading-relaxed">
            С A/B-тестированием можно будет:
          </p>
          <ul className="text-zinc-700 space-y-1.5 pl-5 list-disc">
            <li>Создать <b>вариант B</b> текста этого шага</li>
            <li>Распределить трафик 50/50 (или другой split)</li>
            <li>Сравнить open-rate, click-rate, конверсию в paid</li>
            <li>Победивший вариант → автоматически становится основным</li>
          </ul>

          <div className="border-t border-zinc-200/60 pt-4">
            <p className="text-xs text-zinc-500 mb-3">
              Эта фича в roadmap. Если она нужна вам сейчас — мы это посчитаем как +1 голос:
            </p>
            {sent ? (
              <div className="text-sm text-emerald-700 bg-emerald-50/60 border border-emerald-200/60 rounded-xl px-3 py-2">
                ✓ Спасибо! Голос засчитан. Дадим знать, когда фича появится.
              </div>
            ) : (
              <Button onClick={vote} disabled={busy} variant="ghost" className="w-full">
                {busy ? 'Отправляем…' : '🗳 Хочу A/B-тестирование'}
              </Button>
            )}
          </div>
        </div>
      </Sheet>
    </>
  );
}

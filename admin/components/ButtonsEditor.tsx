'use client';

import { Button, Field, Input, Select } from '@/components/ui';

export type Btn = { text: string; url?: string; callback_data?: string };
export type ButtonRows = Btn[][];

export function ButtonsEditor({
  value,
  onChange,
}: {
  value: ButtonRows | null;
  onChange: (next: ButtonRows | null) => void;
}) {
  const rows = value || [];

  function update(rowIdx: number, btnIdx: number, patch: Partial<Btn>) {
    const next = rows.map((r, ri) =>
      ri === rowIdx ? r.map((b, bi) => (bi === btnIdx ? { ...b, ...patch } : b)) : r,
    );
    onChange(next.length ? next : null);
  }

  function addBtnInRow(rowIdx: number) {
    const next = rows.map((r, ri) =>
      ri === rowIdx ? [...r, { text: '', url: '' }] : r,
    );
    onChange(next);
  }

  function addRow() {
    onChange([...(rows || []), [{ text: '', url: '' }]]);
  }

  function removeBtn(rowIdx: number, btnIdx: number) {
    const next = rows
      .map((r, ri) => (ri === rowIdx ? r.filter((_, bi) => bi !== btnIdx) : r))
      .filter((r) => r.length > 0);
    onChange(next.length ? next : null);
  }

  if (!rows.length) {
    return (
      <div className="text-xs text-zinc-500 py-3 px-3.5 border border-dashed border-zinc-300 rounded-xl">
        Кнопки опциональны. Используйте чтобы дать действие пользователю прямо под сообщением — открыть ссылку или передать callback.
        <button
          type="button"
          onClick={addRow}
          className="ml-2 text-indigo-600 hover:underline"
        >
          + Добавить кнопку
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      {rows.map((row, ri) => (
        <div key={ri} className="rounded-xl glass-soft p-2.5 space-y-2">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Ряд {ri + 1}</div>
          {row.map((b, bi) => (
            <div key={bi} className="flex gap-2 items-start">
              <div className="flex-1 grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2">
                <Input
                  placeholder="Текст кнопки"
                  value={b.text}
                  onChange={(e) => update(ri, bi, { text: e.target.value })}
                />
                <Input
                  placeholder="URL или callback_data"
                  value={b.url || b.callback_data || ''}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v.startsWith('http') || v.startsWith('tg://')) {
                      update(ri, bi, { url: v, callback_data: undefined });
                    } else {
                      update(ri, bi, { callback_data: v, url: undefined });
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={() => removeBtn(ri, bi)}
                  className="text-zinc-400 hover:text-rose-600 transition text-xs px-2 self-center"
                  aria-label="Удалить"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
          <button
            type="button"
            onClick={() => addBtnInRow(ri)}
            className="text-xs text-indigo-600 hover:underline"
          >
            + Кнопка в этом ряду
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addRow}
        className="text-xs text-indigo-600 hover:underline"
      >
        + Новый ряд кнопок
      </button>
    </div>
  );
}

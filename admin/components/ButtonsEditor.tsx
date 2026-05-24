'use client';

import useSWR from 'swr';

import { Input, Select } from '@/components/ui';
import { fetcher } from '@/lib/api';

/**
 * Inline-кнопки шага воронки.
 *
 * Хранятся в БД в формате Telegram (text + url ИЛИ callback_data), но в
 * админке мы прячем технические детали за «типом кнопки». Юзер выбирает
 * действие («Открыть ссылку», «Оставить заявку на продукт N» и т.п.),
 * редактор сам формирует правильное callback_data.
 *
 * Поддерживаются типы:
 *   URL          — открыть ссылку (url=...)
 *   LEAD         — оставить заявку на продукт (callback_data=lead:{id})
 *   PRODUCT      — показать тарифы продукта (callback_data=prod:{id})
 *   FUNNEL       — запустить воронку (callback_data=funnel:start:{id})
 *   MENU         — главное меню (callback_data=menu:main)
 *
 * Системная кнопка «🔕 Не присылать напоминания» добавляется бэкендом
 * автоматически и здесь НЕ настраивается.
 */

export type Btn = { text: string; url?: string; callback_data?: string };
export type ButtonRows = Btn[][];

type BtnKind = 'url' | 'lead' | 'product' | 'funnel' | 'menu';

type ProductBrief = { id: number; name: string };
type FunnelBrief = { id: number; name: string };

function detectKind(b: Btn): BtnKind {
  const cd = b.callback_data || '';
  if (cd.startsWith('lead:')) return 'lead';
  if (cd.startsWith('prod:')) return 'product';
  if (cd.startsWith('funnel:start:')) return 'funnel';
  if (cd === 'menu:main') return 'menu';
  return 'url';
}

const KIND_OPTIONS: { value: BtnKind; label: string; hint: string }[] = [
  { value: 'url',     label: '🔗 Открыть ссылку',         hint: 'URL сайта, оплаты, чата с менеджером' },
  { value: 'lead',    label: '📝 Оставить заявку',        hint: 'Создаёт Lead в админке' },
  { value: 'product', label: '💎 Показать тарифы',        hint: 'Карточка продукта с ценами 3/6/12' },
  { value: 'funnel',  label: '🎯 Запустить воронку',      hint: 'Подписать юзера на серию сообщений' },
  { value: 'menu',    label: '🏠 Главное меню',           hint: 'Каталог всех продуктов' },
];

function defaultsForKind(kind: BtnKind, currentText: string): Btn {
  // Сохраняем текст кнопки при смене типа; технические поля переустанавливаем
  switch (kind) {
    case 'url':
      return { text: currentText || 'Открыть', url: '', callback_data: undefined };
    case 'lead':
      return { text: currentText || 'Оставить заявку', callback_data: '', url: undefined };
    case 'product':
      return { text: currentText || 'Посмотреть тарифы', callback_data: '', url: undefined };
    case 'funnel':
      return { text: currentText || 'Узнать подробнее', callback_data: '', url: undefined };
    case 'menu':
      return { text: currentText || 'Главное меню', callback_data: 'menu:main', url: undefined };
  }
}


export function ButtonsEditor({
  value,
  onChange,
}: {
  value: ButtonRows | null;
  onChange: (next: ButtonRows | null) => void;
}) {
  const rows = value || [];
  const { data: products } = useSWR<ProductBrief[]>('/products', fetcher);
  const { data: funnels } = useSWR<FunnelBrief[]>('/funnels', fetcher);

  function update(rowIdx: number, btnIdx: number, patch: Partial<Btn>) {
    const next = rows.map((r, ri) =>
      ri === rowIdx ? r.map((b, bi) => (bi === btnIdx ? { ...b, ...patch } : b)) : r,
    );
    onChange(next.length ? next : null);
  }

  function changeKind(rowIdx: number, btnIdx: number, kind: BtnKind) {
    const current = rows[rowIdx][btnIdx];
    const next = defaultsForKind(kind, current.text);
    const updated = rows.map((r, ri) =>
      ri === rowIdx ? r.map((b, bi) => (bi === btnIdx ? next : b)) : r,
    );
    onChange(updated);
  }

  function addBtnInRow(rowIdx: number) {
    const next = rows.map((r, ri) =>
      ri === rowIdx ? [...r, defaultsForKind('url', '')] : r,
    );
    onChange(next);
  }

  function addRow() {
    onChange([...(rows || []), [defaultsForKind('url', '')]]);
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
        Кнопки опциональны. Можно добавить действие прямо под сообщением:
        ссылку, заявку на продукт, переход в другую воронку и т.д.
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
        <div key={ri} className="rounded-xl glass-soft p-2.5 space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">
              Ряд {ri + 1}
            </div>
            <div className="text-[10px] text-zinc-400">
              кнопки в ряду показываются Telegram в одну строку
            </div>
          </div>
          {row.map((b, bi) => {
            const kind = detectKind(b);
            return (
              <div key={bi} className="rounded-lg bg-white/60 p-2.5 space-y-2 border border-zinc-200/60">
                <div className="flex gap-2 items-start">
                  <Select
                    value={kind}
                    onChange={(e) => changeKind(ri, bi, e.target.value as BtnKind)}
                    className="!w-48 shrink-0"
                  >
                    {KIND_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </Select>
                  <Input
                    placeholder="Текст кнопки (что видит юзер)"
                    value={b.text}
                    onChange={(e) => update(ri, bi, { text: e.target.value })}
                    className="flex-1"
                  />
                  <button
                    type="button"
                    onClick={() => removeBtn(ri, bi)}
                    className="text-zinc-400 hover:text-rose-600 transition text-xs px-2 self-center"
                    aria-label="Удалить кнопку"
                  >
                    ✕
                  </button>
                </div>
                <BtnActionFields
                  kind={kind}
                  btn={b}
                  products={products || []}
                  funnels={funnels || []}
                  onChange={(patch) => update(ri, bi, patch)}
                />
                <div className="text-[10px] text-zinc-500 italic">
                  {KIND_OPTIONS.find((o) => o.value === kind)?.hint}
                </div>
              </div>
            );
          })}
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


/** Поле(я) специфичное для выбранного типа кнопки. */
function BtnActionFields({
  kind, btn, products, funnels, onChange,
}: {
  kind: BtnKind;
  btn: Btn;
  products: ProductBrief[];
  funnels: FunnelBrief[];
  onChange: (patch: Partial<Btn>) => void;
}) {
  if (kind === 'url') {
    return (
      <Input
        placeholder="https://… или t.me/your_bot"
        value={btn.url || ''}
        onChange={(e) => onChange({ url: e.target.value, callback_data: undefined })}
      />
    );
  }

  if (kind === 'menu') {
    // Без полей — callback_data='menu:main' зашит дефолтами
    return null;
  }

  if (kind === 'lead' || kind === 'product') {
    // Извлекаем id продукта из callback_data
    const prefix = kind === 'lead' ? 'lead:' : 'prod:';
    const cd = btn.callback_data || '';
    const currentId = cd.startsWith(prefix) ? cd.slice(prefix.length) : '';
    return (
      <Select
        value={currentId}
        onChange={(e) => onChange({
          callback_data: e.target.value ? `${prefix}${e.target.value}` : '',
          url: undefined,
        })}
      >
        <option value="">— выберите продукт —</option>
        {products.map((p) => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </Select>
    );
  }

  if (kind === 'funnel') {
    const cd = btn.callback_data || '';
    const currentId = cd.startsWith('funnel:start:') ? cd.slice('funnel:start:'.length) : '';
    return (
      <Select
        value={currentId}
        onChange={(e) => onChange({
          callback_data: e.target.value ? `funnel:start:${e.target.value}` : '',
          url: undefined,
        })}
      >
        <option value="">— выберите воронку —</option>
        {funnels.map((f) => (
          <option key={f.id} value={f.id}>{f.name}</option>
        ))}
      </Select>
    );
  }

  return null;
}

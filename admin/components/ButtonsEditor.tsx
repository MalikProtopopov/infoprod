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
 *   QUIZ         — запустить квиз (callback_data=quiz:start:{step_id})
 *   FORM         — открыть форму (callback_data=form:start:{step_id})
 *   MENU         — главное меню (callback_data=menu:main)
 *
 * Для QUIZ/FORM в селекторе показываются ШАГИ-контейнеры (kind='quiz'/'form')
 * текущей воронки. Если контекст воронки неизвестен — показываем все.
 *
 * Системная кнопка «🔕 Не присылать напоминания» добавляется бэкендом
 * автоматически и здесь НЕ настраивается.
 */

export type Btn = {
  text: string;
  url?: string;
  callback_data?: string;
  // Только для track-кнопок: тег сегмента и ответ после клика.
  tag?: string;
  reply_text?: string;
};
export type ButtonRows = Btn[][];

type BtnKind = 'url' | 'lead' | 'product' | 'funnel' | 'quiz' | 'form' | 'menu' | 'track';

type ProductBrief = { id: number; name: string };
type FunnelBrief = { id: number; name: string };
type StepBrief = {
  id: number;
  funnel_id: number;
  kind: 'message' | 'quiz' | 'form';
  quiz_id: number | null;
  form_id: number | null;
};

function detectKind(b: Btn): BtnKind {
  const cd = b.callback_data || '';
  if (cd.startsWith('lead:')) return 'lead';
  if (cd.startsWith('prod:')) return 'product';
  if (cd.startsWith('funnel:start:')) return 'funnel';
  if (cd.startsWith('quiz:start:')) return 'quiz';
  if (cd.startsWith('form:start:')) return 'form';
  if (cd.startsWith('track:')) return 'track';
  if (cd === 'menu:main') return 'menu';
  return 'url';
}

const KIND_OPTIONS: { value: BtnKind; label: string; hint: string }[] = [
  { value: 'url',     label: '🔗 Открыть ссылку',         hint: 'URL сайта, оплаты, чата с менеджером' },
  { value: 'lead',    label: '📝 Оставить заявку',        hint: 'Создаёт Lead в админке' },
  { value: 'product', label: '💎 Показать тарифы',        hint: 'Карточка продукта с ценами 3/6/12' },
  { value: 'funnel',  label: '🎯 Запустить воронку',      hint: 'Подписать юзера на серию сообщений' },
  { value: 'quiz',    label: '🧠 Запустить квиз',         hint: 'Открыть интерактивный опрос с подсчётом score' },
  { value: 'form',    label: '📋 Открыть форму',          hint: 'Серия вопросов с сохранением в Lead' },
  { value: 'track',   label: '✅ Кнопка-отметка',          hint: 'Фиксирует клик (CTR), ставит тег сегмента и опц. отвечает текстом' },
  { value: 'menu',    label: '🏠 Главное меню',           hint: 'Каталог всех продуктов' },
];

function genTrackKey(): string {
  return Math.random().toString(36).slice(2, 8);
}

function defaultsForKind(kind: BtnKind, currentText: string, stepId?: number): Btn {
  // Сохраняем текст кнопки при смене типа; технические поля переустанавливаем
  switch (kind) {
    case 'track':
      return {
        text: currentText || 'Понятно',
        callback_data: stepId ? `track:${stepId}:${genTrackKey()}` : '',
        url: undefined,
        tag: '',
        reply_text: '',
      };
    case 'url':
      return { text: currentText || 'Открыть', url: '', callback_data: undefined };
    case 'lead':
      return { text: currentText || 'Оставить заявку', callback_data: '', url: undefined };
    case 'product':
      return { text: currentText || 'Посмотреть тарифы', callback_data: '', url: undefined };
    case 'funnel':
      return { text: currentText || 'Узнать подробнее', callback_data: '', url: undefined };
    case 'quiz':
      return { text: currentText || 'начать тест →', callback_data: '', url: undefined };
    case 'form':
      return { text: currentText || 'оставить заявку →', callback_data: '', url: undefined };
    case 'menu':
      return { text: currentText || 'Главное меню', callback_data: 'menu:main', url: undefined };
  }
}


export function ButtonsEditor({
  value,
  onChange,
  funnelId,
  stepId,
}: {
  value: ButtonRows | null;
  onChange: (next: ButtonRows | null) => void;
  /** id текущей воронки — для фильтрации quiz/form-шагов по контексту */
  funnelId?: number;
  /** id текущего шага — нужен для track-кнопок (callback_data=track:{stepId}:{key}) */
  stepId?: number;
}) {
  const rows = value || [];
  const { data: products } = useSWR<ProductBrief[]>('/products', fetcher);
  const { data: funnels } = useSWR<FunnelBrief[]>('/funnels', fetcher);

  // Шаги-контейнеры (quiz/form) текущей воронки — для селекторов
  const { data: funnelDetail } = useSWR<{ steps: StepBrief[] } | null>(
    funnelId ? `/funnels/${funnelId}` : null,
    fetcher,
  );
  const containerSteps: StepBrief[] = funnelDetail?.steps?.filter(
    (s) => s.kind === 'quiz' || s.kind === 'form',
  ) || [];

  // Имена квизов/форм — батч-загрузка для лейблов в select'ах
  const { data: quizzes } = useSWR<{ id: number; name: string }[]>('/quizzes', fetcher);
  const { data: forms } = useSWR<{ id: number; name: string }[]>('/forms', fetcher);
  const quizNameById = new Map((quizzes || []).map((q) => [q.id, q.name]));
  const formNameById = new Map((forms || []).map((f) => [f.id, f.name]));

  function update(rowIdx: number, btnIdx: number, patch: Partial<Btn>) {
    const next = rows.map((r, ri) =>
      ri === rowIdx ? r.map((b, bi) => (bi === btnIdx ? { ...b, ...patch } : b)) : r,
    );
    onChange(next.length ? next : null);
  }

  function changeKind(rowIdx: number, btnIdx: number, kind: BtnKind) {
    const current = rows[rowIdx][btnIdx];
    const next = defaultsForKind(kind, current.text, stepId);
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
                    {KIND_OPTIONS.filter((opt) => opt.value !== 'track' || stepId).map((opt) => (
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
                  containerSteps={containerSteps}
                  quizNameById={quizNameById}
                  formNameById={formNameById}
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
  kind, btn, products, funnels, containerSteps, quizNameById, formNameById, onChange,
}: {
  kind: BtnKind;
  btn: Btn;
  products: ProductBrief[];
  funnels: FunnelBrief[];
  containerSteps: StepBrief[];
  quizNameById: Map<number, string>;
  formNameById: Map<number, string>;
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

  if (kind === 'track') {
    return (
      <div className="space-y-1.5">
        <Input
          placeholder="Тег сегмента (опц.), напр. hot"
          value={btn.tag || ''}
          onChange={(e) => onChange({ tag: e.target.value })}
        />
        <Input
          placeholder="Ответ после клика (опц.) — придёт сообщением"
          value={btn.reply_text || ''}
          onChange={(e) => onChange({ reply_text: e.target.value })}
        />
        <div className="text-[10px] text-zinc-400 leading-snug">
          Тег используется для показа шагов «только своему сегменту» (поле «Кому показывать» в шаге).
        </div>
      </div>
    );
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

  if (kind === 'quiz' || kind === 'form') {
    // Селектор показывает СТУПЕНИ-контейнеры этой воронки (kind='quiz'/'form'),
    // потому что callback_data это step_id, не quiz_id напрямую.
    // Шаг — это место, через которое квиз/форма подключены к воронке.
    const prefix = kind === 'quiz' ? 'quiz:start:' : 'form:start:';
    const cd = btn.callback_data || '';
    const currentStepId = cd.startsWith(prefix) ? cd.slice(prefix.length) : '';
    const steps = containerSteps.filter((s) => s.kind === kind);
    return (
      <div className="space-y-1">
        <Select
          value={currentStepId}
          onChange={(e) => onChange({
            callback_data: e.target.value ? `${prefix}${e.target.value}` : '',
            url: undefined,
          })}
        >
          <option value="">
            {steps.length === 0
              ? `— нет ${kind === 'quiz' ? 'квизов' : 'форм'} в этой воронке —`
              : `— выберите ${kind === 'quiz' ? 'квиз' : 'форму'} —`}
          </option>
          {steps.map((s) => {
            const sourceId = kind === 'quiz' ? s.quiz_id : s.form_id;
            const label = sourceId
              ? (kind === 'quiz' ? quizNameById.get(sourceId) : formNameById.get(sourceId))
              : null;
            return (
              <option key={s.id} value={s.id}>
                {label || `шаг #${s.id} (${kind === 'quiz' ? 'квиз' : 'форма'} #${sourceId ?? '?'})`}
              </option>
            );
          })}
        </Select>
        {steps.length === 0 && (
          <div className="text-[10px] text-amber-700 leading-snug">
            Добавь {kind === 'quiz' ? 'квиз' : 'форму'} в шаги воронки через
            «+ Шаг» → выбрать тип «{kind === 'quiz' ? 'Квиз' : 'Форма'}».
          </div>
        )}
      </div>
    );
  }

  return null;
}

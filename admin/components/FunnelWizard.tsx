'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { Button, Field, Input, Select, Textarea } from '@/components/ui';

type Product = { id: number; name: string; code: string };

const TEMPLATES = {
  short: {
    label: 'Короткая: 3 шага за 3 дня',
    steps: [
      { delay_minutes: 0,   message_text: 'Здравствуйте, {first_name}! Спасибо что пришли. Прикрепляю обещанное ↓' },
      { delay_minutes: 1440, message_text: 'День 1: первый кейс/пример из практики.' },
      { delay_minutes: 4320, message_text: 'День 3: финальное приглашение присоединиться.' },
    ],
  },
  medium: {
    label: 'Средняя: 5 шагов за 7 дней (рекомендуется)',
    steps: [
      { delay_minutes: 0,   message_text: 'Здравствуйте, {first_name}! Спасибо что пришли. Прикрепляю обещанное ↓' },
      { delay_minutes: 1440, message_text: 'День 1: кейс с конкретным результатом.' },
      { delay_minutes: 4320, message_text: 'День 3: полезный материал / разбор типичной ошибки.' },
      { delay_minutes: 7200, message_text: 'День 5: социальное доказательство (отзывы / цифры).' },
      { delay_minutes: 10080, message_text: 'День 7: финальное приглашение с кнопкой [Узнать подробнее].' },
    ],
  },
  long: {
    label: 'Длинная: 7 шагов за 14 дней',
    steps: [
      { delay_minutes: 0,   message_text: 'Здравствуйте, коллега! В этой серии — материалы из практики. 14 дней.' },
      { delay_minutes: 1440, message_text: 'День 1: лидмагнит / протокол.' },
      { delay_minutes: 4320, message_text: 'День 3: разбор сложного кейса.' },
      { delay_minutes: 7200, message_text: 'День 5: видео-разбор.' },
      { delay_minutes: 10080, message_text: 'День 7: бизнес-материал с цифрами.' },
      { delay_minutes: 14400, message_text: 'День 10: истории выпускниц.' },
      { delay_minutes: 20160, message_text: 'День 14: приглашение на личный разбор.' },
    ],
  },
  empty: { label: 'Пустая — добавлю шаги сам', steps: [] },
} as const;
type TemplateKey = keyof typeof TEMPLATES;


export function FunnelWizard({
  onClose,
  onCreated,
  preSelectedProductId,
}: {
  onClose: () => void;
  onCreated: (funnelId: number) => void;
  preSelectedProductId?: number;
}) {
  const router = useRouter();
  const { data: products } = useSWR<Product[]>('/products', fetcher);

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [productId, setProductId] = useState<number | ''>(preSelectedProductId || '');
  const [name, setName] = useState('');
  const [template, setTemplate] = useState<TemplateKey>('medium');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasProducts = (products?.length || 0) > 0;

  async function create() {
    setCreating(true); setError(null);
    try {
      const payload = {
        name: name.trim(),
        product_id: Number(productId),
        ttl_days: 30,
        cancel_on_payment: true,
        steps: TEMPLATES[template].steps.map((s, i) => ({
          order_idx: i,
          delay_minutes: s.delay_minutes,
          message_text: s.message_text,
        })),
      };
      const created = await api.post<{ id: number }>('/funnels', payload);
      onCreated(created.id);
      // редирект с pulse-флагом
      router.push(`/funnels/${created.id}/edit?welcome=1`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  // Empty state: 0 продуктов
  if (products && !hasProducts) {
    return (
      <WizardShell title="Создание первой воронки" onClose={onClose} step={1} totalSteps={4}>
        <div className="text-center py-6">
          <div className="text-4xl mb-3">📦</div>
          <h3 className="text-lg font-semibold mb-2">Сначала нужен продукт</h3>
          <p className="text-sm text-zinc-600 mb-5 max-w-md mx-auto">
            Воронка прогревает покупателей конкретного продукта. У вас пока ни одного нет —
            создайте, и вы вернётесь сюда с уже выбранным продуктом в wizard'е.
          </p>
          <Link href="/products?return=/funnels">
            <Button>→ Создать первый продукт</Button>
          </Link>
        </div>
      </WizardShell>
    );
  }

  return (
    <WizardShell title="Создание первой воронки" onClose={onClose} step={step} totalSteps={4}>
      {step === 1 && (
        <div className="space-y-4">
          <h3 className="text-base font-semibold">Что продаёте?</h3>
          <Field label="Продукт" required>
            <Select value={productId} onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">— выберите —</option>
              {(products || []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Название воронки" required hint="Внутреннее имя для админа">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Воронка прогрева для клуба" />
          </Field>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="ghost" onClick={onClose}>Отмена</Button>
            <Button onClick={() => setStep(2)} disabled={!productId || !name.trim()}>
              Дальше: Шаблон →
            </Button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <h3 className="text-base font-semibold">Сколько шагов и за какой срок?</h3>
          <div className="space-y-2">
            {Object.entries(TEMPLATES).map(([key, t]) => (
              <label
                key={key}
                className={`block p-3 rounded-xl border-2 cursor-pointer transition ${
                  template === key ? 'border-indigo-500 bg-indigo-50/40' : 'border-zinc-200 hover:border-zinc-300'
                }`}
              >
                <input
                  type="radio"
                  className="sr-only"
                  checked={template === key}
                  onChange={() => setTemplate(key as TemplateKey)}
                />
                <div className="flex items-start gap-3">
                  <div className={`size-5 rounded-full border-2 mt-0.5 shrink-0 ${
                    template === key ? 'border-indigo-500 bg-indigo-500' : 'border-zinc-300'
                  }`}>
                    {template === key && (
                      <svg viewBox="0 0 20 20" fill="white" className="size-full p-0.5">
                        <path d="M16.7 5.3l-9 9-3.4-3.4-1.4 1.4 4.8 4.8 10.4-10.4z" />
                      </svg>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{t.label}</div>
                    {t.steps.length > 0 && (
                      <div className="text-xs text-zinc-500 mt-0.5">
                        Готовые тексты-заглушки — вы их потом отредактируете в студии.
                      </div>
                    )}
                  </div>
                </div>
              </label>
            ))}
          </div>
          <div className="flex justify-between gap-2 pt-4">
            <Button variant="ghost" onClick={() => setStep(1)}>← Назад</Button>
            <Button onClick={() => setStep(4)}>
              Дальше: Создать →
            </Button>
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-4">
          <h3 className="text-base font-semibold">Готово к созданию</h3>
          <div className="rounded-xl glass-soft p-4 text-sm space-y-1.5">
            <div><b>Продукт:</b> {(products || []).find((p) => p.id === productId)?.name}</div>
            <div><b>Название:</b> {name}</div>
            <div><b>Шаблон:</b> {TEMPLATES[template].label}</div>
            <div><b>TTL:</b> 30 дней (можно изменить позже)</div>
          </div>
          <div className="text-xs text-zinc-500">
            После создания вы попадёте в Студию — там добавите лидмагниты, подключите точки входа
            и сможете запустить тестовый прогон. Шаги-заглушки можно отредактировать прямо там.
          </div>
          {error && (
            <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>
          )}
          <div className="flex justify-between gap-2 pt-4">
            <Button variant="ghost" onClick={() => setStep(2)}>← Назад</Button>
            <Button onClick={create} disabled={creating}>
              {creating ? 'Создаём…' : '🚀 Создать воронку'}
            </Button>
          </div>
        </div>
      )}
    </WizardShell>
  );
}


function WizardShell({
  title, onClose, step, totalSteps, children,
}: {
  title: string;
  onClose: () => void;
  step: number;
  totalSteps: number;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 anim-fade">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative glass-strong rounded-2xl max-w-lg w-full p-6 anim-rise max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
            <div className="flex gap-1.5 mt-1">
              {Array.from({ length: totalSteps }).map((_, i) => (
                <div
                  key={i}
                  className={`h-1 rounded-full flex-1 transition ${
                    i + 1 <= step ? 'gradient-primary' : 'bg-zinc-200'
                  }`}
                  style={{ minWidth: 40 }}
                />
              ))}
            </div>
            <div className="text-xs text-zinc-500 mt-1">Шаг {step} из {totalSteps}</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-zinc-400 hover:text-ink transition"
            aria-label="Закрыть"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

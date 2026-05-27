'use client';

import Link from 'next/link';
import { use, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Select,
} from '@/components/ui';
import { ButtonsEditor, type ButtonRows } from '@/components/ButtonsEditor';
import { FunnelProgress, type ProgressStep } from '@/components/FunnelProgress';
import { TelegramPreview } from '@/components/TelegramPreview';
import { RichTextEditor } from '@/components/RichTextEditor';
import { QuickLeadMagnetUpload } from '@/components/QuickLeadMagnetUpload';
import { useFeatures } from '@/lib/features';
import { QuizFormPicker } from '@/components/funnel-studio/QuizFormPicker';
import { SectionHeader } from '@/components/funnel-studio/SectionHeader';
import { StepKindSelector } from '@/components/funnel-studio/StepKindSelector';
import { StepMediaPanel } from '@/components/StepMediaPanel';
import { EntryPointsSection } from '@/components/EntryPointsSection';
import { ObservableTestPanel } from '@/components/ObservableTestPanel';
import { ActiveFunnelWarning, ActiveFunnelConfirm } from '@/components/SafetyWarning';
import { AbTestPlaceholder } from '@/components/AbTestPlaceholder';

type LeadMagnet = { id: number; name: string; file_type: string; file_size: number | null };
type Bot = { id: number; username: string };

type StepMediaBrief = {
  id: number;
  media_type: 'photo' | 'video' | 'animation' | 'audio' | 'document' | 'voice';
  mime_type: string;
  file_size: number;
  order_idx: number;
  caption: string | null;
  has_telegram_file_id: boolean;
  has_thumbnail: boolean;
  original_filename: string | null;
};

type Step = {
  id: number;
  funnel_id: number;
  order_idx: number;
  delay_minutes: number;
  message_text: string;
  parse_mode: string | null;
  lead_magnet_id: number | null;
  buttons: ButtonRows | null;
  is_active: boolean;
  kind: 'message' | 'quiz' | 'form';
  quiz_id: number | null;
  form_id: number | null;
  media: StepMediaBrief[];
};

type FunnelDetail = {
  id: number;
  name: string;
  description: string | null;
  product_id: number;
  bot_id: number | null;
  is_active: boolean;
  ttl_days: number;
  cancel_on_payment: boolean;
  steps_count: number;
  active_entries: number;
  steps: Step[];
};

type EntryPoints = {
  tracking_links: unknown[];
  triggers: unknown[];
  is_product_default: boolean;
  has_any: boolean;
};

type Product = { id: number; name: string; code: string };

const DELAY_UNITS = [
  { label: 'минут', mult: 1 },
  { label: 'часов', mult: 60 },
  { label: 'дней', mult: 1440 },
];

function delayToHuman(minutes: number): { value: number; unit: number } {
  if (minutes % 1440 === 0 && minutes >= 1440) return { value: minutes / 1440, unit: 1440 };
  if (minutes % 60 === 0 && minutes >= 60) return { value: minutes / 60, unit: 60 };
  return { value: minutes, unit: 1 };
}

/**
 * Возвращает мини-метку медиа шага: иконка + цветовая схема + tooltip.
 * Используется в списке шагов (полный режим) и на рельсе (свёрнутый режим).
 *
 * Приоритет: массив step.media (Фаза B) > step.lead_magnet_id (legacy).
 */
function getStepMediaInfo(
  step: Step,
  magnets: LeadMagnet[],
): { icon: string; color: string; dot: string; title: string; count: number } {
  // Новая система: массив media
  if (step.media && step.media.length > 0) {
    const first = step.media[0];
    const count = step.media.length;
    const suffix = count > 1 ? ` (${count})` : '';
    switch (first.media_type) {
      case 'photo':
        return { icon: count > 1 ? '🖼+' : '🖼', color: 'bg-teal-50 text-teal-700', dot: 'bg-teal-400', title: `Изображение${suffix}`, count };
      case 'video':
        return { icon: count > 1 ? '🎬+' : '🎬', color: 'bg-rose-50 text-rose-700', dot: 'bg-rose-400', title: `Видео${suffix}`, count };
      case 'animation':
        return { icon: '🎞', color: 'bg-fuchsia-50 text-fuchsia-700', dot: 'bg-fuchsia-400', title: `Анимация${suffix}`, count };
      case 'audio':
      case 'voice':
        return { icon: '🎵', color: 'bg-amber-50 text-amber-700', dot: 'bg-amber-400', title: `Аудио${suffix}`, count };
      default:
        return { icon: '📎', color: 'bg-zinc-100 text-zinc-700', dot: 'bg-zinc-400', title: `Документ${suffix}`, count };
    }
  }
  // Legacy: lead_magnet_id (для воронок без миграции)
  if (!step.lead_magnet_id) {
    return {
      icon: 'T',
      color: 'bg-zinc-100 text-zinc-500',
      dot: 'bg-zinc-300',
      title: 'Только текст',
      count: 0,
    };
  }
  const lm = (magnets || []).find((m) => m.id === step.lead_magnet_id);
  if (!lm) {
    return { icon: '?', color: 'bg-zinc-100 text-zinc-500', dot: 'bg-zinc-300', title: 'Медиа удалено', count: 0 };
  }
  switch (lm.file_type) {
    case 'image':
      return { icon: '🖼', color: 'bg-teal-50 text-teal-700', dot: 'bg-teal-400', title: `Изображение · ${lm.name}`, count: 1 };
    case 'video':
      return { icon: '🎬', color: 'bg-rose-50 text-rose-700', dot: 'bg-rose-400', title: `Видео · ${lm.name}`, count: 1 };
    case 'pdf':
      return { icon: '📄', color: 'bg-amber-50 text-amber-700', dot: 'bg-amber-400', title: `PDF · ${lm.name}`, count: 1 };
    default:
      return { icon: '📎', color: 'bg-zinc-100 text-zinc-700', dot: 'bg-zinc-400', title: `Файл · ${lm.name}`, count: 1 };
  }
}

export default function FunnelStudioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const search = useSearchParams();
  const welcomeMode = search?.get('welcome') === '1';

  const { isOn: pageIsOn } = useFeatures();
  const { data, mutate } = useSWR<FunnelDetail>(`/funnels/${id}`, fetcher);
  const { data: products } = useSWR<Product[]>('/products', fetcher);
  const { data: magnets, mutate: mutateMagnets } = useSWR<LeadMagnet[]>(
    pageIsOn('lead_magnets') ? '/lead-magnets' : null,
    fetcher,
  );
  const { data: bots } = useSWR<Bot[]>('/bots', fetcher);
  const { data: entryPoints } = useSWR<EntryPoints>(`/funnels/${id}/entry-points`, fetcher);

  const [savingState, setSavingState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [currentSection, setCurrentSection] = useState<string>('s1');

  const refS1 = useRef<HTMLDivElement>(null);
  const refS2 = useRef<HTMLDivElement>(null);
  const refS3 = useRef<HTMLDivElement>(null);
  const refS4 = useRef<HTMLDivElement>(null);
  const refMap: Record<string, React.RefObject<HTMLDivElement | null>> = { s1: refS1, s2: refS2, s3: refS3, s4: refS4 };

  function jumpTo(key: string) {
    setCurrentSection(key);
    refMap[key]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const [pulse, setPulse] = useState<string | null>(welcomeMode ? 's1' : null);
  useEffect(() => {
    if (!welcomeMode) return;
    const order = ['s1', 's2', 's3', 's4'];
    let i = 0;
    const t = setInterval(() => {
      i++;
      if (i >= order.length) { clearInterval(t); setPulse(null); return; }
      setPulse(order[i]);
    }, 1200);
    return () => clearInterval(t);
  }, [welcomeMode]);

  if (!data) return <div className="p-6 text-sm text-zinc-500">Загрузка…</div>;

  const product = products?.find((p) => p.id === data.product_id);
  const bot = bots?.find((b) => b.id === data.bot_id) || bots?.[0];

  const stepsOk = data.steps.length > 0;
  const entryOk = entryPoints?.has_any ?? false;
  const progressSteps: ProgressStep[] = [
    { key: 's1', label: 'Параметры', status: data.name ? 'ok' : 'todo' },
    { key: 's2', label: 'Шаги', count: data.steps.length, status: stepsOk ? 'ok' : 'warn' },
    { key: 's3', label: 'Точки входа', status: entryOk ? 'ok' : 'warn' },
    { key: 's4', label: 'Запуск', status: data.is_active ? 'ok' : 'off' },
  ];

  return (
    <div>
      <PageHeader
        title={data.name || 'Воронка'}
        subtitle={`Шагов: ${data.steps.length} · Активных подписчиков: ${data.active_entries}`}
        action={<Link href="/funnels"><Button variant="ghost">← К списку</Button></Link>}
      />

      <FunnelProgress steps={progressSteps} currentKey={currentSection} onJump={jumpTo} savingState={savingState} />

      <div ref={refS1} id="s1" className={`mb-5 transition ${pulse === 's1' ? 'ring-2 ring-indigo-300 rounded-2xl animate-pulse' : ''}`}>
        <Section1Params funnel={data} onSavingChange={setSavingState} onMutate={() => mutate()} />
      </div>

      <div ref={refS2} id="s2" className={`mb-5 transition ${pulse === 's2' ? 'ring-2 ring-indigo-300 rounded-2xl animate-pulse' : ''}`}>
        <Section2Steps funnel={data} magnets={magnets || []} bot={bot} onMutate={() => mutate()} onMutateMagnets={() => mutateMagnets()} />
      </div>

      <div ref={refS3} id="s3" className={`mb-5 transition ${pulse === 's3' ? 'ring-2 ring-indigo-300 rounded-2xl animate-pulse' : ''}`}>
        <Card padded>
          <SectionHeader n={3} title="Как пользователи попадут в воронку" subtitle="Минимум одна точка входа должна быть подключена" status={entryOk ? 'ok' : 'warn'} />
          <EntryPointsSection funnelId={data.id} productId={data.product_id} productName={product?.name} botUsername={bot?.username} />
        </Card>
      </div>

      <div ref={refS4} id="s4" className={`mb-5 transition ${pulse === 's4' ? 'ring-2 ring-indigo-300 rounded-2xl animate-pulse' : ''}`}>
        <Section4Launch funnel={data} botUsername={bot?.username} stepsOk={stepsOk} entryOk={entryOk} onMutate={() => mutate()} />
      </div>
    </div>
  );
}


function Section1Params({
  funnel, onSavingChange, onMutate,
}: {
  funnel: FunnelDetail;
  onSavingChange: (s: 'idle' | 'saving' | 'saved') => void;
  onMutate: () => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [form, setForm] = useState({
    name: funnel.name,
    description: funnel.description || '',
    ttl_days: funnel.ttl_days,
    is_active: funnel.is_active,
    cancel_on_payment: funnel.cancel_on_payment,
  });

  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const initial = useRef(true);
  useEffect(() => {
    if (initial.current) { initial.current = false; return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    onSavingChange('saving');
    debounceRef.current = setTimeout(async () => {
      try {
        await api.patch(`/funnels/${funnel.id}`, {
          name: form.name.trim(),
          description: form.description.trim() || null,
          ttl_days: form.ttl_days,
          is_active: form.is_active,
          cancel_on_payment: form.cancel_on_payment,
        });
        onSavingChange('saved');
        onMutate();
        setTimeout(() => onSavingChange('idle'), 1500);
      } catch (e) {
        onSavingChange('idle');
        alert(e instanceof Error ? e.message : String(e));
      }
    }, 1000);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.name, form.description, form.ttl_days, form.is_active, form.cancel_on_payment]);

  return (
    <Card padded>
      <SectionHeader n={1} title="Параметры воронки" status="ok" onCollapse={() => setCollapsed(!collapsed)} collapsed={collapsed} />
      {!collapsed && (
        <div className="space-y-4">
          <Field label="Название воронки" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Описание" hint="Внутренняя заметка для админа">
            <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="TTL, дней" hint="За сколько дней воронка авто-закроется если не оплатил">
              <Input type="number" min={1} max={365} value={form.ttl_days} onChange={(e) => setForm({ ...form, ttl_days: Math.max(1, Number(e.target.value) || 1) })} />
            </Field>
            <Field label="Активна сейчас?">
              <Select value={form.is_active ? '1' : '0'} onChange={(e) => setForm({ ...form, is_active: e.target.value === '1' })}>
                <option value="1">Да — пользователи попадают</option>
                <option value="0">Нет — draft</option>
              </Select>
            </Field>
            <Field label="Отменять при оплате?" hint="Не слать follow-up после покупки">
              <Select value={form.cancel_on_payment ? '1' : '0'} onChange={(e) => setForm({ ...form, cancel_on_payment: e.target.value === '1' })}>
                <option value="1">Да (рекомендуется)</option>
                <option value="0">Нет</option>
              </Select>
            </Field>
          </div>
          <div className="text-xs text-zinc-500">💡 Изменения сохраняются автоматически.</div>
        </div>
      )}
    </Card>
  );
}


function Section2Steps({
  funnel, magnets, bot, onMutate, onMutateMagnets,
}: {
  funnel: FunnelDetail;
  magnets: LeadMagnet[];
  bot?: Bot;
  onMutate: () => void;
  onMutateMagnets: () => void;
}) {
  const [editingId, setEditingId] = useState<number | null>(funnel.steps[0]?.id || null);
  const [mobileTab, setMobileTab] = useState<'list' | 'editor' | 'preview'>('list');
  const [dragId, setDragId] = useState<number | null>(null);
  const [dropTargetId, setDropTargetId] = useState<number | null>(null);

  // Сворачиваемый список шагов: persist в localStorage. По умолчанию — развёрнут
  // на широких экранах, свёрнут на узких (< 1280px).
  const [collapsed, setCollapsed] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const raw = window.localStorage.getItem('funnel-studio.steps-list-collapsed');
    if (raw === '1') setCollapsed(true);
    else if (raw === '0') setCollapsed(false);
    else if (window.innerWidth < 1280) setCollapsed(true);
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem('funnel-studio.steps-list-collapsed', next ? '1' : '0');
      } catch {}
      return next;
    });
  }

  // Hotkey ⌘\ / Ctrl+\ переключает свёрнутость. Игнорируется, когда фокус
  // внутри input / textarea / contentEditable — чтобы не ломать набор текста.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key !== '\\') return;
      const a = document.activeElement as HTMLElement | null;
      const tag = a?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || a?.isContentEditable) return;
      e.preventDefault();
      toggleCollapsed();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Re-sync editingId если шагов стало больше/меньше
  useEffect(() => {
    if (editingId && !funnel.steps.some((s) => s.id === editingId)) {
      setEditingId(funnel.steps[0]?.id || null);
    }
    if (!editingId && funnel.steps.length > 0) {
      setEditingId(funnel.steps[0].id);
    }
  }, [funnel.steps, editingId]);

  const editingStep = funnel.steps.find((s) => s.id === editingId) || null;

  async function addStep() {
    const next = funnel.steps.length;
    const created = await api.post<Step>(`/funnels/${funnel.id}/steps`, {
      order_idx: next,
      delay_minutes: next === 0 ? 0 : 1440,
      message_text: 'Здравствуйте, {first_name}!\n\nТекст шага. Поддерживается <b>HTML</b>.',
      parse_mode: 'HTML',
      lead_magnet_id: null,
      buttons: null,
      is_active: true,
    });
    onMutate();
    setEditingId(created.id);
    setMobileTab('editor');
  }

  async function deleteStep(step: Step) {
    if (!confirm(`Удалить шаг ${step.order_idx + 1}?`)) return;
    await api.del(`/funnel-steps/${step.id}`);
    onMutate();
    if (editingId === step.id) setEditingId(null);
  }

  async function reorder(targetId: number) {
    if (dragId === null || dragId === targetId) return;
    const ids = funnel.steps.map((s) => s.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) return;
    const newIds = [...ids];
    newIds.splice(from, 1);
    newIds.splice(to, 0, dragId);
    setDragId(null);
    setDropTargetId(null);
    try {
      await api.post(`/funnels/${funnel.id}/reorder`, { ordered_step_ids: newIds });
      onMutate();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <Card padded>
      <SectionHeader n={2} title={`Шаги воронки${funnel.steps.length ? ` (${funnel.steps.length})` : ''}`} status={funnel.steps.length ? 'ok' : 'warn'} />

      {funnel.steps.length === 0 && (
        <Empty>
          <div>Шагов ещё нет</div>
          <Button onClick={addStep} className="mt-3">+ Добавить первый шаг</Button>
        </Empty>
      )}

      {funnel.steps.length > 0 && (
        <>
          <div className="lg:hidden mb-3 inline-flex glass-soft rounded-xl p-1 text-xs">
            {(['list', 'editor', 'preview'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setMobileTab(t)}
                className={`px-3 h-8 rounded-lg transition ${mobileTab === t ? 'bg-white shadow-soft' : 'text-zinc-500'}`}
              >
                {t === 'list' ? `Список (${funnel.steps.length})` : t === 'editor' ? 'Редактор' : 'Превью'}
              </button>
            ))}
          </div>

          <div
            className={`grid grid-cols-1 gap-3 transition-[grid-template-columns] duration-200 ease-in-out ${
              collapsed
                ? 'lg:grid-cols-[56px_2.5fr_1fr]'
                : 'lg:grid-cols-[1fr_1.5fr_1fr]'
            }`}
          >
            {/* Развёрнутый список */}
            {!collapsed && (
              <div className={mobileTab === 'list' ? '' : 'hidden lg:block'}>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs uppercase tracking-wider text-zinc-500">Шаги</h4>
                  <div className="flex items-center gap-1">
                    <Button size="sm" onClick={addStep}>+ Шаг</Button>
                    <button
                      type="button"
                      onClick={toggleCollapsed}
                      title="Свернуть список (⌘\)"
                      className="hidden lg:inline-flex w-7 h-7 items-center justify-center rounded-md text-zinc-400 hover:text-zinc-700 hover:bg-white/70 transition"
                    >
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 19l-7-7 7-7M20 19l-7-7 7-7" />
                      </svg>
                    </button>
                  </div>
                </div>
                <ul className="space-y-2">
                  {funnel.steps.map((s) => {
                    const h = delayToHuman(s.delay_minutes);
                    const unitLabel = DELAY_UNITS.find((u) => u.mult === h.unit)?.label || 'мин';
                    const lm = (magnets || []).find((m) => m.id === s.lead_magnet_id);
                    const media = getStepMediaInfo(s, magnets);
                    const isDropTarget = dropTargetId === s.id && dragId !== s.id;
                    return (
                      <li
                        key={s.id}
                        draggable
                        onDragStart={() => setDragId(s.id)}
                        onDragEnd={() => { setDragId(null); setDropTargetId(null); }}
                        onDragOver={(e) => { e.preventDefault(); setDropTargetId(s.id); }}
                        onDragLeave={() => { if (dropTargetId === s.id) setDropTargetId(null); }}
                        onDrop={() => reorder(s.id)}
                        className={`glass rounded-xl px-3 py-2.5 cursor-grab active:cursor-grabbing transition ${
                          editingId === s.id ? 'ring-2 ring-indigo-400' : 'hover:bg-white/70'
                        } ${isDropTarget ? 'border-t-4 border-indigo-500' : ''}`}
                        onClick={() => { setEditingId(s.id); setMobileTab('editor'); }}
                      >
                        <div className="flex items-center gap-2.5">
                          {/* Миниатюра типа медиа */}
                          <div
                            className={`size-10 rounded-lg flex items-center justify-center text-base shrink-0 ${media.color}`}
                            title={media.title}
                          >
                            {media.icon}
                          </div>
                          {/* Номер */}
                          <span className="size-6 rounded-md gradient-primary text-white text-[10px] font-semibold flex items-center justify-center shadow-soft shrink-0">
                            {s.order_idx + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium truncate">
                              {s.message_text.slice(0, 50)}{s.message_text.length > 50 && '…'}
                            </div>
                            <div className="text-[11px] text-zinc-500">
                              через {h.value} {unitLabel}
                              {lm && <span> · {lm.name.slice(0, 20)}</span>}
                              {!s.is_active && <span className="text-rose-500"> · OFF</span>}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="text-zinc-400 hover:text-rose-600 transition text-xs shrink-0"
                            onClick={(e) => { e.stopPropagation(); deleteStep(s); }}
                          >
                            ✕
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {/* Свёрнутый рельс — только на desktop */}
            {collapsed && (
              <div className="hidden lg:flex lg:flex-col gap-1 items-center pt-1">
                <button
                  type="button"
                  onClick={toggleCollapsed}
                  title="Развернуть список (⌘\)"
                  className="w-8 h-8 mb-1 flex items-center justify-center rounded-md text-zinc-400 hover:text-zinc-700 hover:bg-white/70 transition"
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M13 19l7-7-7-7M4 19l7-7-7-7" />
                  </svg>
                </button>
                {funnel.steps.map((s) => {
                  const media = getStepMediaInfo(s, magnets);
                  const h = delayToHuman(s.delay_minutes);
                  const unitLabel = DELAY_UNITS.find((u) => u.mult === h.unit)?.label || 'мин';
                  const isActive = editingId === s.id;
                  const isDropTarget = dropTargetId === s.id && dragId !== s.id;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      draggable
                      onDragStart={() => setDragId(s.id)}
                      onDragEnd={() => { setDragId(null); setDropTargetId(null); }}
                      onDragOver={(e) => { e.preventDefault(); setDropTargetId(s.id); }}
                      onDragLeave={() => { if (dropTargetId === s.id) setDropTargetId(null); }}
                      onDrop={() => reorder(s.id)}
                      onClick={() => setEditingId(s.id)}
                      title={`Шаг ${s.order_idx + 1} · через ${h.value} ${unitLabel}\n${media.title}${!s.is_active ? ' · выключен' : ''}\n${s.message_text.slice(0, 80)}`}
                      className={`relative w-10 h-10 rounded-lg flex items-center justify-center text-xs font-semibold transition shrink-0 ${
                        isActive
                          ? 'gradient-primary text-white shadow-soft'
                          : 'glass text-zinc-700 hover:bg-white/80'
                      } ${!s.is_active ? 'opacity-50' : ''} ${
                        isDropTarget ? 'ring-2 ring-indigo-500' : ''
                      }`}
                    >
                      {s.order_idx + 1}
                      <span
                        className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white ${media.dot}`}
                      />
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={addStep}
                  title="Добавить шаг"
                  className="w-10 h-10 mt-1 rounded-lg border-2 border-dashed border-zinc-300 text-zinc-400 hover:border-indigo-400 hover:text-indigo-500 hover:bg-indigo-50/40 transition flex items-center justify-center text-lg shrink-0"
                >
                  +
                </button>
              </div>
            )}

            <div className={mobileTab === 'editor' ? '' : 'hidden lg:block'}>
              <h4 className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Редактор</h4>
              {editingStep ? (
                <StepEditor
                  step={editingStep}
                  funnel={funnel}
                  magnets={magnets}
                  onMutate={onMutate}
                  onMutateMagnets={onMutateMagnets}
                />
              ) : (
                <div className="text-sm text-zinc-500 py-6 text-center">Выберите шаг слева</div>
              )}
            </div>

            <div className={mobileTab === 'preview' ? '' : 'hidden lg:block'}>
              <h4 className="text-xs uppercase tracking-wider text-zinc-500 mb-2">Превью Telegram</h4>
              {editingStep ? (
                <TelegramPreview
                  text={editingStep.message_text}
                  leadMagnet={editingStep.lead_magnet_id ? (magnets || []).find((m) => m.id === editingStep.lead_magnet_id) || null : null}
                  buttons={editingStep.buttons}
                  botUsername={bot?.username}
                  stepMedia={editingStep.media || []}
                />
              ) : (
                <div className="text-sm text-zinc-500 py-6 text-center">Выберите шаг чтобы увидеть превью</div>
              )}
            </div>
          </div>
        </>
      )}
    </Card>
  );
}


function StepEditor({
  step, funnel, magnets, onMutate, onMutateMagnets,
}: {
  step: Step;
  funnel: FunnelDetail;
  magnets: LeadMagnet[];
  onMutate: () => void;
  onMutateMagnets: () => void;
}) {
  const [local, setLocal] = useState<Step>(step);
  const [saving, setSaving] = useState(false);
  const [magnetUploadOpen, setMagnetUploadOpen] = useState(false);
  const [confirmActive, setConfirmActive] = useState(false);
  const isActive = funnel.is_active && funnel.active_entries > 0;
  const human = delayToHuman(local.delay_minutes);

  useEffect(() => { setLocal(step); }, [step.id]);

  const dirty = JSON.stringify(local) !== JSON.stringify(step);

  async function persist() {
    if (isActive && dirty) { setConfirmActive(true); return; }
    await reallyPersist();
  }

  async function reallyPersist() {
    setSaving(true);
    try {
      await api.patch(`/funnel-steps/${local.id}`, {
        order_idx: local.order_idx,
        delay_minutes: local.delay_minutes,
        message_text: local.message_text,
        parse_mode: local.parse_mode || 'HTML',
        lead_magnet_id: local.lead_magnet_id,
        buttons: local.buttons,
        is_active: local.is_active,
        kind: local.kind,
        quiz_id: local.quiz_id,
        form_id: local.form_id,
      });
      onMutate();
      setConfirmActive(false);
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally { setSaving(false); }
  }

  const { isOn } = useFeatures();
  const isQuiz = local.kind === 'quiz';
  const isForm = local.kind === 'form';
  const isMessage = !isQuiz && !isForm;

  return (
    <div className="space-y-3">
      {isActive && dirty && (
        <ActiveFunnelWarning
          activeEntries={funnel.active_entries}
          estimatedAffected={Math.ceil(funnel.active_entries / 4)}
        >
          Изменения сохранятся только после явного подтверждения.
        </ActiveFunnelWarning>
      )}

      <AbTestPlaceholder stepId={local.id} />

      {/* Тип шага */}
      <Field
        label="Тип шага"
        hint={
          isMessage
            ? 'Обычное сообщение — отправляется юзеру по расписанию (delay).'
            : isQuiz
            ? 'Контейнер квиза. Сам в чат не уходит — открывается кнопкой quiz:start.'
            : 'Контейнер формы. Открывается кнопкой form:start.'
        }
      >
        <StepKindSelector
          kind={local.kind}
          allowQuiz={isOn('quizzes')}
          allowForm={isOn('forms')}
          onChange={(nextKind) => {
            if (nextKind === local.kind) return;
            // При смене типа: квиз/форма — контейнеры (is_active=false, delay_minutes=0),
            // сообщение — обычный шаг. Возвращая на message, восстанавливаем delay из
            // оригинального step (если был сохранён ранее) или 1440 (сутки).
            if (nextKind === 'message') {
              const restoredDelay = step.kind === 'message' ? step.delay_minutes : 1440;
              setLocal({
                ...local,
                kind: 'message',
                quiz_id: null,
                form_id: null,
                is_active: true,
                delay_minutes: local.delay_minutes || restoredDelay,
              });
            } else if (nextKind === 'quiz') {
              setLocal({ ...local, kind: 'quiz', form_id: null, is_active: false, delay_minutes: 0 });
            } else {
              setLocal({ ...local, kind: 'form', quiz_id: null, is_active: false, delay_minutes: 0 });
            }
          }}
        />
      </Field>

      {/* Селектор квиза / формы для container-шагов */}
      {(isQuiz || isForm) && (
        <Field
          label={isQuiz ? 'Какой квиз привязать' : 'Какую форму привязать'}
          hint={
            isQuiz
              ? 'Управление вопросами и вердиктами — в разделе «Квизы».'
              : 'Управление полями и success-сообщением — в разделе «Формы».'
          }
        >
          <QuizFormPicker
            kind={local.kind as 'quiz' | 'form'}
            value={isQuiz ? local.quiz_id : local.form_id}
            onChange={(id) => {
              if (isQuiz) setLocal({ ...local, quiz_id: id });
              else setLocal({ ...local, form_id: id });
            }}
          />
        </Field>
      )}

      {/* Параметры расписания — только для message */}
      {isMessage && (
        <div className="grid grid-cols-3 gap-2">
          <Field label="Задержка">
            <Input type="number" min={0} value={human.value} onChange={(e) => setLocal({ ...local, delay_minutes: Number(e.target.value) * human.unit })} />
          </Field>
          <Field label="Единица">
            <Select value={human.unit} onChange={(e) => setLocal({ ...local, delay_minutes: human.value * Number(e.target.value) })}>
              {DELAY_UNITS.map((u) => <option key={u.mult} value={u.mult}>{u.label}</option>)}
            </Select>
          </Field>
          <Field label="Активен">
            <Select value={local.is_active ? '1' : '0'} onChange={(e) => setLocal({ ...local, is_active: e.target.value === '1' })}>
              <option value="1">Да</option>
              <option value="0">Нет</option>
            </Select>
          </Field>
        </div>
      )}

      {/* Текст / медиа / лидмагнит / кнопки — только для message */}
      {isMessage ? (
        <>
          <Field
            label="Текст сообщения"
            hint="Выделите фрагмент и примените форматирование тулбаром. Поддерживаются жирный, курсив, моноширинный, цитаты, спойлеры, ссылки. Превью справа обновляется на лету."
          >
            <RichTextEditor
              rows={8}
              value={local.message_text}
              onChange={(next) => setLocal({ ...local, message_text: next })}
              placeholders={['first_name', 'username']}
            />
          </Field>

          <Field
            label="Медиа шага"
            hint="До 10 файлов (фото / видео / документ). Если ≥2 — отправятся альбомом. Если 1 — с подписью и кнопками. Фото ≤ 10 MB, остальное ≤ 50 MB."
          >
            <StepMediaPanel stepId={local.id} />
          </Field>

          {isOn('lead_magnets') && (
          <Field
            label="Готовый лидмагнит (старый формат)"
            hint="Опционально, если хотите выбрать ранее загруженный лидмагнит из библиотеки. Отправится после текста, если на шаге нет своих медиа выше."
          >
            <div className="flex gap-2">
              <Select
                className="flex-1"
                value={local.lead_magnet_id ?? ''}
                onChange={(e) => setLocal({ ...local, lead_magnet_id: e.target.value ? Number(e.target.value) : null })}
              >
                <option value="">— без лидмагнита —</option>
                {(magnets || []).map((m) => (
                  <option key={m.id} value={m.id}>{m.name} ({m.file_type})</option>
                ))}
              </Select>
              <Button variant="ghost" size="md" onClick={() => setMagnetUploadOpen(true)}>+ Загрузить</Button>
            </div>
          </Field>
          )}

          <Field label="Inline-кнопки" hint="Опционально. Системная «🔕 Не присылать» добавляется автоматически.">
            <ButtonsEditor
              value={local.buttons}
              onChange={(rows) => setLocal({ ...local, buttons: rows })}
              funnelId={funnel.id}
            />
          </Field>
        </>
      ) : (
        <div className="glass-soft rounded-xl px-4 py-3 text-sm text-zinc-600">
          <p className="mb-1">
            {isQuiz ? '🧠 Шаг-контейнер квиза.' : '📋 Шаг-контейнер формы.'} Не отправляется в чат напрямую.
          </p>
          <p className="text-xs text-zinc-500">
            Юзер попадает сюда только через кнопку с типом
            «{isQuiz ? 'Запустить квиз' : 'Открыть форму'}»
            на любом message-шаге (или внешней trigger-кнопке).
          </p>
        </div>
      )}

      <div className="flex justify-between items-center pt-2">
        <div className="text-xs text-zinc-500">
          {local.message_text.length} симв.
          {dirty && <span className="text-amber-600 ml-2">• несохранено</span>}
        </div>
        <Button onClick={persist} disabled={saving || !dirty || !local.message_text.trim()}>
          {saving ? 'Сохраняем…' : 'Сохранить шаг'}
        </Button>
      </div>

      <QuickLeadMagnetUpload
        open={magnetUploadOpen}
        onClose={() => setMagnetUploadOpen(false)}
        productId={funnel.product_id}
        onUploaded={(lm) => {
          onMutateMagnets();
          setLocal({ ...local, lead_magnet_id: lm.id });
        }}
      />

      <ActiveFunnelConfirm
        open={confirmActive}
        activeEntries={funnel.active_entries}
        estimatedAffected={Math.ceil(funnel.active_entries / 4)}
        onCancel={() => setConfirmActive(false)}
        onConfirm={reallyPersist}
      />
    </div>
  );
}


function Section4Launch({
  funnel, botUsername, stepsOk, entryOk, onMutate,
}: {
  funnel: FunnelDetail;
  botUsername?: string;
  stepsOk: boolean;
  entryOk: boolean;
  onMutate: () => void;
}) {
  const [testRunId, setTestRunId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const allReady = stepsOk && entryOk;

  async function runTest() {
    setBusy(true);
    try {
      const res = await api.post<{ test_entry_id: number }>(`/funnels/${funnel.id}/test-run`);
      setTestRunId(res.test_entry_id);
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  async function activate() {
    try {
      await api.patch(`/funnels/${funnel.id}`, { is_active: true });
      onMutate();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  async function deactivate() {
    if (!confirm('Деактивировать воронку? Новые пользователи в неё не попадут.')) return;
    try {
      await api.patch(`/funnels/${funnel.id}`, { is_active: false });
      onMutate();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <Card padded>
      <SectionHeader n={4} title="Запуск" status={funnel.is_active ? 'ok' : 'off'} />

      <div className="space-y-3">
        <div className="text-sm">
          Статус: {funnel.is_active ? (
            <span className="text-emerald-700 font-medium">🟢 Активна</span>
          ) : allReady ? (
            <span className="text-amber-700 font-medium">🟡 Готова к активации</span>
          ) : (
            <span className="text-zinc-500">⚫ Не настроена</span>
          )}
        </div>

        <div className="text-xs text-zinc-600 space-y-1.5 rounded-xl bg-zinc-50/60 p-3">
          <div>• Пользователи попадают в воронку через подключённые точки входа</div>
          <div>• Каждый получает шаги по очереди с указанными задержками</div>
          <div>• При оплате продукта — недотправленные шаги отменяются (если включено)</div>
          <div>• Деактивация останавливает новые подписки; уже подписанные продолжат получать шаги</div>
        </div>

        <div className="flex gap-2 flex-wrap">
          <Button onClick={runTest} variant="ghost" disabled={busy || !stepsOk}>
            {busy ? 'Запускаем…' : '▶ Тест на меня (x60)'}
          </Button>
          {funnel.is_active ? (
            <Button onClick={deactivate} variant="danger">Деактивировать</Button>
          ) : (
            <Button onClick={activate} disabled={!allReady}>🚀 Активировать</Button>
          )}
        </div>

        {!allReady && (
          <div className="text-xs text-amber-700 bg-amber-50/60 border border-amber-200/60 rounded-xl px-3 py-2">
            Нельзя активировать: {!stepsOk && 'нет шагов'}{!stepsOk && !entryOk && ' и '}{!entryOk && 'нет точек входа'}.
          </div>
        )}

        {testRunId && (
          <ObservableTestPanel
            funnelId={funnel.id}
            testEntryId={testRunId}
            botUsername={botUsername}
            onClose={() => setTestRunId(null)}
          />
        )}
      </div>
    </Card>
  );
}


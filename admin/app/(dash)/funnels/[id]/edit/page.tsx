'use client';

import Link from 'next/link';
import { use, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Select, Textarea,
} from '@/components/ui';
import { ButtonsEditor, type ButtonRows } from '@/components/ButtonsEditor';
import { FunnelProgress, type ProgressStep } from '@/components/FunnelProgress';
import { TelegramPreview } from '@/components/TelegramPreview';
import { QuickLeadMagnetUpload } from '@/components/QuickLeadMagnetUpload';
import { EntryPointsSection } from '@/components/EntryPointsSection';
import { ObservableTestPanel } from '@/components/ObservableTestPanel';
import { ActiveFunnelWarning, ActiveFunnelConfirm } from '@/components/SafetyWarning';
import { AbTestPlaceholder } from '@/components/AbTestPlaceholder';

type LeadMagnet = { id: number; name: string; file_type: string; file_size: number | null };
type Bot = { id: number; username: string };

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

export default function FunnelStudioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const search = useSearchParams();
  const welcomeMode = search?.get('welcome') === '1';

  const { data, mutate } = useSWR<FunnelDetail>(`/funnels/${id}`, fetcher);
  const { data: products } = useSWR<Product[]>('/products', fetcher);
  const { data: magnets, mutate: mutateMagnets } = useSWR<LeadMagnet[]>('/lead-magnets', fetcher);
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

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr_1fr] gap-3">
            <div className={mobileTab === 'list' ? '' : 'hidden lg:block'}>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs uppercase tracking-wider text-zinc-500">Шаги</h4>
                <Button size="sm" onClick={addStep}>+ Шаг</Button>
              </div>
              <ul className="space-y-2">
                {funnel.steps.map((s) => {
                  const h = delayToHuman(s.delay_minutes);
                  const unitLabel = DELAY_UNITS.find((u) => u.mult === h.unit)?.label || 'мин';
                  const lm = magnets.find((m) => m.id === s.lead_magnet_id);
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
                      <div className="flex items-center gap-3">
                        <span className="size-7 rounded-lg gradient-primary text-white text-[11px] font-semibold flex items-center justify-center shadow-soft shrink-0">
                          {s.order_idx + 1}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">
                            {s.message_text.slice(0, 50)}{s.message_text.length > 50 && '…'}
                          </div>
                          <div className="text-[11px] text-zinc-500">
                            через {h.value} {unitLabel}
                            {lm && <span> · 📎 {lm.name.slice(0, 20)}</span>}
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
                  leadMagnet={editingStep.lead_magnet_id ? magnets.find((m) => m.id === editingStep.lead_magnet_id) || null : null}
                  buttons={editingStep.buttons}
                  botUsername={bot?.username}
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
      });
      onMutate();
      setConfirmActive(false);
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally { setSaving(false); }
  }

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

      <Field label="Текст сообщения" hint="HTML: <b>, <i>, <a href=…>. Плейсхолдеры: {first_name}, {username}. Превью справа обновляется на лету.">
        <Textarea
          rows={6}
          value={local.message_text}
          onChange={(e) => setLocal({ ...local, message_text: e.target.value })}
        />
      </Field>

      <Field
        label="Лидмагнит"
        hint="PDF / видео придёт пользователю отдельным сообщением после текста. Создаёт ощущение «получил ценность бесплатно»."
      >
        <div className="flex gap-2">
          <Select
            className="flex-1"
            value={local.lead_magnet_id ?? ''}
            onChange={(e) => setLocal({ ...local, lead_magnet_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">— без лидмагнита —</option>
            {magnets.map((m) => (
              <option key={m.id} value={m.id}>{m.name} ({m.file_type})</option>
            ))}
          </Select>
          <Button variant="ghost" size="md" onClick={() => setMagnetUploadOpen(true)}>+ Загрузить</Button>
        </div>
      </Field>

      <Field label="Inline-кнопки" hint="Опционально. Системная «🔕 Не присылать» добавляется автоматически.">
        <ButtonsEditor value={local.buttons} onChange={(rows) => setLocal({ ...local, buttons: rows })} />
      </Field>

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


function SectionHeader({
  n, title, subtitle, status, onCollapse, collapsed,
}: {
  n: number;
  title: string;
  subtitle?: string;
  status: 'ok' | 'warn' | 'todo' | 'off';
  onCollapse?: () => void;
  collapsed?: boolean;
}) {
  const icon = { ok: '✅', warn: '❗', todo: '⚪', off: '🔘' }[status];
  return (
    <div className="flex items-start justify-between gap-3 mb-3">
      <div className="flex items-center gap-2 min-w-0">
        <span className="size-7 rounded-lg gradient-primary text-white text-xs font-bold flex items-center justify-center shrink-0">
          §{n}
        </span>
        <div>
          <h3 className="font-semibold text-base flex items-center gap-2">
            <span>{title}</span>
            <span className="text-sm">{icon}</span>
          </h3>
          {subtitle && <div className="text-xs text-zinc-500 mt-0.5">{subtitle}</div>}
        </div>
      </div>
      {onCollapse && (
        <button type="button" onClick={onCollapse} className="text-xs text-zinc-500 hover:text-ink">
          {collapsed ? '⌄ Раскрыть' : '⌃ Свернуть'}
        </button>
      )}
    </div>
  );
}

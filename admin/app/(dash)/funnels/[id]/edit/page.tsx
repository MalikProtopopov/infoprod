'use client';

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Select, Sheet,
  Textarea,
} from '@/components/ui';

type LeadMagnet = { id: number; name: string; file_type: string };

type Step = {
  id: number;
  funnel_id: number;
  order_idx: number;
  delay_minutes: number;
  message_text: string;
  parse_mode: string | null;
  lead_magnet_id: number | null;
  buttons: unknown;
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

export default function FunnelEditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, mutate } = useSWR<FunnelDetail>(`/funnels/${id}`, fetcher);
  const { data: products } = useSWR<{ id: number; name: string }[]>(`/products`, fetcher);
  const { data: magnets } = useSWR<LeadMagnet[]>(`/lead-magnets`, fetcher);

  const [steps, setSteps] = useState<Step[]>([]);
  const [editingStep, setEditingStep] = useState<Step | null>(null);
  const [savingMeta, setSavingMeta] = useState(false);
  const [savingStep, setSavingStep] = useState(false);
  const [dragId, setDragId] = useState<number | null>(null);

  // Meta-форма
  const [meta, setMeta] = useState({
    name: '', description: '', ttl_days: 90, is_active: true, cancel_on_payment: true,
  });

  useEffect(() => {
    if (data) {
      setSteps(data.steps);
      setMeta({
        name: data.name,
        description: data.description || '',
        ttl_days: data.ttl_days,
        is_active: data.is_active,
        cancel_on_payment: data.cancel_on_payment,
      });
    }
  }, [data]);

  if (!data) return <div className="p-6 text-sm text-zinc-500">Загрузка…</div>;

  async function saveMeta() {
    setSavingMeta(true);
    try {
      await api.patch(`/funnels/${id}`, {
        name: meta.name.trim(),
        description: meta.description.trim() || null,
        ttl_days: meta.ttl_days,
        is_active: meta.is_active,
        cancel_on_payment: meta.cancel_on_payment,
      });
      mutate();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally { setSavingMeta(false); }
  }

  async function addStep() {
    const next = steps.length;
    const created = await api.post<Step>(`/funnels/${id}/steps`, {
      order_idx: next,
      delay_minutes: next === 0 ? 0 : 60,
      message_text: '— Текст шага —',
      parse_mode: 'HTML',
      lead_magnet_id: null,
      buttons: null,
      is_active: true,
    });
    mutate();
    setEditingStep(created);
  }

  async function deleteStep(step: Step) {
    if (!confirm(`Удалить шаг ${step.order_idx + 1}?`)) return;
    await api.del(`/funnel-steps/${step.id}`);
    mutate();
    if (editingStep?.id === step.id) setEditingStep(null);
  }

  async function persistStep(s: Step) {
    setSavingStep(true);
    try {
      await api.patch<Step>(`/funnel-steps/${s.id}`, {
        order_idx: s.order_idx,
        delay_minutes: s.delay_minutes,
        message_text: s.message_text,
        parse_mode: s.parse_mode || 'HTML',
        lead_magnet_id: s.lead_magnet_id,
        buttons: s.buttons,
        is_active: s.is_active,
      });
      mutate();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    } finally { setSavingStep(false); }
  }

  // ─── Drag and drop ──────────────────────────
  function onDragStart(stepId: number) {
    setDragId(stepId);
  }
  async function onDrop(targetId: number) {
    if (dragId === null || dragId === targetId) return;
    const ids = steps.map((s) => s.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) return;
    const newIds = [...ids];
    newIds.splice(from, 1);
    newIds.splice(to, 0, dragId);
    const newSteps = newIds.map((idd, idx) => ({
      ...steps.find((s) => s.id === idd)!,
      order_idx: idx,
    }));
    setSteps(newSteps);
    setDragId(null);
    try {
      await api.post(`/funnels/${id}/reorder`, { ordered_step_ids: newIds });
      mutate();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
      mutate(); // вернёт серверное состояние
    }
  }

  return (
    <div>
      <PageHeader
        title={data.name || 'Воронка'}
        subtitle={`Шагов: ${steps.length} · Активных подписчиков: ${data.active_entries}`}
        action={
          <Link href="/funnels"><Button variant="ghost">← К списку</Button></Link>
        }
      />

      {/* ── Мета ── */}
      <Card padded className="mb-5 anim-rise">
        <h3 className="font-semibold mb-3">Параметры воронки</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Название">
            <Input value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} />
          </Field>
          <Field label="Описание" hint="Внутренняя заметка">
            <Input value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} />
          </Field>
          <Field label="TTL, дней">
            <Input type="number" min={1} max={365} value={meta.ttl_days}
                    onChange={(e) => setMeta({ ...meta, ttl_days: Number(e.target.value) })} />
          </Field>
          <Field label="Активность">
            <Select value={meta.is_active ? '1' : '0'} onChange={(e) => setMeta({ ...meta, is_active: e.target.value === '1' })}>
              <option value="1">Активна</option>
              <option value="0">Выключена</option>
            </Select>
          </Field>
          <Field label="Auto-cancel при оплате">
            <Select value={meta.cancel_on_payment ? '1' : '0'} onChange={(e) => setMeta({ ...meta, cancel_on_payment: e.target.value === '1' })}>
              <option value="1">Да</option>
              <option value="0">Нет</option>
            </Select>
          </Field>
        </div>
        <div className="mt-4 flex justify-end">
          <Button onClick={saveMeta} disabled={savingMeta}>{savingMeta ? 'Сохраняем…' : 'Сохранить'}</Button>
        </div>
      </Card>

      {/* ── Шаги + редактор ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Список шагов */}
        <Card padded className="anim-rise">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">Шаги</h3>
            <Button size="sm" onClick={addStep}>+ Добавить шаг</Button>
          </div>
          {steps.length === 0 && <Empty>Шагов ещё нет</Empty>}
          <ul className="space-y-2">
            {steps.map((s) => {
              const human = delayToHuman(s.delay_minutes);
              const unitLabel = DELAY_UNITS.find((u) => u.mult === human.unit)?.label || 'мин';
              return (
                <li
                  key={s.id}
                  draggable
                  onDragStart={() => onDragStart(s.id)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => onDrop(s.id)}
                  className={`glass rounded-xl px-3 py-2.5 cursor-grab active:cursor-grabbing transition ${editingStep?.id === s.id ? 'ring-2 ring-indigo-400' : 'hover:bg-white/60'}`}
                  onClick={() => setEditingStep(s)}
                >
                  <div className="flex items-center gap-3">
                    <span className="size-7 rounded-lg gradient-primary text-white text-[11px] font-semibold flex items-center justify-center shadow-soft">
                      {s.order_idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">
                        {s.message_text.slice(0, 60)}{s.message_text.length > 60 && '…'}
                      </div>
                      <div className="text-xs text-zinc-500">
                        через {human.value} {unitLabel}
                        {s.lead_magnet_id && <span> · с лидмагнитом</span>}
                        {!s.is_active && <span className="text-rose-500"> · отключён</span>}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="text-zinc-400 hover:text-rose-600 transition text-xs"
                      onClick={(e) => { e.stopPropagation(); deleteStep(s); }}
                    >
                      Удалить
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>

        {/* Редактор шага */}
        <Card padded className="anim-rise">
          <h3 className="font-semibold mb-3">
            {editingStep ? `Редактор шага ${editingStep.order_idx + 1}` : 'Выберите шаг для редактирования'}
          </h3>
          {editingStep ? (
            <StepEditor
              step={editingStep}
              magnets={magnets || []}
              onChange={setEditingStep}
              onSave={() => persistStep(editingStep)}
              saving={savingStep}
            />
          ) : (
            <div className="text-sm text-zinc-500">Кликните на шаг слева</div>
          )}
        </Card>
      </div>
    </div>
  );
}


function StepEditor({
  step, magnets, onChange, onSave, saving,
}: {
  step: Step;
  magnets: LeadMagnet[];
  onChange: (s: Step) => void;
  onSave: () => void;
  saving: boolean;
}) {
  const human = delayToHuman(step.delay_minutes);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <Field label="Задержка">
          <Input
            type="number" min={0}
            value={human.value}
            onChange={(e) => onChange({
              ...step,
              delay_minutes: Number(e.target.value) * human.unit,
            })}
          />
        </Field>
        <Field label="Единица">
          <Select
            value={human.unit}
            onChange={(e) => onChange({
              ...step,
              delay_minutes: human.value * Number(e.target.value),
            })}
          >
            {DELAY_UNITS.map((u) => (
              <option key={u.mult} value={u.mult}>{u.label}</option>
            ))}
          </Select>
        </Field>
        <Field label="Активен">
          <Select value={step.is_active ? '1' : '0'} onChange={(e) => onChange({ ...step, is_active: e.target.value === '1' })}>
            <option value="1">Да</option>
            <option value="0">Нет</option>
          </Select>
        </Field>
      </div>

      <Field label="Текст сообщения" hint="HTML разрешён: <b>, <i>, <a>. Плейсхолдер: {first_name}">
        <Textarea
          rows={8}
          value={step.message_text}
          onChange={(e) => onChange({ ...step, message_text: e.target.value })}
        />
      </Field>

      <Field label="Лидмагнит (опц.)" hint="Файл отправится отдельным сообщением после текста">
        <Select
          value={step.lead_magnet_id ?? ''}
          onChange={(e) => onChange({
            ...step,
            lead_magnet_id: e.target.value ? Number(e.target.value) : null,
          })}
        >
          <option value="">— без лидмагнита —</option>
          {magnets.map((m) => (
            <option key={m.id} value={m.id}>{m.name} ({m.file_type})</option>
          ))}
        </Select>
      </Field>

      <div className="flex justify-between items-center pt-2">
        <div className="text-xs text-zinc-500">
          {step.message_text.length} симв.
        </div>
        <Button onClick={onSave} disabled={saving || !step.message_text.trim()}>
          {saving ? 'Сохраняем…' : 'Сохранить шаг'}
        </Button>
      </div>
    </div>
  );
}

'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { use, useEffect, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, IconButton, Input, PageHeader, Pill, Skeleton, Textarea,
} from '@/components/ui';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { useToast } from '@/components/Toast';

type QuizOption = { id?: number; order_idx?: number; text: string; score: number };
type QuizQuestion = {
  id?: number;
  order_idx?: number;
  text: string;
  prefix: string | null;
  options: QuizOption[];
};
type QuizVerdict = {
  id?: number;
  order_idx?: number;
  max_score: number;
  text: string;
  button_text: string | null;
  button_action: string | null;
};
type QuizDetail = {
  id: number;
  name: string;
  description: string | null;
  questions: QuizQuestion[];
  verdicts: QuizVerdict[];
  created_at: string;
  updated_at: string;
};

export default function QuizEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { showToast } = useToast();
  const { data, mutate, isLoading } = useSWR<QuizDetail>(`/quizzes/${id}`, fetcher);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [verdicts, setVerdicts] = useState<QuizVerdict[]>([]);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Pull в локальное состояние когда данные пришли
  useEffect(() => {
    if (!data) return;
    setName(data.name);
    setDescription(data.description || '');
    setQuestions(data.questions);
    setVerdicts(data.verdicts);
    setDirty(false);
  }, [data]);

  function markDirty() {
    setDirty(true);
  }

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      // Зачищаем id у вложенных — PATCH делает full-replace, серверу id не нужны
      const cleanQuestions = questions.map((q, qi) => ({
        text: q.text,
        prefix: q.prefix,
        order_idx: qi,
        options: q.options.map((o, oi) => ({
          text: o.text,
          score: Number(o.score) || 0,
          order_idx: oi,
        })),
      }));
      const cleanVerdicts = verdicts.map((v, vi) => ({
        max_score: Number(v.max_score) || 0,
        text: v.text,
        button_text: v.button_text,
        button_action: v.button_action,
        order_idx: vi,
      }));
      await api.patch(`/quizzes/${id}`, {
        name,
        description: description || null,
        questions: cleanQuestions,
        verdicts: cleanVerdicts,
      });
      await mutate();
      setDirty(false);
      showToast('Квиз сохранён');
    } catch (e: any) {
      setErr(e?.message || 'Не удалось сохранить');
      showToast(e?.message || 'Не удалось сохранить', { type: 'error' });
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      await api.del(`/quizzes/${id}`);
      showToast('Квиз удалён');
      router.push('/quizzes');
    } catch (e: any) {
      showToast(e?.message || 'Не удалось удалить', { type: 'error' });
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  // ── Mutations: questions ──

  function addQuestion() {
    setQuestions((qs) => [
      ...qs,
      {
        text: '',
        prefix: `вопрос ${qs.length + 1}/${qs.length + 1}`,
        options: [
          { text: '✓ да', score: 0 },
          { text: '✗ нет', score: 1 },
        ],
      },
    ]);
    markDirty();
  }

  function updateQuestion(idx: number, patch: Partial<QuizQuestion>) {
    setQuestions((qs) => qs.map((q, i) => (i === idx ? { ...q, ...patch } : q)));
    markDirty();
  }

  function removeQuestion(idx: number) {
    setQuestions((qs) => qs.filter((_, i) => i !== idx));
    markDirty();
  }

  function moveQuestion(idx: number, dir: -1 | 1) {
    setQuestions((qs) => {
      const j = idx + dir;
      if (j < 0 || j >= qs.length) return qs;
      const next = qs.slice();
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
    markDirty();
  }

  function addOption(qIdx: number) {
    setQuestions((qs) =>
      qs.map((q, i) =>
        i === qIdx ? { ...q, options: [...q.options, { text: '', score: 0 }] } : q,
      ),
    );
    markDirty();
  }

  function updateOption(qIdx: number, oIdx: number, patch: Partial<QuizOption>) {
    setQuestions((qs) =>
      qs.map((q, i) =>
        i === qIdx
          ? { ...q, options: q.options.map((o, j) => (j === oIdx ? { ...o, ...patch } : o)) }
          : q,
      ),
    );
    markDirty();
  }

  function removeOption(qIdx: number, oIdx: number) {
    setQuestions((qs) =>
      qs.map((q, i) =>
        i === qIdx ? { ...q, options: q.options.filter((_, j) => j !== oIdx) } : q,
      ),
    );
    markDirty();
  }

  // ── Mutations: verdicts ──

  function addVerdict() {
    setVerdicts((vs) => [
      ...vs,
      {
        max_score: vs.length === 0 ? 1 : (vs[vs.length - 1].max_score || 0) + 2,
        text: '',
        button_text: null,
        button_action: null,
      },
    ]);
    markDirty();
  }

  function updateVerdict(idx: number, patch: Partial<QuizVerdict>) {
    setVerdicts((vs) => vs.map((v, i) => (i === idx ? { ...v, ...patch } : v)));
    markDirty();
  }

  function removeVerdict(idx: number) {
    setVerdicts((vs) => vs.filter((_, i) => i !== idx));
    markDirty();
  }

  function moveVerdict(idx: number, dir: -1 | 1) {
    setVerdicts((vs) => {
      const j = idx + dir;
      if (j < 0 || j >= vs.length) return vs;
      const next = vs.slice();
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
    markDirty();
  }

  if (isLoading || !data) {
    return <QuizEditorSkeleton />;
  }

  const maxScore = questions.reduce(
    (sum, q) => sum + Math.max(0, ...q.options.map((o) => Number(o.score) || 0)),
    0,
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={name || 'Без названия'}
        subtitle={`Максимально возможный score: ${maxScore} · вопросов: ${questions.length} · вердиктов: ${verdicts.length}`}
        action={
          <div className="flex gap-2">
            <Link href="/quizzes" className="text-sm text-zinc-500 hover:text-ink self-center">
              ← К списку
            </Link>
            <Button variant="danger" onClick={() => setConfirmDelete(true)} disabled={saving}>
              Удалить
            </Button>
            <Button onClick={save} disabled={saving || !dirty}>
              {saving ? 'Сохраняем…' : dirty ? 'Сохранить' : 'Сохранено'}
            </Button>
          </div>
        }
      />

      {err && (
        <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
          {err}
        </div>
      )}

      {/* Meta */}
      <Card padded className="space-y-4">
        <Field label="Название" required>
          <Input
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              markDirty();
            }}
            placeholder="готов ли твой MVP"
          />
        </Field>
        <Field label="Описание" hint="Видно только в админке">
          <Textarea
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              markDirty();
            }}
            rows={2}
          />
        </Field>
      </Card>

      {/* Questions */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Вопросы</h2>
          <Button size="sm" variant="ghost" onClick={addQuestion}>
            + Вопрос
          </Button>
        </div>
        {questions.length === 0 ? (
          <Card padded>
            <Empty>Добавь первый вопрос — без вопросов квиз бесполезен.</Empty>
          </Card>
        ) : (
          questions.map((q, qi) => (
            <Card key={qi} padded className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <Pill color="indigo">Вопрос {qi + 1}</Pill>
                <div className="flex gap-1">
                  <IconButton onClick={() => moveQuestion(qi, -1)} disabled={qi === 0} title="Выше">
                    ↑
                  </IconButton>
                  <IconButton
                    onClick={() => moveQuestion(qi, 1)}
                    disabled={qi === questions.length - 1}
                    title="Ниже"
                  >
                    ↓
                  </IconButton>
                  <IconButton onClick={() => removeQuestion(qi)} title="Удалить" className="hover:text-rose-600">
                    ✕
                  </IconButton>
                </div>
              </div>
              <Field label="Префикс (над вопросом)" hint="Опционально. Например, «вопрос 1/5»">
                <Input
                  value={q.prefix || ''}
                  onChange={(e) => updateQuestion(qi, { prefix: e.target.value || null })}
                />
              </Field>
              <Field label="Текст вопроса" required>
                <Textarea
                  value={q.text}
                  onChange={(e) => updateQuestion(qi, { text: e.target.value })}
                  rows={3}
                />
              </Field>
              <div>
                <div className="text-xs uppercase tracking-wide text-zinc-500 mb-1.5 flex items-center justify-between">
                  <span>Варианты ответа</span>
                  <button
                    type="button"
                    onClick={() => addOption(qi)}
                    className="text-indigo-600 hover:underline normal-case tracking-normal text-sm"
                  >
                    + опция
                  </button>
                </div>
                {q.options.length === 0 ? (
                  <div className="text-xs text-zinc-400 italic">Нет вариантов</div>
                ) : (
                  <div className="space-y-2">
                    {q.options.map((o, oi) => (
                      <div key={oi} className="flex gap-2 items-center">
                        <Input
                          value={o.text}
                          onChange={(e) => updateOption(qi, oi, { text: e.target.value })}
                          placeholder="✓ да"
                          className="flex-1"
                        />
                        <div className="w-24">
                          <Input
                            type="number"
                            value={o.score}
                            onChange={(e) =>
                              updateOption(qi, oi, { score: Number(e.target.value) || 0 })
                            }
                            placeholder="score"
                            title="Вклад в score юзера"
                          />
                        </div>
                        <IconButton
                          onClick={() => removeOption(qi, oi)}
                          className="hover:text-rose-600 shrink-0"
                          title="Удалить вариант"
                        >
                          ✕
                        </IconButton>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          ))
        )}
      </section>

      {/* Verdicts */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Вердикты</h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              По итоговому score юзеру показывается первый подходящий вердикт.
              Условие: <code>score ≤ max_score</code>. Отсортируй по возрастанию max_score.
            </p>
          </div>
          <Button size="sm" variant="ghost" onClick={addVerdict}>
            + Вердикт
          </Button>
        </div>
        {verdicts.length === 0 ? (
          <Card padded>
            <Empty>Без вердиктов квиз просто покажет «Тест завершён. Балл: X».</Empty>
          </Card>
        ) : (
          verdicts.map((v, vi) => (
            <Card key={vi} padded className="space-y-3">
              <div className="flex items-start justify-between gap-2">
                <Pill color="violet">
                  Вердикт {vi + 1} · score ≤ {v.max_score}
                </Pill>
                <div className="flex gap-1">
                  <IconButton onClick={() => moveVerdict(vi, -1)} disabled={vi === 0}>
                    ↑
                  </IconButton>
                  <IconButton
                    onClick={() => moveVerdict(vi, 1)}
                    disabled={vi === verdicts.length - 1}
                  >
                    ↓
                  </IconButton>
                  <IconButton onClick={() => removeVerdict(vi)} className="hover:text-rose-600">
                    ✕
                  </IconButton>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Field label="Max score (включительно)" hint="Срабатывает если score ≤ этого">
                  <Input
                    type="number"
                    value={v.max_score}
                    onChange={(e) =>
                      updateVerdict(vi, { max_score: Number(e.target.value) || 0 })
                    }
                  />
                </Field>
                <Field label="Текст кнопки" hint="Опционально">
                  <Input
                    value={v.button_text || ''}
                    onChange={(e) =>
                      updateVerdict(vi, { button_text: e.target.value || null })
                    }
                    placeholder="оставить заявку →"
                  />
                </Field>
                <Field
                  label="Действие кнопки"
                  hint="URL (https://…) или callback (form:start:6)"
                >
                  <Input
                    value={v.button_action || ''}
                    onChange={(e) =>
                      updateVerdict(vi, { button_action: e.target.value || null })
                    }
                    placeholder="form:start:6"
                  />
                </Field>
              </div>
              <Field label="Текст вердикта" required>
                <Textarea
                  value={v.text}
                  onChange={(e) => updateVerdict(vi, { text: e.target.value })}
                  rows={4}
                />
              </Field>
            </Card>
          ))
        )}
      </section>

      {dirty && (
        <div className="sticky bottom-3 z-20 flex justify-center">
          <div className="glass-strong rounded-2xl px-4 py-2 shadow-lg flex items-center gap-3">
            <span className="text-sm text-zinc-600">есть несохранённые изменения</span>
            <Button size="sm" onClick={save} disabled={saving}>
              {saving ? 'Сохраняем…' : 'Сохранить'}
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={remove}
        busy={deleting}
        title="Удалить квиз?"
        description={
          <>
            История прохождений (ответы пользователей и финальный score)
            <b> сохранится</b> — мы храним снапшоты. Но новые попытки запустить квиз
            будет нельзя, и все шаги воронок, привязанные к этому квизу, перестанут работать.
          </>
        }
        confirmText="Да, удалить"
      />
    </div>
  );
}


function QuizEditorSkeleton() {
  return (
    <div className="space-y-5 anim-fade">
      {/* PageHeader skeleton */}
      <div className="flex items-end justify-between gap-3">
        <div className="space-y-2">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-3 w-80" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-20" />
          <Skeleton className="h-10 w-24" />
        </div>
      </div>

      {/* Meta card */}
      <Card padded className="space-y-3">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-3 w-24 mt-2" />
        <Skeleton className="h-16 w-full" />
      </Card>

      {/* Questions section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-8 w-24" />
        </div>
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} padded className="space-y-2">
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-16 w-full" />
            <div className="flex gap-2">
              <Skeleton className="h-9 flex-1" />
              <Skeleton className="h-9 w-24" />
            </div>
          </Card>
        ))}
      </div>

      {/* Verdicts section */}
      <div className="space-y-3">
        <Skeleton className="h-5 w-24" />
        {Array.from({ length: 1 }).map((_, i) => (
          <Card key={i} padded className="space-y-3">
            <Skeleton className="h-5 w-32" />
            <div className="grid grid-cols-3 gap-3">
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
            </div>
            <Skeleton className="h-24 w-full" />
          </Card>
        ))}
      </div>
    </div>
  );
}

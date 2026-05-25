'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import {
  Button, Card, Empty, Field, Input, PageHeader, Pill, Sheet,
  TableHead, TableWrap, Td, Textarea, Th, Tr,
} from '@/components/ui';

type QuizBrief = {
  id: number;
  name: string;
  description: string | null;
  questions_count: number;
  verdicts_count: number;
  attempts_total: number;
  attempts_completed: number;
  created_at: string;
};

export default function QuizzesPage() {
  const router = useRouter();
  const { data, mutate, isLoading } = useSWR<QuizBrief[]>('/quizzes', fetcher);

  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    if (!name.trim()) {
      setErr('Введите название');
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const created = await api.post<{ id: number }>('/quizzes', {
        name: name.trim(),
        description: description.trim() || null,
        questions: [],
        verdicts: [],
      });
      setOpen(false);
      setName('');
      setDescription('');
      mutate();
      router.push(`/quizzes/${created.id}`);
    } catch (e: any) {
      setErr(e?.message || 'Ошибка');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Квизы"
        subtitle="Интерактивные мини-опросы. Подсчитывают score и показывают вердикт. Подключаются к шагу воронки или к кнопке."
        action={<Button onClick={() => setOpen(true)}>+ Новый квиз</Button>}
      />

      <Card>
        {isLoading ? (
          <Empty>Загрузка…</Empty>
        ) : !data || data.length === 0 ? (
          <Empty>Пока нет квизов. Создайте первый — например, «готов ли твой MVP».</Empty>
        ) : (
          <TableWrap>
            <table className="w-full text-sm">
              <TableHead>
                <Th>Название</Th>
                <Th className="text-right">Вопросов</Th>
                <Th className="text-right">Вердиктов</Th>
                <Th className="text-right">Прохождений</Th>
                <Th className="text-right">Завершено</Th>
                <Th className="text-right">% завершения</Th>
              </TableHead>
              <tbody>
                {data.map((q) => {
                  const pct =
                    q.attempts_total > 0
                      ? Math.round((q.attempts_completed / q.attempts_total) * 100)
                      : null;
                  return (
                    <Tr key={q.id} className="cursor-pointer" onClick={() => router.push(`/quizzes/${q.id}`)}>
                      <Td>
                        <div className="font-medium text-ink">{q.name}</div>
                        {q.description && (
                          <div className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{q.description}</div>
                        )}
                      </Td>
                      <Td className="text-right tabular-nums">{q.questions_count}</Td>
                      <Td className="text-right tabular-nums">{q.verdicts_count}</Td>
                      <Td className="text-right tabular-nums">{q.attempts_total}</Td>
                      <Td className="text-right tabular-nums">{q.attempts_completed}</Td>
                      <Td className="text-right">
                        {pct == null ? (
                          <span className="text-zinc-400">—</span>
                        ) : (
                          <Pill color={pct >= 70 ? 'green' : pct >= 40 ? 'amber' : 'red'}>{pct}%</Pill>
                        )}
                      </Td>
                    </Tr>
                  );
                })}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>

      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title="Новый квиз"
        description="Создадим пустой квиз — наполнить вопросами можно сразу после."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>
              Отмена
            </Button>
            <Button onClick={create} disabled={busy}>
              {busy ? 'Создаём…' : 'Создать и открыть'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Название" required>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="готов ли твой MVP"
              autoFocus
            />
          </Field>
          <Field label="Описание" hint="Видно только в админке">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="5 вопросов да/нет, считаем минусы, даём один из 3 вердиктов"
            />
          </Field>
          {err && (
            <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
              {err}
            </div>
          )}
        </div>
      </Sheet>
    </div>
  );
}

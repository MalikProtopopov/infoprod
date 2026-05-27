'use client';

import Link from 'next/link';
import useSWR from 'swr';

import { fetcher } from '@/lib/api';
import { Select } from '@/components/ui';

export /** Селектор существующего квиза/формы + кнопка «создать новый». */
function QuizFormPicker({
  kind, value, onChange,
}: {
  kind: 'quiz' | 'form';
  value: number | null;
  onChange: (id: number | null) => void;
}) {
  const endpoint = kind === 'quiz' ? '/quizzes' : '/forms';
  const detailHref = kind === 'quiz' ? '/quizzes/' : '/forms/';
  const { data } = useSWR<{ id: number; name: string }[]>(endpoint, fetcher);
  return (
    <div className="flex gap-2 items-center">
      <Select
        className="flex-1"
        value={value == null ? '' : String(value)}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
      >
        <option value="">— не привязан —</option>
        {(data || []).map((q) => (
          <option key={q.id} value={q.id}>{q.name}</option>
        ))}
      </Select>
      {value != null && (
        <Link
          href={`${detailHref}${value}`}
          className="text-sm text-indigo-600 hover:underline shrink-0"
        >
          Открыть →
        </Link>
      )}
      <Link
        href={endpoint}
        className="text-sm text-zinc-500 hover:text-ink shrink-0"
        title={kind === 'quiz' ? 'Список квизов' : 'Список форм'}
      >
        + Создать
      </Link>
    </div>
  );
}

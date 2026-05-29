'use client';

import { use, useEffect, useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { useFeatures } from '@/lib/features';
import { useToast } from '@/components/Toast';
import { Button, Card, Empty, Field, Input, PageHeader, Pill, Select, Skeleton, Textarea } from '@/components/ui';

type UserBotRow = { bot_id: number; username: string | null; is_blocked: boolean; last_seen_at: string };

type UserCard = {
  user: {
    id: number;
    telegram_user_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
    phone: string | null;
    email: string | null;
    notes: string | null;
    first_seen_at: string;
    last_seen_at: string;
  };
  bots: UserBotRow[];
  leads: Array<{
    id: number;
    product_name: string;
    channel_title: string | null;
    status: string;
    created_at: string;
  }>;
  payments: Array<{
    id: number;
    product_name: string;
    channel_title: string | null;
    period_months: number;
    amount: string;
    currency: string;
    created_at: string;
  }>;
  subscriptions: Array<{
    id: number;
    channel_id: number;
    channel_title: string | null;
    product_id: number | null;
    product_name: string | null;
    starts_at: string;
    ends_at: string;
    status: string;
    invite_link: string | null;
  }>;
};

export default function UserPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { isOn } = useFeatures();
  const { data, mutate } = useSWR<UserCard>(`/users/${id}`, fetcher);
  const [form, setForm] = useState({ phone: '', email: '', notes: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    if (data) setForm({ phone: data.user.phone ?? '', email: data.user.email ?? '', notes: data.user.notes ?? '' });
  }, [data]);

  if (!data) return <div className="text-sm text-zinc-500">Загрузка…</div>;
  const u = data.user;
  const fullName = [u.first_name, u.last_name].filter(Boolean).join(' ') || `Пользователь #${u.id}`;

  async function save() {
    setBusy(true); setError(null); setOk(false);
    try {
      await api.patch(`/users/${id}`, {
        phone: form.phone || null,
        email: form.email || null,
        notes: form.notes || null,
      });
      await mutate(); setOk(true);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={fullName}
        subtitle={u.username ? '@' + u.username : `Telegram ID ${u.telegram_user_id}`}
        action={
          u.username && (
            <a href={`https://t.me/${u.username}`} target="_blank" rel="noreferrer">
              <Button variant="glass">Написать в Telegram ↗</Button>
            </a>
          )
        }
      />

      <ChatPanel userId={Number(id)} bots={data.bots ?? []} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card padded className="anim-rise">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-indigo-500" /> Из Telegram
          </h3>
          <dl className="text-sm space-y-1.5">
            <Row label="TG ID" mono>{u.telegram_user_id}</Row>
            <Row label="Username">{u.username ? '@' + u.username : '—'}</Row>
            <Row label="Имя">{u.first_name || '—'}</Row>
            <Row label="Фамилия">{u.last_name || '—'}</Row>
            <Row label="Первый визит">{new Date(u.first_seen_at).toLocaleString('ru-RU')}</Row>
            <Row label="Последний визит">{new Date(u.last_seen_at).toLocaleString('ru-RU')}</Row>
          </dl>
        </Card>

        <Card padded className="anim-rise">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-violet-500" /> Данные администратора
          </h3>
          <div className="space-y-3">
            <Field label="Телефон">
              <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="Email">
              <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </Field>
            <Field label="Заметки">
              <Textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </Field>
            {error && <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>}
            {ok && <div className="text-sm text-emerald-700">Сохранено</div>}
            <Button onClick={save} disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</Button>
          </div>
        </Card>
      </div>

      {isOn('monetization') && (
      <Card padded className="anim-rise">
        <h3 className="font-semibold mb-4">Подписки</h3>
        {(data.subscriptions ?? []).length === 0 ? <Empty>Подписок нет</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[680px]">
              <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2 pr-3">Канал</th>
                  <th className="py-2 pr-3">Продукт</th>
                  <th className="py-2 pr-3">Статус</th>
                  <th className="py-2 pr-3">Начало</th>
                  <th className="py-2 pr-3">Окончание</th>
                  <th className="py-2">Ссылка</th>
                </tr>
              </thead>
              <tbody>
                {data.subscriptions.map((s) => (
                  <tr key={s.id} className="border-t border-zinc-100/80">
                    <td className="py-2.5 pr-3">{s.channel_title || '—'}</td>
                    <td className="py-2.5 pr-3 text-zinc-600">{s.product_name || '—'}</td>
                    <td className="py-2.5 pr-3"><SubStatus s={s.status} /></td>
                    <td className="py-2.5 pr-3">{new Date(s.starts_at).toLocaleDateString('ru-RU')}</td>
                    <td className="py-2.5 pr-3">{new Date(s.ends_at).toLocaleDateString('ru-RU')}</td>
                    <td className="py-2.5 truncate max-w-[200px]">
                      {s.invite_link ? <a className="text-indigo-600 hover:underline" href={s.invite_link} target="_blank" rel="noreferrer">link ↗</a> : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      )}

      {isOn('monetization') && (
      <Card padded className="anim-rise">
        <h3 className="font-semibold mb-4">Платежи</h3>
        {(data.payments ?? []).length === 0 ? <Empty>Платежей нет</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[680px]">
              <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2 pr-3">Дата</th>
                  <th className="py-2 pr-3">Канал</th>
                  <th className="py-2 pr-3">Продукт</th>
                  <th className="py-2 pr-3">Период</th>
                  <th className="py-2">Сумма</th>
                </tr>
              </thead>
              <tbody>
                {data.payments.map((p) => (
                  <tr key={p.id} className="border-t border-zinc-100/80">
                    <td className="py-2.5 pr-3">{new Date(p.created_at).toLocaleString('ru-RU')}</td>
                    <td className="py-2.5 pr-3 text-zinc-600">{p.channel_title || '—'}</td>
                    <td className="py-2.5 pr-3">{p.product_name}</td>
                    <td className="py-2.5 pr-3">{p.period_months} мес.</td>
                    <td className="py-2.5 font-medium">{p.amount} {p.currency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      )}

      {isOn('leads') && (
      <Card padded className="anim-rise">
        <h3 className="font-semibold mb-4">Заявки</h3>
        {(data.leads ?? []).length === 0 ? <Empty>Заявок нет</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2 pr-3">Дата</th>
                  <th className="py-2 pr-3">Канал</th>
                  <th className="py-2 pr-3">Продукт</th>
                  <th className="py-2">Статус</th>
                </tr>
              </thead>
              <tbody>
                {data.leads.map((l) => (
                  <tr key={l.id} className="border-t border-zinc-100/80">
                    <td className="py-2.5 pr-3">{new Date(l.created_at).toLocaleString('ru-RU')}</td>
                    <td className="py-2.5 pr-3 text-zinc-600">{l.channel_title || '—'}</td>
                    <td className="py-2.5 pr-3">{l.product_name}</td>
                    <td className="py-2.5"><LeadStatus s={l.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      )}

      {(isOn('quizzes') || isOn('forms')) && <SubmissionsTimeline userId={Number(id)} />}
    </div>
  );
}


type ChatMessage = {
  id: number;
  bot_id: number;
  direction: 'in' | 'out';
  text: string | null;
  created_at: string;
  by_admin: boolean;
};

function ChatPanel({ userId, bots }: { userId: number; bots: UserBotRow[] }) {
  const { showToast } = useToast();
  const [botId, setBotId] = useState<number | null>(
    bots.find((b) => !b.is_blocked)?.bot_id ?? bots[0]?.bot_id ?? null,
  );
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const key = botId != null ? `/users/${userId}/messages?bot_id=${botId}` : null;
  const { data, mutate } = useSWR<{ items: ChatMessage[] }>(key, fetcher);
  const selectedBot = bots.find((b) => b.bot_id === botId) || null;

  if (bots.length === 0) {
    return (
      <Card padded className="anim-rise">
        <h3 className="font-semibold mb-2">Чат</h3>
        <Empty>Пользователь ещё не контактировал ни с одним ботом — писать некуда.</Empty>
      </Card>
    );
  }

  async function send() {
    if (!text.trim() || botId == null) return;
    setBusy(true);
    try {
      await api.post(`/users/${userId}/message`, { bot_id: botId, text: text.trim() });
      setText('');
      await mutate();
      showToast('Сообщение отправлено');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Не удалось отправить', { type: 'error', durationMs: 5000 });
      await mutate(); // блокировка могла обновиться
    } finally {
      setBusy(false);
    }
  }

  const items = data?.items ?? [];

  return (
    <Card padded className="anim-rise space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="font-semibold">Чат с пользователем</h3>
        <div className="w-56">
          <Select value={botId ?? ''} onChange={(e) => setBotId(Number(e.target.value))}>
            {bots.map((b) => (
              <option key={b.bot_id} value={b.bot_id}>
                {(b.username ? '@' + b.username : `бот #${b.bot_id}`) + (b.is_blocked ? ' 🚫' : '')}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {selectedBot?.is_blocked && (
        <div className="text-xs text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">
          🚫 Пользователь заблокировал этого бота — сообщения не дойдут. Попробуйте другого бота, если есть.
        </div>
      )}

      <div className="rounded-xl bg-zinc-50/70 border border-zinc-200/60 p-3 max-h-[360px] overflow-y-auto space-y-2">
        {items.length === 0 ? (
          <div className="text-sm text-zinc-400 text-center py-6">Сообщений пока нет</div>
        ) : (
          items.map((m) => (
            <div key={m.id} className={'flex ' + (m.direction === 'out' ? 'justify-end' : 'justify-start')}>
              <div
                className={
                  'max-w-[75%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap break-words ' +
                  (m.direction === 'out'
                    ? 'bg-indigo-600 text-white rounded-br-sm'
                    : 'bg-white border border-zinc-200 text-ink rounded-bl-sm')
                }
              >
                {m.direction === 'out'
                  ? <div dangerouslySetInnerHTML={{ __html: m.text || '' }} />
                  : <div>{m.text}</div>}
                <div className={'mt-1 text-[10px] ' + (m.direction === 'out' ? 'text-indigo-200' : 'text-zinc-400')}>
                  {m.direction === 'out' ? (m.by_admin ? 'вы · ' : 'бот · ') : ''}
                  {new Date(m.created_at).toLocaleString('ru-RU')}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="flex gap-2 items-end">
        <Textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Сообщение пользователю (HTML: b/i/u, ссылки)…"
          className="flex-1"
        />
        <Button onClick={send} disabled={busy || !text.trim()}>
          {busy ? '…' : 'Отправить'}
        </Button>
      </div>
    </Card>
  );
}


type SubmissionItem = {
  id: number;
  mode: 'quiz' | 'form';
  status: 'in_progress' | 'completed' | 'cancelled';
  started_at: string;
  completed_at: string | null;
  score: number | null;
  current_idx: number;
  answers: Record<string, any> | null;
  funnel: { id: number; name: string } | null;
  funnel_entry_id: number | null;
  step_id: number | null;
  quiz?: { id: number; name: string };
  form?: { id: number; name: string };
  lead_id?: number;
};

function SubmissionsTimeline({ userId }: { userId: number }) {
  const { data } = useSWR<{ total: number; items: SubmissionItem[] }>(
    `/users/${userId}/submissions`,
    fetcher,
  );

  return (
    <Card padded className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight">История ответов</h2>
      <p className="text-xs text-zinc-500 -mt-1">
        Все квизы и формы, которые юзер прошёл или начал. Ответы хранятся в снапшоте
        на момент прохождения — даже если содержание квиза/формы потом поменяли.
      </p>
      {!data ? (
        <div className="space-y-2.5">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="rounded-xl bg-white/70 border border-zinc-200/70 p-3.5 space-y-2">
              <div className="flex gap-2">
                <Skeleton className="h-5 w-16 rounded-full" />
                <Skeleton className="h-5 w-24 rounded-full" />
              </div>
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <Empty>Пользователь пока не отвечал ни на один квиз / форму.</Empty>
      ) : (
        <div className="space-y-2.5">
          {data.items.map((it) => (
            <SubmissionCard key={it.id} item={it} />
          ))}
        </div>
      )}
    </Card>
  );
}


function SubmissionCard({ item }: { item: SubmissionItem }) {
  const [expanded, setExpanded] = useState(false);
  const startedTs = new Date(item.started_at).toLocaleString('ru-RU');
  const completedTs = item.completed_at ? new Date(item.completed_at).toLocaleString('ru-RU') : null;
  const isCompleted = item.status === 'completed';
  const isCancelled = item.status === 'cancelled';
  const isInProgress = item.status === 'in_progress';

  const statusPill = isCompleted ? (
    <Pill color="green">✓ завершено</Pill>
  ) : isCancelled ? (
    <Pill color="amber">✗ прерван</Pill>
  ) : (
    <Pill color="sky">в процессе</Pill>
  );

  const modeBadge = item.mode === 'quiz' ? (
    <Pill color="indigo">🧠 квиз</Pill>
  ) : (
    <Pill color="violet">📋 форма</Pill>
  );

  const title = item.mode === 'quiz' ? item.quiz?.name : item.form?.name;
  const quizItems = item.mode === 'quiz' ? (item.answers?.items as any[] | undefined) || [] : [];
  const formSnapshots = item.mode === 'form' ? (item.answers?.__snapshots as any[] | undefined) || [] : [];

  return (
    <div className="rounded-xl bg-white/70 border border-zinc-200/70 p-3.5">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        {modeBadge}
        {statusPill}
        {item.mode === 'quiz' && item.score != null && (
          <Pill color="rose">score: {item.score}</Pill>
        )}
        {item.lead_id && (
          <Pill color="green">Lead #{item.lead_id}</Pill>
        )}
        {item.funnel && (
          <span className="text-xs text-zinc-500">
            в воронке «{item.funnel.name}»
          </span>
        )}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="ml-auto text-xs text-indigo-600 hover:underline"
        >
          {expanded ? 'свернуть' : 'все ответы'}
        </button>
      </div>
      <div className="text-sm font-medium text-ink">{title || '(без названия)'}</div>
      <div className="text-xs text-zinc-500 mt-0.5">
        начато: {startedTs}
        {completedTs && ` · завершено: ${completedTs}`}
        {isInProgress && ` · поле/вопрос: ${item.current_idx + 1}`}
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-zinc-100">
          {item.mode === 'quiz' && quizItems.length > 0 && (
            <ol className="space-y-2 text-sm">
              {quizItems.map((qi, i) => (
                <li key={i} className="flex flex-col gap-0.5">
                  <span className="text-zinc-700">
                    <span className="text-zinc-400">Q{i + 1}.</span> {qi.q}
                  </span>
                  <span className="text-zinc-900 ml-5">
                    → {qi.option}{' '}
                    {qi.score != null && (
                      <span className="text-xs text-zinc-400">(+{qi.score})</span>
                    )}
                  </span>
                </li>
              ))}
            </ol>
          )}
          {item.mode === 'form' && formSnapshots.length > 0 && (
            <dl className="space-y-2 text-sm">
              {formSnapshots.map((fs, i) => (
                <div key={i}>
                  <dt className="text-zinc-500 text-xs uppercase tracking-wide">{fs.question}</dt>
                  <dd className="text-zinc-900 break-words">{fs.answer || <span className="text-zinc-400">—</span>}</dd>
                </div>
              ))}
            </dl>
          )}
          {((item.mode === 'quiz' && quizItems.length === 0) ||
            (item.mode === 'form' && formSnapshots.length === 0)) && (
            <p className="text-xs text-zinc-500 italic">Юзер ничего не успел ответить.</p>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, children, mono }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3 border-b border-zinc-100/80 py-1.5">
      <dt className="text-zinc-500 text-xs uppercase tracking-wide">{label}</dt>
      <dd className={`text-zinc-900 text-right ${mono ? 'font-mono text-xs' : ''}`}>{children}</dd>
    </div>
  );
}

function SubStatus({ s }: { s: string }) {
  if (s === 'active') return <Pill color="green">активна</Pill>;
  if (s === 'expired') return <Pill color="amber">истекла</Pill>;
  if (s === 'revoked') return <Pill color="red">отозвана</Pill>;
  return <Pill color="gray">{s}</Pill>;
}

function LeadStatus({ s }: { s: string }) {
  if (s === 'new') return <Pill color="amber">новая</Pill>;
  if (s === 'contacted') return <Pill color="gray">связались</Pill>;
  if (s === 'paid') return <Pill color="green">оплачена</Pill>;
  if (s === 'closed') return <Pill color="green">завершена</Pill>;
  if (s === 'cancelled') return <Pill color="red">отменена</Pill>;
  return <Pill color="gray">{s}</Pill>;
}

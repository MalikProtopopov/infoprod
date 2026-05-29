'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import useSWR from 'swr';
import clsx from 'clsx';
import {
  Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

import { fetcher } from '@/lib/api';
import {
  Card, Empty, PageHeader, Pill, Select,
  TableHead, TableWrap, Td, Th, Tr,
} from '@/components/ui';

/* ---------- Types ---------- */

type HealthResp = {
  summary: {
    leads_30d: number;
    leads_attributed_30d: number;
    attribution_pct: number;
    tracking_links_total: number;
    tracking_links_active: number;
    payments_30d: number;
    revenue_30d: string;
    funnels_total: number;
    funnels_active: number;
    scheduled_messages_total: number;
    scheduled_messages_sent: number;
    scheduled_messages_failed: number;
    test_entries: number;
    test_users: number;
    users_total: number;
    users_notifications_off: number;
    users_notifications_off_pct: number;
  };
  warnings: Array<{
    key: string;
    severity: 'info' | 'warning' | 'error';
    title: string;
    message: string;
    action: { label: string; href: string } | null;
  }>;
};

type TimelineResp = {
  from: string;
  to: string;
  granularity: string;
  dimension: string;
  attribution: string;
  dims: string[];
  buckets: string[];
  points: Array<{ date: string; dim: string; leads: number; payments: number; revenue: string }>;
  totals: { leads: number; payments: number; revenue: string };
};

type FunnelsSummaryResp = {
  rows: Array<{
    funnel_id: number;
    name: string;
    product_id: number;
    is_active: boolean;
    entered: number;
    successful_outcomes: number;
    completed: number;
    cancelled_by_payment: number;
    cancelled_other: number;
    payments: number;
    revenue: string;
    cvr: number;
  }>;
};

type Product = { id: number; name: string };

/* ---------- Period / dimension / attribution ---------- */

type Period = '7d' | '30d' | '90d';
const PERIODS: Array<{ key: Period; label: string; days: number }> = [
  { key: '7d',  label: '7 дней',  days: 7 },
  { key: '30d', label: '30 дней', days: 30 },
  { key: '90d', label: '90 дней', days: 90 },
];

type Granularity = 'day' | 'week' | 'month';
type Dimension = 'source' | 'campaign' | 'product' | 'none';
type Attribution = 'last' | 'first';
type Metric = 'leads' | 'payments' | 'revenue';

function periodRange(p: Period): { from: string; to: string } {
  const now = new Date();
  const to = now.toISOString();
  const from = new Date(now);
  from.setDate(from.getDate() - PERIODS.find((x) => x.key === p)!.days);
  return { from: from.toISOString(), to };
}

/* ---------- Page ---------- */

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<Period>('30d');
  const [productId, setProductId] = useState<number | ''>('');
  const [dimension, setDimension] = useState<Dimension>('source');
  const [attribution, setAttribution] = useState<Attribution>('last');
  const [metric, setMetric] = useState<Metric>('leads');
  const [granularity, setGranularity] = useState<Granularity>('day');
  const [botId, setBotId] = useState<number | ''>('');

  const { data: products } = useSWR<Product[]>('/products', fetcher);
  const { data: bots } = useSWR<{ id: number; username: string | null }[]>('/bots', fetcher);
  const { data: health } = useSWR<HealthResp>('/stats/health', fetcher, {
    refreshInterval: 120_000,
    revalidateOnFocus: false,
  });

  const timelineKey = useMemo(() => {
    const { from, to } = periodRange(period);
    const params = new URLSearchParams({
      from, to, granularity, dimension, attribution,
    });
    if (productId) params.set('product_id', String(productId));
    if (botId) params.set('bot_id', String(botId));
    return `/stats/timeline?${params}`;
  }, [period, granularity, dimension, attribution, productId, botId]);

  const { data: timeline, isLoading: timelineLoading } = useSWR<TimelineResp>(timelineKey, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });

  const funnelsSummaryKey = useMemo(() => {
    const { from, to } = periodRange(period);
    return `/stats/funnels/summary?from=${from}&to=${to}${botId ? `&bot_id=${botId}` : ''}`;
  }, [period, botId]);
  const { data: funnelsSummary } = useSWR<FunnelsSummaryResp>(funnelsSummaryKey, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });

  // --- Pareto: переколбасить points в строки по dim
  const pareto = useMemo(() => {
    if (!timeline) return [];
    const m = new Map<string, { dim: string; leads: number; payments: number; revenue: number }>();
    for (const p of timeline.points) {
      const r = m.get(p.dim) || { dim: p.dim, leads: 0, payments: 0, revenue: 0 };
      r.leads += p.leads;
      r.payments += p.payments;
      r.revenue += Number(p.revenue) || 0;
      m.set(p.dim, r);
    }
    return Array.from(m.values())
      .map((r) => ({ ...r, cvr: r.leads > 0 ? r.payments / r.leads : 0 }))
      .sort((a, b) => b.revenue - a.revenue);
  }, [timeline]);

  // --- Chart data: row per bucket, column per dim
  const chartData = useMemo(() => {
    if (!timeline) return [];
    const byBucket: Record<string, Record<string, number | string>> = {};
    for (const p of timeline.points) {
      const k = p.date.slice(0, 10);
      if (!byBucket[k]) byBucket[k] = { date: k };
      const val = metric === 'revenue' ? (Number(p.revenue) || 0) : (p[metric] as number);
      byBucket[k][p.dim] = ((byBucket[k][p.dim] as number) || 0) + val;
    }
    return Object.values(byBucket).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [timeline, metric]);

  return (
    <div>
      <PageHeader
        title="Эффективность"
        subtitle="Источники, воронки и кампании — что приводит платящих клиентов"
      />

      {/* --- Health-check block --- */}
      {health && health.warnings.length > 0 && (
        <Card className="mb-5">
          <div className="p-4 sm:p-5 space-y-3">
            <div className="text-xs uppercase tracking-widest text-zinc-500 font-medium">
              Состояние данных
            </div>
            {health.warnings.map((w) => (
              <WarningRow key={w.key} w={w} />
            ))}
          </div>
        </Card>
      )}

      {/* --- Filters --- */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5 flex-wrap">
        <div
          className="inline-flex glass rounded-2xl p-1.5"
          role="group"
          aria-label="Период"
        >
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              aria-pressed={period === p.key}
              className={clsx(
                'px-3 sm:px-4 h-9 rounded-xl text-sm transition',
                period === p.key ? 'bg-white shadow-soft text-ink' : 'text-zinc-600 hover:text-ink hover:bg-white/60',
              )}
            >
              {p.label}
            </button>
          ))}
        </div>

        <Select
          value={botId}
          onChange={(e) => setBotId(e.target.value ? Number(e.target.value) : '')}
          className="!w-auto"
          title="Фильтр статистики по боту (по боту первого касания)"
        >
          <option value="">Все боты</option>
          {(bots || []).map((b) => (
            <option key={b.id} value={b.id}>{b.username ? '@' + b.username : `бот #${b.id}`}</option>
          ))}
        </Select>

        <Select
          value={productId}
          onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}
          className="!w-auto"
        >
          <option value="">Все продукты</option>
          {(products || []).map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </Select>

        <Select value={dimension} onChange={(e) => setDimension(e.target.value as Dimension)} className="!w-auto">
          <option value="source">По источнику</option>
          <option value="campaign">По кампании</option>
          <option value="product">По продукту</option>
          <option value="none">Без разреза</option>
        </Select>

        <div
          className="inline-flex glass rounded-2xl p-1.5"
          role="group"
          aria-label="Модель атрибуции"
        >
          <button
            onClick={() => setAttribution('last')}
            aria-pressed={attribution === 'last'}
            className={clsx(
              'px-3 h-9 rounded-xl text-sm transition',
              attribution === 'last' ? 'bg-white shadow-soft text-ink' : 'text-zinc-600 hover:text-ink hover:bg-white/60',
            )}
            title="По последнему касанию: источник последней заявки юзера перед оплатой"
          >
            Последнее касание
          </button>
          <button
            onClick={() => setAttribution('first')}
            aria-pressed={attribution === 'first'}
            className={clsx(
              'px-3 h-9 rounded-xl text-sm transition',
              attribution === 'first' ? 'bg-white shadow-soft text-ink' : 'text-zinc-600 hover:text-ink hover:bg-white/60',
            )}
            title="По первому касанию: источник первого захода юзера в бота"
          >
            Первое касание
          </button>
        </div>

        <div
          className="ml-auto inline-flex glass rounded-2xl p-1.5"
          role="group"
          aria-label="Гранулярность"
        >
          {(['day', 'week', 'month'] as Granularity[]).map((g) => (
            <button
              key={g}
              onClick={() => setGranularity(g)}
              aria-pressed={granularity === g}
              className={clsx(
                'px-3 h-9 rounded-xl text-sm transition',
                granularity === g ? 'bg-white shadow-soft text-ink' : 'text-zinc-600 hover:text-ink hover:bg-white/60',
              )}
            >
              {g === 'day' ? 'День' : g === 'week' ? 'Неделя' : 'Месяц'}
            </button>
          ))}
        </div>
      </div>

      {/* --- Big numbers --- */}
      {timeline && (
        <div
          className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5"
          aria-live="polite"
          aria-label="Сводные показатели за выбранный период"
        >
          <BigNumber label="Лиды" value={timeline.totals.leads} />
          <BigNumber label="Оплаты" value={timeline.totals.payments} />
          <BigNumber label="Выручка" value={fmtMoney(timeline.totals.revenue) + ' ₽'} />
          <BigNumber
            label="Конверсия лид→оплата"
            value={timeline.totals.leads > 0
              ? `${((timeline.totals.payments / timeline.totals.leads) * 100).toFixed(1)}%`
              : '—'}
          />
        </div>
      )}

      {/* --- Stacked area chart --- */}
      <Card padded className="mb-5">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div>
            <div className="text-sm font-semibold text-ink">Динамика по дням</div>
            <div className="text-xs text-zinc-500">
              {{ leads: 'Сколько лидов', payments: 'Сколько оплат', revenue: 'Сколько выручки' }[metric]}
              {' '}приходило в каждый день
              {' · '}
              {dimension === 'none'
                ? 'без разреза'
                : `разрез по ${{ source: 'источникам', campaign: 'кампаниям', product: 'продуктам' }[dimension]}`}
            </div>
          </div>
          <div
            className="inline-flex glass rounded-2xl p-1"
            role="group"
            aria-label="Метрика"
          >
            {(['leads', 'payments', 'revenue'] as Metric[]).map((m) => (
              <button
                key={m}
                onClick={() => setMetric(m)}
                aria-pressed={metric === m}
                className={clsx(
                  'px-3 h-8 rounded-xl text-xs transition',
                  metric === m ? 'bg-white shadow-soft text-ink' : 'text-zinc-500 hover:text-ink hover:bg-white/60',
                )}
              >
                {m === 'leads' ? 'Лиды' : m === 'payments' ? 'Оплаты' : 'Выручка'}
              </button>
            ))}
          </div>
        </div>

        {timelineLoading ? (
          <div className="h-72 flex items-center justify-center text-sm text-zinc-500">Загрузка…</div>
        ) : !timeline || timeline.points.length === 0 ? (
          <Empty>
            Нет данных за период. Создайте tracking-ссылку и запустите трафик — данные появятся здесь.
          </Empty>
        ) : (
          <div
            className="h-72"
            role="img"
            aria-label={`График динамики по дням, метрика: ${
              { leads: 'лиды', payments: 'оплаты', revenue: 'выручка' }[metric]
            }, ${
              dimension === 'none'
                ? 'без разреза'
                : `разрез по ${{ source: 'источникам', campaign: 'кампаниям', product: 'продуктам' }[dimension]}`
            }`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#a1a1aa" />
                <YAxis tick={{ fontSize: 11 }} stroke="#a1a1aa" />
                <Tooltip
                  contentStyle={{ borderRadius: 12, fontSize: 12, border: '1px solid #e4e4e7' }}
                  labelStyle={{ fontWeight: 600 }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {timeline.dims.map((dim, i) => (
                  <Area
                    key={dim}
                    type="monotone"
                    dataKey={dim}
                    stackId="1"
                    stroke={CHART_COLORS[i % CHART_COLORS.length]}
                    fill={CHART_COLORS[i % CHART_COLORS.length]}
                    fillOpacity={0.6}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* --- Pareto table --- */}
      <Card className="mb-5">
        <div className="p-4 sm:p-5 pb-2 flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-ink">Топ-{dimension === 'source' ? 'источников' : dimension === 'campaign' ? 'кампаний' : dimension === 'product' ? 'продуктов' : 'строк'} за период</div>
            <div className="text-xs text-zinc-500">
              Сортировка по выручке. Конверсия = оплат / лидов в этой группе.
            </div>
          </div>
        </div>

        {pareto.length === 0 ? (
          <Empty>Нет данных для разреза</Empty>
        ) : (
          <TableWrap>
            <table className="w-full text-sm min-w-[640px]">
              <TableHead>
                <Th>{dimension === 'source' ? 'Источник' : dimension === 'campaign' ? 'Кампания' : dimension === 'product' ? 'Продукт' : '—'}</Th>
                <Th>Лидов</Th>
                <Th>Оплат</Th>
                <Th><span title="Доля лидов, оплативших продукт">Конверсия</span></Th>
                <Th>Выручка</Th>
              </TableHead>
              <tbody>
                {pareto.map((r) => (
                  <Tr key={r.dim}>
                    <Td className="font-medium">
                      {r.dim === 'organic' || r.dim === 'None' || !r.dim
                        ? <Pill color="gray">органика</Pill>
                        : r.dim}
                    </Td>
                    <Td>{r.leads.toLocaleString('ru-RU')}</Td>
                    <Td>{r.payments.toLocaleString('ru-RU')}</Td>
                    <Td className="text-zinc-600">{(r.cvr * 100).toFixed(1)}%</Td>
                    <Td className="font-semibold">{r.revenue.toLocaleString('ru-RU')} ₽</Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>

      {/* --- Funnels --- */}
      <Card>
        <div className="p-4 sm:p-5 pb-2">
          <div className="text-sm font-semibold text-ink">Эффективность воронок</div>
          <div className="text-xs text-zinc-500">
            Сколько пользователей вошло в воронку и сколько из них купили продукт.
            В «успех» засчитываются и те, кто прошёл воронку до конца, и те, кто оплатил во время её прохождения.
          </div>
        </div>

        {!funnelsSummary || funnelsSummary.rows.length === 0 ? (
          <Empty>Нет данных по воронкам за выбранный период</Empty>
        ) : (
          <div className="p-4 sm:p-5 pt-0 space-y-2">
            {funnelsSummary.rows.map((f) => (
              <Link
                key={f.funnel_id}
                href={`/funnels/${f.funnel_id}/edit`}
                className="glass-soft rounded-xl p-3 sm:p-4 hover:bg-white/80 transition flex items-center gap-4 flex-wrap"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="text-sm font-semibold text-ink truncate">{f.name}</div>
                    {!f.is_active && <Pill color="gray">черновик</Pill>}
                  </div>
                  <div className="text-xs text-zinc-500">
                    Вход <b className="text-ink">{f.entered}</b>
                    {' · '}успех <b className="text-ink">{f.successful_outcomes}</b>
                    {' '}<span className="text-zinc-400">({f.completed} завершили + {f.cancelled_by_payment} оплатили во время)</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-base font-bold tracking-tight text-ink">
                    {(f.cvr * 100).toFixed(1)}%
                  </div>
                  <div className="text-xs text-zinc-500">конверсия</div>
                </div>
                <div className="text-right">
                  <div className="text-base font-bold tracking-tight text-ink">
                    {fmtMoney(f.revenue)} ₽
                  </div>
                  <div className="text-xs text-zinc-500">{f.payments} оплат</div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>

      <div className="mt-5 text-xs text-zinc-500 max-w-3xl space-y-1">
        <div><b>Как читать:</b></div>
        <div>
          <b>Последнее касание</b> — атрибуция на источник последней заявки пользователя
          (учитывается клик за 30 минут до неё).
        </div>
        <div>
          <b>Первое касание</b> — атрибуция на источник первого захода пользователя в бота.
        </div>
        <div>
          <b>Оплачено во время воронки</b> — пользователь купил продукт, пока шла воронка;
          она автоматически остановилась, и это засчитывается как успех.
        </div>
        <div>Тестовые прогоны исключены из данных автоматически.</div>
      </div>
    </div>
  );
}

/* ---------- Helpers ---------- */

const CHART_COLORS = ['#7c3aed', '#06b6d4', '#f59e0b', '#10b981', '#ef4444', '#6366f1', '#ec4899', '#84cc16'];

function fmtMoney(s: string | number): string {
  const n = Number(s);
  if (!Number.isFinite(n)) return String(s);
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function BigNumber({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="glass rounded-2xl px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-zinc-500 font-medium">{label}</div>
      <div className="text-2xl font-bold tracking-tight text-ink mt-0.5">
        {typeof value === 'number' ? value.toLocaleString('ru-RU') : value}
      </div>
    </div>
  );
}

function WarningRow({ w }: { w: HealthResp['warnings'][number] }) {
  const colors = {
    info: 'bg-sky-50/70 border-sky-200/60 text-sky-900',
    warning: 'bg-amber-50/70 border-amber-200/60 text-amber-900',
    error: 'bg-rose-50/70 border-rose-200/60 text-rose-900',
  } as const;
  const dotColors = {
    info: 'bg-sky-500',
    warning: 'bg-amber-500',
    error: 'bg-rose-500',
  } as const;
  return (
    <div className={clsx('rounded-xl border px-4 py-3 flex items-start gap-3', colors[w.severity])}>
      <span className={clsx('mt-1.5 size-2 rounded-full shrink-0', dotColors[w.severity])} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold">{w.title}</div>
        <div className="text-xs mt-0.5 opacity-80">{w.message}</div>
      </div>
      {w.action && (
        <Link
          href={w.action.href}
          className="shrink-0 inline-flex items-center px-3 h-8 rounded-lg bg-white/80 hover:bg-white text-xs font-medium text-ink transition"
        >
          {w.action.label} →
        </Link>
      )}
    </div>
  );
}

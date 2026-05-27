'use client';

import Link from 'next/link';
import useSWR from 'swr';

import { fetcher } from '@/lib/api';
import { useFeatures } from '@/lib/features';
import { Card, Empty, PageHeader, Pill, Stat } from '@/components/ui';

type Overview = {
  users: { total: number; new_7d: number };
  leads: { total: number; new: number; last_24h: number };
  subscriptions: { active: number; expiring_7d: number };
  revenue: { total: string; last_30d: string; payments_30d: number };
  catalog: { products: number; channels: number; active_bots: number };
  recent_leads: Array<{
    id: number;
    status: string;
    created_at: string;
    user_id: number;
    user_first_name: string | null;
    user_username: string | null;
    product_name: string;
  }>;
  recent_payments: Array<{
    id: number;
    amount: string;
    currency: string;
    period_months: number;
    created_at: string;
    user_first_name: string | null;
    user_username: string | null;
    product_name: string;
  }>;
};

export default function DashboardPage() {
  const { isOn } = useFeatures();
  const { data, isLoading } = useSWR<Overview>('/stats/overview', fetcher, { refreshInterval: 30000 });

  return (
    <div>
      <PageHeader
        title="Обзор"
        subtitle="Краткая сводка по магазину доступов"
      />

      {isLoading || !data ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="glass rounded-2xl p-5 h-28 animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5">
            {isOn('monetization') && (
            <Stat
              label="Активные подписки"
              value={data.subscriptions.active}
              hint={data.subscriptions.expiring_7d > 0
                ? `Истекают за 7 дней: ${data.subscriptions.expiring_7d}`
                : 'Срочных истечений нет'}
              accent="violet"
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
                </svg>
              }
            />
            )}
            {isOn('leads') && (
            <Stat
              label="Новые заявки"
              value={data.leads.new}
              hint={`За 24 ч: ${data.leads.last_24h} · Всего: ${data.leads.total}`}
              accent="amber"
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 4h16v14H7l-3 3z" /><path d="M8 9h8M8 13h5" />
                </svg>
              }
            />
            )}
            <Stat
              label="Пользователи бота"
              value={data.users.total}
              hint={`Новых за 7 дней: ${data.users.new_7d}`}
              accent="indigo"
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
                </svg>
              }
            />
            {isOn('monetization') && (
            <Stat
              label="Оборот за 30 дней"
              value={fmtMoney(data.revenue.last_30d)}
              hint={(() => {
                const n = data.revenue.payments_30d;
                const sum30 = Number(data.revenue.last_30d) || 0;
                const avg = n > 0 ? sum30 / n : 0;
                return `Платежей: ${n}${avg ? ` · ср.чек ${fmtMoney(avg)}` : ''}`;
              })()}
              accent="teal"
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="6" width="18" height="13" rx="2" /><path d="M16 12h3" />
                </svg>
              }
            />
            )}
          </section>

          <section className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Последние заявки */}
            {isOn('leads') && (
            <Card padded className="anim-rise">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-semibold tracking-tight">Последние заявки</h3>
                  <p className="text-xs text-zinc-500">Свежие запросы из бота</p>
                </div>
                <Link href="/leads" className="text-xs text-indigo-600 hover:text-indigo-800 transition">Все →</Link>
              </div>
              {data.recent_leads.length === 0 ? (
                <Empty>Заявок пока нет</Empty>
              ) : (
                <ul className="space-y-1">
                  {data.recent_leads.map((l) => (
                    <li key={l.id}>
                      <Link
                        href={`/leads/${l.id}`}
                        className="flex items-center gap-3 px-2 py-2.5 rounded-xl hover:bg-white/60 transition"
                      >
                        <Avatar text={initials(l.user_first_name, l.user_username)} />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-ink truncate">
                            {l.user_first_name || '—'}
                            {l.user_username && <span className="text-zinc-500"> · @{l.user_username}</span>}
                          </div>
                          <div className="text-xs text-zinc-500 truncate">{l.product_name}</div>
                        </div>
                        <LeadStatusPill s={l.status} />
                        <time className="hidden sm:block ml-2 text-xs text-zinc-400">
                          {timeAgo(l.created_at)}
                        </time>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            )}

            {/* Последние платежи */}
            {isOn('monetization') && (
            <Card padded className="anim-rise">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-base font-semibold tracking-tight">Последние платежи</h3>
                  <p className="text-xs text-zinc-500">Зафиксированные оплаты</p>
                </div>
                <Link href="/payments" className="text-xs text-indigo-600 hover:text-indigo-800 transition">Все →</Link>
              </div>
              {data.recent_payments.length === 0 ? (
                <Empty>Платежей пока нет</Empty>
              ) : (
                <ul className="space-y-1">
                  {data.recent_payments.map((p) => (
                    <li key={p.id} className="flex items-center gap-3 px-2 py-2.5 rounded-xl hover:bg-white/60 transition">
                      <Avatar text={initials(p.user_first_name, p.user_username)} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-ink truncate">
                          {p.user_first_name || '—'}
                          {p.user_username && <span className="text-zinc-500"> · @{p.user_username}</span>}
                        </div>
                        <div className="text-xs text-zinc-500 truncate">
                          {p.product_name} · {p.period_months} мес.
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold text-ink">
                          {fmtMoney(p.amount)} <span className="text-xs text-zinc-500">{p.currency}</span>
                        </div>
                        <div className="text-xs text-zinc-400">{timeAgo(p.created_at)}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            )}
          </section>

          {isOn('leads') && <CancelReasonsCard />}

          <section className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-5">
            <CatalogCard label="Продукты" value={data.catalog.products} hint="карточки каналов" href="/products" />
            <CatalogCard label="Каналы" value={data.catalog.channels} hint="закрытые TG-каналы" href="/channels" />
            <CatalogCard label="Активные боты" value={data.catalog.active_bots} hint="polling запущен" href="/bots" />
          </section>
        </>
      )}
    </div>
  );
}

function CancelReasonsCard() {
  const { data } = useSWR<{ breakdown: { reason: string; count: number }[]; total: number }>(
    '/leads/cancel-reasons', fetcher, { refreshInterval: 60_000 },
  );
  if (!data || data.total === 0) return null;
  const max = Math.max(...data.breakdown.map((b) => b.count), 1);
  return (
    <section className="mt-6">
      <Card padded className="anim-rise">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold tracking-tight">Причины отмены</h3>
            <p className="text-xs text-zinc-500">Почему заявки не закрылись — {data.total} всего</p>
          </div>
          <Link href="/leads?status=cancelled" className="text-xs text-indigo-600 hover:text-indigo-800 transition">Отменённые →</Link>
        </div>
        <ul className="space-y-2">
          {data.breakdown.map((b) => (
            <li key={b.reason} className="flex items-center gap-3">
              <span className="text-sm text-ink w-48 shrink-0 truncate" title={b.reason}>{b.reason}</span>
              <div className="flex-1 h-2 rounded-full bg-zinc-100 overflow-hidden">
                <div className="h-full rounded-full bg-rose-400" style={{ width: `${(b.count / max) * 100}%` }} />
              </div>
              <span className="text-sm font-medium tabular-nums w-8 text-right">{b.count}</span>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}

function CatalogCard({ label, value, hint, href }: { label: string; value: number; hint: string; href: string }) {
  return (
    <Link
      href={href}
      className="glass rounded-2xl p-5 hover:shadow-glass-lg transition group anim-rise"
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500 font-medium">{label}</div>
          <div className="mt-1.5 text-3xl font-bold tracking-tight text-ink">{value}</div>
          <div className="mt-0.5 text-xs text-zinc-500">{hint}</div>
        </div>
        <span className="size-9 rounded-xl glass-soft flex items-center justify-center text-zinc-500 group-hover:text-indigo-600 transition">
          →
        </span>
      </div>
    </Link>
  );
}

function Avatar({ text }: { text: string }) {
  return (
    <span className="shrink-0 size-8 rounded-full gradient-primary text-white text-[11px] font-semibold flex items-center justify-center shadow-soft">
      {text}
    </span>
  );
}

function initials(firstName: string | null, username: string | null): string {
  const src = (firstName || username || 'U').trim();
  return src.slice(0, 2).toUpperCase();
}

function fmtMoney(s: string | number): string {
  const n = Number(s);
  if (!Number.isFinite(n)) return String(s);
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

function timeAgo(iso: string): string {
  const t = new Date(iso).getTime();
  const sec = Math.max(1, Math.floor((Date.now() - t) / 1000));
  if (sec < 60) return `${sec} с`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} мин`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} ч`;
  const d = Math.floor(hr / 24);
  if (d < 30) return `${d} д`;
  return new Date(iso).toLocaleDateString('ru-RU');
}

function LeadStatusPill({ s }: { s: string }) {
  if (s === 'new') return <Pill color="amber">новая</Pill>;
  if (s === 'contacted') return <Pill color="gray">связались</Pill>;
  if (s === 'paid') return <Pill color="green">оплачена</Pill>;
  if (s === 'closed') return <Pill color="red">закрыта</Pill>;
  return <Pill color="gray">{s}</Pill>;
}

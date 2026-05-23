'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ReactNode, useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';

type Me = { id: number; username: string; role?: string };
type Overview = {
  leads: { new: number };
  subscriptions: { expiring_7d: number };
};
type Funnel = { id: number; steps_count: number; is_active: boolean };

/* ---------- Icons ---------- */
const baseIcon = 'w-full h-full';

const I = {
  Home: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /><path d="M9 21V14h6v7" />
    </svg>
  ),
  Leads: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16v14H7l-3 3z" /><path d="M8 9h8M8 13h5" />
    </svg>
  ),
  Users: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  Wallet: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="6" width="18" height="13" rx="2" /><path d="M16 12h3" /><path d="M3 10h18" />
    </svg>
  ),
  Subs: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
    </svg>
  ),
  Product: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 7l-8-4-8 4v10l8 4 8-4z" /><path d="M4 7l8 4 8-4" /><path d="M12 11v10" />
    </svg>
  ),
  Channel: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 11l18-8-8 18-2-8z" />
    </svg>
  ),
  Bot: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="8" width="18" height="12" rx="3" /><path d="M12 4v4" /><circle cx="8" cy="14" r="1" /><circle cx="16" cy="14" r="1" />
    </svg>
  ),
  Source: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="3" /><circle cx="18" cy="18" r="3" /><path d="M9 6h6l3 12" />
    </svg>
  ),
  Funnel: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 5h18l-7 8v6l-4 2v-8z" />
    </svg>
  ),
  Magnet: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 4v8a6 6 0 0 0 12 0V4" /><path d="M6 4h4" /><path d="M14 4h4" />
    </svg>
  ),
  Trigger: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2L3 14h7l-1 8 10-12h-7z" />
    </svg>
  ),
  Shield: () => (
    <svg className={baseIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  Chevron: () => (
    <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M6 9l6 6 6-6" />
    </svg>
  ),
  Logout: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  ),
  Settings: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
};

/* ---------- Navigation structure ---------- */

type NavItem = {
  href: string;
  label: string;
  icon: ReactNode;
  badge?: (counts: NavCounts) => number | undefined;
};

type NavGroup = {
  key: string;
  label?: string;        // если undefined — без заголовка, всегда expanded
  defaultCollapsed?: boolean;
  adminOnly?: boolean;
  items: NavItem[];
};

type NavCounts = {
  newLeads: number;
  funnelsTodo: number;
  expiringSubs: number;
};

const NAV_GROUPS: NavGroup[] = [
  {
    key: 'top',
    items: [
      { href: '/', label: 'Обзор', icon: <I.Home /> },
    ],
  },
  {
    key: 'analytics',
    label: 'Аналитика',
    items: [
      { href: '/sources', label: 'Источники', icon: <I.Source /> },
    ],
  },
  {
    key: 'sales',
    label: 'Продажи',
    items: [
      { href: '/leads', label: 'Заявки', icon: <I.Leads />, badge: (c) => c.newLeads },
      { href: '/payments', label: 'Платежи', icon: <I.Wallet /> },
      { href: '/subscriptions', label: 'Подписки', icon: <I.Subs />, badge: (c) => c.expiringSubs },
    ],
  },
  {
    key: 'funnels',
    label: 'Воронки',
    items: [
      { href: '/funnels', label: 'Воронки', icon: <I.Funnel />, badge: (c) => c.funnelsTodo },
      { href: '/lead-magnets', label: 'Лидмагниты', icon: <I.Magnet /> },
      { href: '/funnel-triggers', label: 'Кодовые слова', icon: <I.Trigger /> },
    ],
  },
  {
    key: 'catalog',
    label: 'Каталог',
    defaultCollapsed: false,
    items: [
      { href: '/products', label: 'Продукты', icon: <I.Product /> },
      { href: '/channels', label: 'Каналы', icon: <I.Channel /> },
      { href: '/bots', label: 'Боты', icon: <I.Bot /> },
    ],
  },
  {
    key: 'audience',
    label: 'Аудитория',
    items: [
      { href: '/users', label: 'Пользователи', icon: <I.Users /> },
    ],
  },
  {
    key: 'admin',
    label: 'Администрирование',
    adminOnly: true,
    defaultCollapsed: true,
    items: [
      { href: '/audit-log', label: 'Аудит-журнал', icon: <I.Shield /> },
    ],
  },
];

const LS_COLLAPSED_KEY = 'sidebar-collapsed-groups-v2';

export default function DashLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [navOpen, setNavOpen] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(() => {
    if (typeof window === 'undefined') return new Set();
    try {
      const raw = window.localStorage.getItem(LS_COLLAPSED_KEY);
      if (raw) return new Set(JSON.parse(raw));
    } catch {}
    // дефолтные свёрнутые группы
    return new Set(NAV_GROUPS.filter((g) => g.defaultCollapsed).map((g) => g.key));
  });

  // Бейджи — лёгкий polling overview + funnels раз в минуту
  const { data: overview } = useSWR<Overview>('/stats/overview', fetcher, {
    refreshInterval: 60_000,
    revalidateOnFocus: false,
  });
  const { data: funnels } = useSWR<Funnel[]>('/funnels', fetcher, {
    refreshInterval: 120_000,
    revalidateOnFocus: false,
  });

  const counts: NavCounts = useMemo(() => ({
    newLeads: overview?.leads?.new || 0,
    expiringSubs: overview?.subscriptions?.expiring_7d || 0,
    // "Требует внимания" = пустая воронка (без шагов) ИЛИ готовый черновик без публикации.
    // Активная воронка с шагами — всё на месте, в badge не попадает.
    funnelsTodo: (funnels || []).filter(
      (f) => f.steps_count === 0 || (!f.is_active && f.steps_count > 0),
    ).length,
  }), [overview, funnels]);

  useEffect(() => {
    let cancelled = false;
    api
      .get<Me>('/auth/me')
      .then((d) => {
        if (!cancelled) {
          setMe(d);
          setLoading(false);
        }
      })
      .catch(() => router.replace('/login'));
    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => { setNavOpen(false); }, [pathname]);

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      if (typeof window !== 'undefined') {
        try { window.localStorage.setItem(LS_COLLAPSED_KEY, JSON.stringify([...next])); } catch {}
      }
      return next;
    });
  }

  async function logout() {
    try { await api.post('/auth/logout'); } catch {}
    router.replace('/login');
  }

  const breadcrumbs = useMemo(() => buildBreadcrumbs(pathname), [pathname]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-zinc-500 anim-fade">
        <div className="glass rounded-2xl px-6 py-4">Загрузка…</div>
      </div>
    );
  }

  const isAdmin = !me?.role || me.role === 'admin';
  const visibleGroups = NAV_GROUPS.filter((g) => !g.adminOnly || isAdmin);

  const sidebar = (
    <aside
      className={clsx(
        'glass-strong rounded-none sm:rounded-2xl flex flex-col w-[260px]',
        'sm:m-3 sm:h-[calc(100vh-1.5rem)] sm:sticky sm:top-3',
        'fixed inset-y-0 left-0 z-50 transition-transform duration-300',
        navOpen ? 'translate-x-0' : '-translate-x-full',
        'sm:translate-x-0 sm:static',
      )}
    >
      {/* Header */}
      <div className="px-5 py-5 flex items-center gap-3 shrink-0">
        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition">
          <div className="size-9 rounded-xl gradient-primary text-white font-bold flex items-center justify-center shadow-[0_8px_20px_-8px_rgba(124,58,237,0.6)]">
            i
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">Infobizbot</div>
            <div className="text-[10px] uppercase tracking-widest text-zinc-500">admin</div>
          </div>
        </Link>
        <button
          className="ml-auto sm:hidden text-zinc-500 hover:text-ink transition"
          onClick={() => setNavOpen(false)}
          aria-label="Закрыть"
        >
          ✕
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 pb-3 space-y-3">
        {visibleGroups.map((group) => {
          const isCollapsed = collapsedGroups.has(group.key);
          return (
            <div key={group.key}>
              {group.label && (
                <button
                  type="button"
                  onClick={() => toggleGroup(group.key)}
                  className="w-full flex items-center justify-between px-3 mb-1 text-zinc-400 hover:text-zinc-700 transition"
                >
                  <span className="text-[10px] uppercase tracking-widest font-medium">
                    {group.label}
                  </span>
                  <span className={clsx('transition-transform', isCollapsed ? '-rotate-90' : '')}>
                    <I.Chevron />
                  </span>
                </button>
              )}
              {!isCollapsed && (
                <div className="space-y-1 anim-fade">
                  {group.items.map((item) => {
                    const active =
                      (item.href === '/' && pathname === '/') ||
                      (item.href !== '/' && (pathname === item.href || pathname.startsWith(item.href + '/')));
                    const badgeValue = item.badge ? item.badge(counts) : undefined;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={clsx(
                          'relative flex items-center gap-3 px-3 h-10 rounded-xl text-sm transition group',
                          active
                            ? 'text-ink bg-white/85 shadow-soft'
                            : 'text-zinc-600 hover:text-ink hover:bg-white/60',
                        )}
                      >
                        {active && (
                          <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full gradient-primary" />
                        )}
                        <span className={clsx(
                          'shrink-0 size-5',
                          active ? 'text-indigo-600' : 'text-zinc-400 group-hover:text-zinc-700',
                        )}>
                          {item.icon}
                        </span>
                        <span className="flex-1">{item.label}</span>
                        {badgeValue != null && badgeValue > 0 && (
                          <NavBadge value={badgeValue} active={active} />
                        )}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer — пользователь */}
      <div className="p-3 shrink-0">
        <div className="glass rounded-xl px-3 py-2.5 flex items-center gap-2.5">
          <div className="size-8 rounded-full gradient-primary text-white text-xs font-semibold flex items-center justify-center shrink-0">
            {(me?.username?.[0] || 'A').toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{me?.username}</div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest">
              {me?.role || 'admin'}
            </div>
          </div>
          <Link
            href="/account"
            className="size-7 inline-flex items-center justify-center rounded-lg text-zinc-400 hover:text-ink hover:bg-white/70 transition"
            aria-label="Профиль"
            title="Профиль"
          >
            <I.Settings />
          </Link>
          <button
            onClick={logout}
            className="size-7 inline-flex items-center justify-center rounded-lg text-zinc-400 hover:text-rose-600 hover:bg-rose-50/60 transition"
            aria-label="Выйти"
            title="Выйти"
          >
            <I.Logout />
          </button>
        </div>
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen sm:flex">
      {sidebar}

      {navOpen && (
        <div
          className="sm:hidden fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-[2px] anim-fade"
          onClick={() => setNavOpen(false)}
          aria-hidden
        />
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-30 sm:top-3 sm:mx-3 mt-0 sm:mt-3">
          <div className="glass sm:rounded-2xl px-4 sm:px-5 h-14 sm:h-14 flex items-center gap-3">
            <button
              className="sm:hidden inline-flex items-center justify-center size-9 rounded-xl text-zinc-700 hover:bg-white/70"
              onClick={() => setNavOpen(true)}
              aria-label="Открыть меню"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M3 6h18M3 12h18M3 18h18" />
              </svg>
            </button>

            <Breadcrumbs items={breadcrumbs} />

            <div className="ml-auto flex items-center gap-2">
              {counts.newLeads > 0 && (
                <Link
                  href="/leads"
                  className="hidden sm:inline-flex items-center gap-2 text-xs px-3 h-8 rounded-lg bg-amber-50/80 hover:bg-amber-100/80 transition text-amber-800 border border-amber-200/60"
                  title={`${counts.newLeads} новых заявок`}
                >
                  <I.Leads />
                  <span className="font-medium">{counts.newLeads} новых заявок</span>
                </Link>
              )}
            </div>
          </div>
        </header>

        <main className="px-4 sm:px-6 py-5 sm:py-6 max-w-[1400px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

/* ---------- NavBadge ---------- */
function NavBadge({ value, active }: { value: number; active: boolean }) {
  const display = value > 99 ? '99+' : String(value);
  return (
    <span
      className={clsx(
        'inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-semibold tabular-nums',
        active
          ? 'bg-indigo-100 text-indigo-700'
          : 'bg-amber-100/80 text-amber-700 group-hover:bg-amber-200/70',
      )}
    >
      {display}
    </span>
  );
}

/* ---------- Breadcrumbs ---------- */
function Breadcrumbs({ items }: { items: Array<{ label: string; href?: string }> }) {
  return (
    <nav className="flex items-center text-sm min-w-0">
      {items.map((b, i) => (
        <span key={i} className="flex items-center min-w-0">
          {i > 0 && <span className="mx-1.5 text-zinc-300">/</span>}
          {b.href ? (
            <Link href={b.href} className="text-zinc-500 hover:text-ink truncate transition">
              {b.label}
            </Link>
          ) : (
            <span className="font-semibold text-ink truncate">{b.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

function buildBreadcrumbs(pathname: string): Array<{ label: string; href?: string }> {
  const map: Record<string, string> = {
    '': 'Обзор',
    bots: 'Боты',
    channels: 'Каналы',
    products: 'Продукты',
    users: 'Пользователи',
    leads: 'Заявки',
    payments: 'Платежи',
    subscriptions: 'Подписки',
    sources: 'Источники',
    account: 'Профиль',
    funnels: 'Воронки',
    'lead-magnets': 'Лидмагниты',
    'funnel-triggers': 'Кодовые слова',
    'audit-log': 'Аудит-журнал',
    edit: 'Студия',
    entries: 'Подписчики',
  };
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length === 0) return [{ label: 'Обзор' }];
  const out: Array<{ label: string; href?: string }> = [{ label: 'Обзор', href: '/' }];
  let acc = '';
  for (let i = 0; i < parts.length; i++) {
    acc += '/' + parts[i];
    const p = parts[i];
    const isLast = i === parts.length - 1;
    const label = map[p] || decodeURIComponent(p);
    out.push({ label, href: isLast ? undefined : acc });
  }
  return out;
}

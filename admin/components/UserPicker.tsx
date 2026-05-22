'use client';

import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';

import { api } from '@/lib/api';

export type PickedUser = {
  id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  telegram_user_id: number;
};

type Props = {
  value: PickedUser | null;
  onChange: (u: PickedUser | null) => void;
  placeholder?: string;
  autoFocus?: boolean;
};

function userLabel(u: PickedUser): string {
  const name = [u.first_name, u.last_name].filter(Boolean).join(' ').trim();
  const at = u.username ? `@${u.username}` : '';
  if (name && at) return `${name} · ${at}`;
  return name || at || `id ${u.telegram_user_id}`;
}

export function UserPicker({
  value,
  onChange,
  placeholder = 'Имя, @username или Telegram ID',
  autoFocus,
}: Props) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<PickedUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    const tm = setTimeout(async () => {
      try {
        const resp = await api.get<{ items: PickedUser[] }>(
          `/users?q=${encodeURIComponent(query)}&limit=20`,
        );
        if (!cancelled) {
          setItems(resp.items);
          setActive(0);
        }
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 180);
    return () => {
      cancelled = true;
      clearTimeout(tm);
    };
  }, [query, open]);

  function pick(u: PickedUser) {
    onChange(u);
    setOpen(false);
    setQuery('');
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') setOpen(true);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, Math.max(items.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const u = items[active];
      if (u) pick(u);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  }

  return (
    <div className="relative" ref={wrapRef}>
      {value ? (
        <div className="flex items-center gap-2 w-full h-10 px-3.5 rounded-xl bg-white/85 backdrop-blur border border-white/70 text-sm shadow-soft">
          <Avatar text={initials(value)} />
          <span className="truncate text-ink">{userLabel(value)}</span>
          <button
            type="button"
            className="ml-auto text-zinc-400 hover:text-zinc-900 transition"
            onClick={() => {
              onChange(null);
              setQuery('');
              setTimeout(() => setOpen(true), 0);
            }}
            aria-label="Очистить"
          >
            ✕
          </button>
        </div>
      ) : (
        <input
          type="text"
          className="w-full h-10 px-3.5 rounded-xl bg-white/85 backdrop-blur border border-white/70 text-sm text-ink placeholder-zinc-400 shadow-soft focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-300/40"
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          autoFocus={autoFocus}
        />
      )}

      {open && !value && (
        <div className="absolute z-50 left-0 right-0 mt-1.5 max-h-72 overflow-auto glass-strong rounded-xl p-1 anim-fade">
          {loading && (
            <div className="px-3 py-3 text-sm text-zinc-500">Поиск…</div>
          )}
          {!loading && items.length === 0 && (
            <div className="px-3 py-3 text-sm text-zinc-500">
              Никого не нашли. Пользователь должен сначала нажать /start в боте.
            </div>
          )}
          {!loading &&
            items.map((u, i) => (
              <button
                key={u.id}
                type="button"
                onMouseEnter={() => setActive(i)}
                onClick={() => pick(u)}
                className={clsx(
                  'w-full text-left px-2.5 py-2 rounded-lg text-sm flex items-center gap-3 transition',
                  i === active ? 'bg-indigo-50/80' : 'hover:bg-white/70',
                )}
              >
                <Avatar text={initials(u)} />
                <span className="flex-1 min-w-0">
                  <span className="block font-medium text-ink truncate">
                    {[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}
                  </span>
                  <span className="block text-xs text-zinc-500 truncate">
                    {u.username ? '@' + u.username + ' · ' : ''}id {u.telegram_user_id}
                  </span>
                </span>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}

function Avatar({ text }: { text: string }) {
  return (
    <span className="shrink-0 size-7 rounded-full gradient-primary text-white text-[11px] font-semibold flex items-center justify-center shadow-soft">
      {text}
    </span>
  );
}

function initials(u: PickedUser): string {
  const a = (u.first_name || u.username || '').slice(0, 1).toUpperCase();
  const b = (u.last_name || '').slice(0, 1).toUpperCase();
  return (a + b) || 'U';
}

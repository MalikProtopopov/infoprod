'use client';
import clsx from 'clsx';
import {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  useEffect,
} from 'react';

/* ---------- Buttons ---------- */
type BtnVariant = 'primary' | 'ghost' | 'danger' | 'glass';
type BtnSize = 'sm' | 'md' | 'lg';

export function Button({
  className,
  variant = 'primary',
  size = 'md',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: BtnSize }) {
  const base =
    'inline-flex items-center justify-center font-medium rounded-xl transition-all duration-200 ' +
    'disabled:opacity-50 disabled:cursor-not-allowed select-none whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/60 focus-visible:ring-offset-2';
  const sizes: Record<BtnSize, string> = {
    sm: 'h-8 px-3 text-xs',
    md: 'h-10 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
  };
  const variants: Record<BtnVariant, string> = {
    primary:
      'gradient-primary gradient-primary-hover text-white shadow-[0_10px_24px_-12px_rgba(79,70,229,0.6)] hover:shadow-[0_14px_30px_-12px_rgba(124,58,237,0.7)] active:translate-y-px',
    ghost:
      'glass-soft text-ink hover:bg-white/80 hover:shadow-soft active:translate-y-px',
    danger:
      'gradient-danger text-white shadow-[0_10px_24px_-12px_rgba(225,29,72,0.55)] hover:brightness-110 active:translate-y-px',
    glass:
      'glass text-ink hover:shadow-glass-lg active:translate-y-px',
  };
  return <button {...rest} className={clsx(base, sizes[size], variants[variant], className)} />;
}

/* ---------- IconButton ---------- */
export function IconButton({ className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      className={clsx(
        'inline-flex items-center justify-center w-9 h-9 rounded-xl text-zinc-600 hover:bg-white/70 hover:text-zinc-900 transition',
        className,
      )}
    />
  );
}

/* ---------- Inputs ---------- */
const INPUT_CLASS =
  'w-full h-10 px-3.5 rounded-xl bg-white/85 backdrop-blur border border-white/70 ' +
  'text-sm text-ink placeholder-zinc-400 transition shadow-soft ' +
  'focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-300/40';

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx(INPUT_CLASS, props.className)} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={clsx(
        'w-full px-3.5 py-2.5 rounded-xl bg-white/85 backdrop-blur border border-white/70 text-sm text-ink placeholder-zinc-400 transition shadow-soft',
        'focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-300/40',
        props.className,
      )}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={clsx(INPUT_CLASS, 'pr-8 appearance-none', props.className)} />;
}

export function Field({
  label,
  children,
  hint,
  required,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  required?: boolean;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="block text-xs font-medium text-zinc-700 tracking-wide uppercase">
        {label}{required && <span className="text-rose-500"> *</span>}
      </span>
      {children}
      {hint && <span className="block text-[11px] text-zinc-500 leading-snug">{hint}</span>}
    </label>
  );
}

/* ---------- Cards ---------- */
export function Card({ children, className, padded = false }: { children: ReactNode; className?: string; padded?: boolean }) {
  return (
    <div className={clsx('glass rounded-2xl', padded && 'p-5 sm:p-6', className)}>{children}</div>
  );
}

export function PlainCard({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx('bg-white border border-zinc-200/80 rounded-2xl shadow-soft', className)}>{children}</div>
  );
}

/* ---------- Table-wrap ---------- */
// overflow-x-auto оставляем для горизонтального скролла на mobile,
// overflow-y-hidden обрезает hover-фон строк по углам, чтобы они не торчали
// за пределы скруглённой Card. rounded-[inherit] наследует радиус от Card.
export function TableWrap({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto overflow-y-hidden rounded-[inherit]">
      {children}
    </div>
  );
}

/* ---------- Page header ---------- */
export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-5 sm:mb-7 anim-rise">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>}
      </div>
      {action && <div className="flex flex-wrap gap-2">{action}</div>}
    </div>
  );
}

/* ---------- Empty / pill ---------- */
export function Empty({ children }: { children: ReactNode }) {
  return <div className="text-sm text-zinc-500 py-12 text-center">{children}</div>;
}

/* ---------- Skeleton loaders ---------- */

/** Базовый pulsing-блок. Принимает className для размера. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        'rounded-md bg-zinc-200/70 animate-pulse',
        className,
      )}
      aria-hidden
    />
  );
}

/** Скелетон-строка для таблицы — повторяет высоту обычной Tr. */
export function SkeletonRow({ cols = 4, widths }: { cols?: number; widths?: string[] }) {
  const defaultWidths = ['w-1/3', 'w-1/4', 'w-1/5', 'w-1/6', 'w-1/5', 'w-1/4'];
  return (
    <tr className="border-t border-zinc-100/80">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className={clsx('h-4', widths?.[i] || defaultWidths[i] || 'w-1/4')} />
        </td>
      ))}
    </tr>
  );
}

/** Скелетон для блоков-карточек — фоновая «карточка» с заглушками. */
export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="glass rounded-2xl p-5 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={clsx('h-3', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  );
}

type PillColor = 'indigo' | 'violet' | 'green' | 'amber' | 'red' | 'gray' | 'sky' | 'rose';
const PILL_STYLES: Record<PillColor, string> = {
  indigo: 'bg-indigo-100/80 text-indigo-700 ring-indigo-200',
  violet: 'bg-violet-100/80 text-violet-700 ring-violet-200',
  green: 'bg-emerald-100/80 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-100/80 text-amber-700 ring-amber-200',
  red: 'bg-rose-100/80 text-rose-700 ring-rose-200',
  rose: 'bg-rose-100/80 text-rose-700 ring-rose-200',
  gray: 'bg-zinc-100/80 text-zinc-700 ring-zinc-200',
  sky: 'bg-sky-100/80 text-sky-700 ring-sky-200',
};

export function Pill({ children, color = 'gray' }: { children: ReactNode; color?: PillColor }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
        PILL_STYLES[color],
      )}
    >
      {children}
    </span>
  );
}

/* ---------- Sheet (drawer справа) ---------- */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: 'md' | 'lg';
}) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/30 backdrop-blur-[2px] anim-fade"
        onClick={onClose}
      />
      {/* Panel */}
      <div
        className={clsx(
          'absolute inset-y-0 right-0 w-full sm:max-w-[480px] flex flex-col anim-slide-right',
          size === 'lg' && 'sm:max-w-[640px]',
        )}
      >
        <div className="m-0 sm:m-3 flex-1 glass-strong sm:rounded-2xl overflow-hidden flex flex-col">
          <header className="px-5 py-4 border-b border-white/40 flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold tracking-tight text-ink truncate">{title}</h2>
              {description && <p className="text-xs text-zinc-500 mt-0.5">{description}</p>}
            </div>
            <IconButton onClick={onClose} aria-label="Закрыть">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </IconButton>
          </header>
          <div className="flex-1 overflow-auto p-5">{children}</div>
          {footer && (
            <footer className="px-5 py-4 border-t border-white/40 bg-white/40 flex justify-end gap-2">
              {footer}
            </footer>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- Modal (compat shim — старые места могут использовать Modal) ---------- */
export const Modal = Sheet;

/* ---------- Stat card для дашборда ---------- */
export function Stat({
  label,
  value,
  hint,
  icon,
  accent = 'indigo',
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  accent?: 'indigo' | 'violet' | 'rose' | 'teal' | 'amber';
}) {
  const accentClass: Record<string, string> = {
    indigo: 'from-indigo-500/15 to-indigo-500/5 text-indigo-600',
    violet: 'from-violet-500/15 to-violet-500/5 text-violet-600',
    rose: 'from-rose-500/15 to-rose-500/5 text-rose-600',
    teal: 'from-teal-500/15 to-teal-500/5 text-teal-600',
    amber: 'from-amber-500/15 to-amber-500/5 text-amber-600',
  };
  return (
    <div className="glass rounded-2xl p-5 anim-rise">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wide text-zinc-500 font-medium">{label}</div>
          <div className="mt-1.5 text-3xl font-bold tracking-tight text-ink">{value}</div>
          {hint && <div className="mt-0.5 text-xs text-zinc-500">{hint}</div>}
        </div>
        {icon && (
          <div className={clsx('shrink-0 size-11 rounded-xl flex items-center justify-center bg-gradient-to-br', accentClass[accent])}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- Simple Table styling helpers ---------- */
export function TableHead({ children }: { children: ReactNode }) {
  return (
    <thead className="bg-white/40 backdrop-blur text-left text-[11px] uppercase tracking-wider text-zinc-500 border-b border-zinc-200/70">
      <tr>{children}</tr>
    </thead>
  );
}

export function Th({ children, className }: { children?: ReactNode; className?: string }) {
  return <th className={clsx('px-4 py-3 font-medium', className)}>{children}</th>;
}

export function Tr(props: HTMLAttributes<HTMLTableRowElement>) {
  return <tr {...props} className={clsx('border-t border-zinc-100/80 hover:bg-white/40 transition', props.className)} />;
}

export function Td({ children, className }: { children?: ReactNode; className?: string }) {
  return <td className={clsx('px-4 py-3', className)}>{children}</td>;
}

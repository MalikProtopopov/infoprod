'use client';

import {
  createContext, useCallback, useContext, useEffect, useRef, useState,
} from 'react';
import clsx from 'clsx';

/**
 * Лёгкий глобальный toast.
 *
 * Использование:
 *   const { showToast } = useToast();
 *   showToast('Ссылка скопирована');
 *   showToast('Не удалось сохранить', { type: 'error' });
 *
 * Подключается через <ToastProvider> в корневом layout.
 */

type ToastType = 'success' | 'error' | 'info';

type ToastItem = {
  id: number;
  message: string;
  type: ToastType;
};

type ToastContextValue = {
  showToast: (message: string, opts?: { type?: ToastType; durationMs?: number }) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Если провайдер не подключён — даём no-op, чтобы не падать в SSR/тестах.
    return { showToast: () => {} };
  }
  return ctx;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback<ToastContextValue['showToast']>((message, opts) => {
    const id = ++idRef.current;
    const type: ToastType = opts?.type ?? 'success';
    const durationMs = opts?.durationMs ?? 2400;
    setToasts((prev) => [...prev, { id, message, type }]);
    if (durationMs > 0) {
      window.setTimeout(() => dismiss(id), durationMs);
    }
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}) {
  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className="fixed z-[100] bottom-4 right-4 flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} item={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  );
}

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    const r = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(r);
  }, []);

  const palette: Record<ToastType, string> = {
    success: 'bg-emerald-600/95 text-white',
    error:   'bg-rose-600/95 text-white',
    info:    'bg-zinc-800/95 text-white',
  };
  const icon: Record<ToastType, React.ReactNode> = {
    success: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    ),
    error: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    ),
    info: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <line x1="12" y1="8" x2="12" y2="13" />
        <circle cx="12" cy="16.5" r="0.6" fill="currentColor" />
      </svg>
    ),
  };

  return (
    <div
      role="status"
      onClick={onDismiss}
      className={clsx(
        'pointer-events-auto cursor-pointer select-none',
        'flex items-center gap-2.5 pl-3 pr-4 py-2.5 rounded-xl shadow-xl backdrop-blur-sm',
        'text-sm font-medium min-w-[200px] max-w-[360px]',
        'transition-all duration-200',
        entered ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0',
        palette[item.type],
      )}
    >
      <span className="shrink-0 inline-flex items-center justify-center size-5 rounded-full bg-white/15">
        {icon[item.type]}
      </span>
      <span className="truncate">{item.message}</span>
    </div>
  );
}

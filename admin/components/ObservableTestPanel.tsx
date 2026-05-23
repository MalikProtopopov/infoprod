'use client';

import { useEffect, useState } from 'react';

import { api } from '@/lib/api';
import { Button } from '@/components/ui';

type TestMessage = {
  step_order_idx: number;
  step_message_text: string;
  scheduled_at: string;
  sent_at: string | null;
  cancelled_at: string | null;
  error: string | null;
};

type StatusResponse = {
  entry_id: number;
  entry_status: string;
  messages: TestMessage[];
};

/**
 * Observable test panel: polls /test-run/{id}/status каждые 2 сек,
 * рендерит прогресс с relative-таймштампами и кнопкой [Открыть TG].
 */
export function ObservableTestPanel({
  funnelId,
  testEntryId,
  botUsername,
  onClose,
}: {
  funnelId: number;
  testEntryId: number;
  botUsername?: string;
  onClose: () => void;
}) {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [stopped, setStopped] = useState(false);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    let active = true;
    async function poll() {
      while (active && !stopped) {
        try {
          const data = await api.get<StatusResponse>(
            `/funnels/${funnelId}/test-run/${testEntryId}/status`,
          );
          if (active) setStatus(data);
          if (data.entry_status !== 'active') break;
        } catch {
          // ignore — продолжаем опрос
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
    void poll();
    return () => { active = false; };
  }, [funnelId, testEntryId, stopped]);

  if (!status) {
    return (
      <div className="glass rounded-2xl p-4 text-sm text-zinc-500">
        Запускаем тестовый прогон…
      </div>
    );
  }

  const sentCount = status.messages.filter((m) => m.sent_at).length;
  const total = status.messages.length;

  return (
    <div className="glass-strong rounded-2xl p-4 sm:p-5 anim-rise">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <h3 className="font-semibold tracking-tight">Тестовый прогон</h3>
          <p className="text-xs text-zinc-500">
            Все шаги уменьшены в 60 раз: «1 день» = 24 сек, «1 час» = 1 мин.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-zinc-400 hover:text-ink transition"
          aria-label="Закрыть"
        >
          ✕
        </button>
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-500 mb-3">
        <span>Прогресс: {sentCount} из {total} шагов отправлено</span>
        <span>{status.entry_status === 'active' ? '🟢 идёт' : '⏹ завершён'}</span>
      </div>

      <ul className="space-y-2 max-h-[400px] overflow-auto">
        {status.messages.map((m) => {
          const stateInfo = getStateInfo(m, now);
          return (
            <li
              key={m.step_order_idx}
              className={`rounded-xl p-3 border ${stateInfo.bg}`}
            >
              <div className="flex items-start gap-3">
                <div className="text-lg shrink-0">{stateInfo.icon}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">
                    Шаг {m.step_order_idx + 1}
                  </div>
                  <div className="text-xs text-zinc-600 mt-0.5 truncate">
                    «{m.step_message_text}»
                  </div>
                  <div className="text-[11px] text-zinc-500 mt-1">
                    {stateInfo.label}
                  </div>
                  {/* Прогресс-бар для ожидающего */}
                  {stateInfo.progress != null && (
                    <div className="mt-1.5 h-1 bg-zinc-200/60 rounded-full overflow-hidden">
                      <div
                        className="h-full gradient-primary transition-all"
                        style={{ width: `${stateInfo.progress * 100}%` }}
                      />
                    </div>
                  )}
                  {m.error && (
                    <div className="mt-1 text-[11px] text-rose-600">
                      Ошибка: {m.error}
                    </div>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="mt-4 flex gap-2 flex-wrap">
        {botUsername && (
          <a href={`https://t.me/${botUsername}`} target="_blank" rel="noreferrer">
            <Button>📱 Открыть Telegram</Button>
          </a>
        )}
        <Button variant="ghost" onClick={() => setStopped(true)} disabled={stopped}>
          ⏸ Прервать тест
        </Button>
      </div>

      <div className="mt-3 text-[11px] text-zinc-500">
        💡 Если сообщения не приходят — у вашего админ-аккаунта в системе нет привязки к
        Telegram. Зайдите в бота из-под нужного аккаунта и нажмите /start — система запомнит.
      </div>
    </div>
  );
}


function getStateInfo(m: TestMessage, now: number) {
  if (m.sent_at) {
    const ago = Math.max(0, Math.floor((now - new Date(m.sent_at).getTime()) / 1000));
    return {
      icon: '✅',
      label: `Отправлен ${ago} сек назад`,
      bg: 'bg-emerald-50/60 border-emerald-200/60',
      progress: null as number | null,
    };
  }
  if (m.cancelled_at) {
    return {
      icon: '⏹',
      label: 'Отменён',
      bg: 'bg-zinc-50/60 border-zinc-200/60',
      progress: null as number | null,
    };
  }
  if (m.error) {
    return {
      icon: '❌',
      label: 'Ошибка отправки',
      bg: 'bg-rose-50/60 border-rose-200/60',
      progress: null as number | null,
    };
  }
  // ожидание
  const scheduled = new Date(m.scheduled_at).getTime();
  const secsLeft = Math.max(0, Math.ceil((scheduled - now) / 1000));
  if (secsLeft === 0) {
    return {
      icon: '⏳',
      label: 'Отправляется…',
      bg: 'bg-indigo-50/60 border-indigo-200/60',
      progress: 1,
    };
  }
  return {
    icon: '⏳',
    label: `Отправится через ${secsLeft} сек`,
    bg: 'bg-white/60 border-zinc-200/40',
    progress: null,
  };
}

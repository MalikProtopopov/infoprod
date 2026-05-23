'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { Button, Field, Input, Pill, Select, Sheet } from '@/components/ui';
import { useToast } from '@/components/Toast';

type Link = {
  id: number;
  slug: string;
  utm_source: string;
  utm_medium: string | null;
  utm_campaign: string | null;
  click_count: number;
  unique_users: number;
};

type Trigger = { id: number; word: string; is_active: boolean; use_count: number };

type EntryPoints = {
  funnel_id: number;
  product_id: number;
  tracking_links: Link[];
  triggers: Trigger[];
  is_product_default: boolean;
  has_any: boolean;
};

type Bot = { id: number; username: string };

/**
 * §3 студии: primary (Trackable Link) + 2 secondary (Word, Default).
 * Все действия — inline-модалки без ухода со страницы.
 */
export function EntryPointsSection({
  funnelId,
  productId,
  productName,
  botUsername,
}: {
  funnelId: number;
  productId: number;
  productName?: string;
  botUsername?: string;
}) {
  const { data, mutate } = useSWR<EntryPoints>(
    `/funnels/${funnelId}/entry-points`,
    fetcher,
  );
  const { data: bots } = useSWR<Bot[]>('/bots', fetcher);
  const { showToast } = useToast();

  const [linkOpen, setLinkOpen] = useState(false);
  const [wordOpen, setWordOpen] = useState(false);

  async function copyLink(slug: string) {
    const url = botUsername
      ? `https://t.me/${botUsername}?start=${slug}`
      : `https://t.me/_?start=${slug}`;
    try {
      await navigator.clipboard?.writeText(url);
      showToast('Ссылка скопирована');
    } catch {
      showToast('Не удалось скопировать ссылку', { type: 'error' });
    }
  }

  async function makeDefault() {
    try {
      await api.patch(`/products/${productId}`, { default_funnel_id: funnelId });
      mutate();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  async function unmakeDefault() {
    if (!confirm('Убрать эту воронку как default для продукта?')) return;
    try {
      await api.patch(`/products/${productId}`, { default_funnel_id: null });
      mutate();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  if (!data) return <div className="text-sm text-zinc-500 py-4">Загрузка…</div>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3">
      {/* PRIMARY: Trackable Link */}
      <div className="glass rounded-2xl p-4 sm:p-5">
        <div className="flex items-start gap-3 mb-3">
          <div className="text-2xl shrink-0">🔗</div>
          <div className="flex-1 min-w-0">
            <h4 className="font-semibold text-base">Trackable Link <span className="text-xs text-indigo-600 font-medium">(рекомендуется)</span></h4>
            <p className="text-xs text-zinc-600 mt-0.5 leading-snug">
              Прикрепите эту ссылку под постом про <b>{productName || 'продукт'}</b>. Все, кто кликнет — попадут в воронку.
              Можно создать отдельную ссылку под каждый канал (Reels / Stories / посты) — увидим в /sources, что лучше работает.
            </p>
          </div>
        </div>

        {data.tracking_links.length > 0 ? (
          <div className="space-y-1.5 mb-3">
            <div className="text-xs text-zinc-500 mb-1">✅ {data.tracking_links.length} активных ссылок:</div>
            {data.tracking_links.map((l) => (
              <div key={l.id} className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-white/50">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-mono truncate">{l.slug}</div>
                  <div className="text-[11px] text-zinc-500 truncate">
                    {l.utm_source}{l.utm_medium && ` / ${l.utm_medium}`}{l.utm_campaign && ` · ${l.utm_campaign}`}
                  </div>
                </div>
                <div className="text-xs text-zinc-500 text-right shrink-0">
                  <div>{l.click_count} кликов</div>
                  <div className="text-[10px]">{l.unique_users} уник.</div>
                </div>
                <button
                  type="button"
                  onClick={() => copyLink(l.slug)}
                  className="shrink-0 inline-flex items-center justify-center size-8 rounded-lg text-indigo-600 hover:bg-indigo-50 transition"
                  title="Скопировать ссылку"
                  aria-label="Скопировать ссылку"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <rect x="9" y="9" width="13" height="13" rx="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-zinc-500 mb-3 px-3 py-2 border border-dashed border-zinc-300 rounded-lg">
            Пока ни одной trackable-ссылки. Добавьте — это самый частый способ запуска воронки.
          </div>
        )}

        <Button onClick={() => setLinkOpen(true)} size="md">
          + Новая ссылка
        </Button>
      </div>

      {/* SECONDARY: Word + Default */}
      <div className="space-y-3">
        {/* Кодовое слово */}
        <div className="glass rounded-2xl p-4">
          <div className="flex items-start gap-2 mb-2">
            <div className="text-xl shrink-0">💬</div>
            <div className="flex-1 min-w-0">
              <h4 className="font-semibold text-sm">Кодовое слово</h4>
              <p className="text-[11px] text-zinc-500 leading-snug">
                Скажите в видео: «Напишите боту КЛУБ». Работает в подкастах и эфирах без активной ссылки.
              </p>
            </div>
          </div>
          {data.triggers.length > 0 ? (
            <div className="space-y-1.5 mb-2">
              {data.triggers.map((t) => (
                <div key={t.id} className="flex items-center justify-between gap-2">
                  <code className="px-2 py-0.5 bg-violet-100/60 text-violet-700 rounded text-xs">{t.word}</code>
                  <span className="text-[11px] text-zinc-500">{t.use_count} раз</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[11px] text-zinc-400 mb-2">Слов пока нет</div>
          )}
          <Button onClick={() => setWordOpen(true)} size="sm" variant="ghost">
            + Добавить слово
          </Button>
        </div>

        {/* Default funnel */}
        <div className="glass rounded-2xl p-4">
          <div className="flex items-start gap-2 mb-2">
            <div className="text-xl shrink-0">📋</div>
            <div className="flex-1 min-w-0">
              <h4 className="font-semibold text-sm">Default для заявок</h4>
              <p className="text-[11px] text-zinc-500 leading-snug">
                Когда пользователь нажмёт «Оставить заявку» на этот продукт — мы автоматически начнём
                слать ему follow-up. Включите, если менеджер не успевает обрабатывать заявки моментально.
              </p>
            </div>
          </div>
          {data.is_product_default ? (
            <div className="space-y-1.5">
              <Pill color="green">✓ Подключено</Pill>
              <button
                type="button"
                onClick={unmakeDefault}
                className="block text-[11px] text-zinc-500 hover:text-rose-600 underline"
              >
                Убрать
              </button>
            </div>
          ) : (
            <Button onClick={makeDefault} size="sm" variant="ghost">
              Сделать default
            </Button>
          )}
        </div>
      </div>

      {/* Sheets */}
      <NewLinkSheet
        open={linkOpen}
        onClose={() => setLinkOpen(false)}
        funnelId={funnelId}
        productId={productId}
        botUsername={botUsername}
        onCreated={() => mutate()}
      />
      <NewTriggerSheet
        open={wordOpen}
        onClose={() => setWordOpen(false)}
        funnelId={funnelId}
        onCreated={() => mutate()}
      />
    </div>
  );
}


function NewLinkSheet({
  open, onClose, funnelId, productId, botUsername, onCreated,
}: {
  open: boolean;
  onClose: () => void;
  funnelId: number;
  productId: number;
  botUsername?: string;
  onCreated: () => void;
}) {
  const [utm_source, setSource] = useState('');
  const [utm_medium, setMedium] = useState('');
  const [utm_campaign, setCampaign] = useState('');
  const [created, setCreated] = useState<{ slug: string; url: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { showToast } = useToast();

  const MEDIUMS = ['reels', 'post', 'story', 'video', 'email', 'другое'];

  async function create() {
    if (!utm_source.trim()) return;
    setBusy(true); setError(null);
    try {
      const body: Record<string, unknown> = {
        product_id: productId,
        funnel_id: funnelId,
        utm_source: utm_source.trim(),
      };
      if (utm_medium) body.utm_medium = utm_medium;
      if (utm_campaign) body.utm_campaign = utm_campaign;
      const link = await api.post<{ slug: string; url: string }>('/tracking-links', body);
      setCreated(link);
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  function reset() {
    setSource(''); setMedium(''); setCampaign(''); setCreated(null); setError(null);
  }

  return (
    <Sheet
      open={open}
      onClose={() => { reset(); onClose(); }}
      title={created ? 'Ссылка готова' : 'Новая trackable-ссылка'}
      description={created ? 'Скопируйте и используйте в посте' : 'Каждая ссылка — отдельный UTM-канал в /sources'}
      footer={
        created ? (
          <Button onClick={() => { reset(); onClose(); }}>Закрыть</Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>Отмена</Button>
            <Button onClick={create} disabled={busy || !utm_source.trim()}>
              {busy ? 'Создаём…' : 'Создать'}
            </Button>
          </>
        )
      }
    >
      {created ? (
        <div className="space-y-3">
          <Field label="URL">
            <Input value={created.url} readOnly className="font-mono text-xs" />
          </Field>
          <Button
            onClick={async () => {
              try {
                await navigator.clipboard?.writeText(created.url);
                showToast('Ссылка скопирована');
              } catch {
                showToast('Не удалось скопировать ссылку', { type: 'error' });
              }
            }}
            className="w-full"
          >
            📋 Скопировать ссылку
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="Источник (utm_source)" required hint="instagram, youtube, tg_chat_marketing">
            <Input value={utm_source} onChange={(e) => setSource(e.target.value)} placeholder="instagram" autoFocus />
          </Field>
          <Field label="Канал (utm_medium)" hint="reels / post / stories — для отчёта в /sources">
            <Select value={utm_medium} onChange={(e) => setMedium(e.target.value)}>
              <option value="">— не указан —</option>
              {MEDIUMS.map((m) => <option key={m} value={m}>{m}</option>)}
            </Select>
          </Field>
          <Field label="Кампания (utm_campaign)">
            <Input value={utm_campaign} onChange={(e) => setCampaign(e.target.value)} placeholder="spring_2026, launch_day_1" />
          </Field>
          {error && (
            <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>
          )}
        </div>
      )}
    </Sheet>
  );
}


function NewTriggerSheet({
  open, onClose, funnelId, onCreated,
}: {
  open: boolean;
  onClose: () => void;
  funnelId: number;
  onCreated: () => void;
}) {
  const [word, setWord] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!word.trim()) return;
    setBusy(true); setError(null);
    try {
      await api.post('/funnel-triggers', { word: word.trim(), funnel_id: funnelId });
      onCreated();
      onClose();
      setWord(''); setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  return (
    <Sheet
      open={open}
      onClose={() => { setWord(''); setError(null); onClose(); }}
      title="Кодовое слово"
      description="Короткое слово без пробелов. Регистр не важен."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button onClick={create} disabled={busy || !word.trim()}>
            {busy ? 'Создаём…' : 'Создать'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Слово" required hint="Например: КЛУБ, ОБУЧЕНИЕ, СТАРТ">
          <Input value={word} onChange={(e) => setWord(e.target.value)} placeholder="старт" autoFocus />
        </Field>
        {error && (
          <div className="text-sm text-rose-600 bg-rose-50/80 border border-rose-200/60 rounded-xl px-3 py-2">{error}</div>
        )}
      </div>
    </Sheet>
  );
}

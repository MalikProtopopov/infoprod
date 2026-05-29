'use client';

import Link from 'next/link';
import { useState } from 'react';
import useSWR from 'swr';

import { api, fetcher } from '@/lib/api';
import { Button, Card, PageHeader, Pill } from '@/components/ui';
import { FunnelWizard } from '@/components/FunnelWizard';

type Funnel = {
  id: number;
  name: string;
  description: string | null;
  product_id: number;
  bot_id: number | null;
  is_active: boolean;
  ttl_days: number;
  cancel_on_payment: boolean;
  steps_count: number;
  active_entries: number;
  completed_entries: number;
};

type Product = { id: number; name: string; code: string };

type EntryStatus = 'green' | 'yellow' | 'red' | 'gray';

function statusOf(f: Funnel, hasAny: boolean): EntryStatus {
  if (f.is_active && hasAny && f.steps_count > 0) return 'green';
  if (f.steps_count === 0 || !hasAny) return 'yellow';
  if (!f.is_active) return 'gray';
  return 'red';
}

function statusLabel(s: EntryStatus): string {
  return { green: 'Активна', yellow: 'Не запущена', red: 'Ошибка', gray: 'Черновик' }[s];
}


export default function FunnelsHubPage() {
  const { data, mutate, isLoading } = useSWR<Funnel[]>('/funnels', fetcher);
  const { data: products } = useSWR<Product[]>('/products', fetcher);
  const [wizardOpen, setWizardOpen] = useState(false);

  async function remove(f: Funnel) {
    if (!confirm(`Удалить воронку "${f.name}"?`)) return;
    try { await api.del(`/funnels/${f.id}`); mutate(); }
    catch (e) { alert(e instanceof Error ? e.message : String(e)); }
  }

  const stats = (data || []).reduce(
    (acc, f) => {
      if (f.is_active && f.steps_count > 0) acc.active++;
      else if (f.steps_count === 0) acc.draft++;
      else acc.todo++;
      return acc;
    },
    { active: 0, draft: 0, todo: 0 },
  );

  const hasProducts = (products?.length || 0) > 0;

  return (
    <div>
      <PageHeader
        title="Воронки"
        subtitle={
          data && data.length > 0
            ? `${stats.active} активных · ${stats.draft} черновиков · ${stats.todo} требуют настройки`
            : 'Цепочки follow-up сообщений с лидмагнитами, прерываемые при оплате'
        }
        action={
          hasProducts ? (
            <Button onClick={() => setWizardOpen(true)}>+ Создать новую воронку</Button>
          ) : null
        }
      />

      {!hasProducts && !isLoading && products !== undefined && (
        <Card padded className="text-center py-10">
          <div className="text-4xl mb-3">🎯</div>
          <h3 className="text-lg font-semibold mb-2">Воронки прогревают будущих клиентов</h3>
          <p className="text-sm text-zinc-600 mb-5 max-w-md mx-auto">
            Серии follow-up сообщений с лидмагнитами, прерываемые при оплате продукта.
          </p>
          <div className="glass-soft rounded-2xl p-4 max-w-md mx-auto">
            <p className="text-sm mb-3">Чтобы создать воронку, сначала нужен продукт.</p>
            <Link href="/products?return=/funnels">
              <Button>→ Создать первый продукт</Button>
            </Link>
            <p className="mt-3 text-xs text-zinc-500">
              После создания продукта вы вернётесь сюда с pre-selected продуктом в wizard'е.
            </p>
          </div>
        </Card>
      )}

      {hasProducts && (
        <>
          {isLoading && <div className="text-sm text-zinc-500 py-6">Загрузка…</div>}

          {!isLoading && data && data.length === 0 && (
            <Card padded className="text-center py-10">
              <div className="text-4xl mb-3">🎯</div>
              <h3 className="text-lg font-semibold mb-2">Воронок пока нет</h3>
              <p className="text-sm text-zinc-600 mb-5 max-w-md mx-auto">
                Создайте первую — wizard за 4 шага соберёт основу из готового шаблона.
              </p>
              <Button onClick={() => setWizardOpen(true)}>+ Создать первую воронку</Button>
            </Card>
          )}

          {data && data.length > 0 && (
            <div className="space-y-3">
              {data.map((f) => (
                <FunnelCard
                  key={f.id}
                  funnel={f}
                  productName={products?.find((p) => p.id === f.product_id)?.name}
                  onDelete={() => remove(f)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {wizardOpen && (
        <FunnelWizard
          onClose={() => setWizardOpen(false)}
          onCreated={() => { setWizardOpen(false); mutate(); }}
        />
      )}
    </div>
  );
}


function FunnelCard({ funnel, productName, onDelete }: {
  funnel: Funnel;
  productName?: string;
  onDelete: () => void;
}) {
  const { data: ep } = useSWR<{
    has_any: boolean;
    tracking_links: unknown[];
    triggers: unknown[];
    is_product_default: boolean;
  }>(`/funnels/${funnel.id}/entry-points`, fetcher);
  const hasAny = ep?.has_any ?? false;
  const status = statusOf(funnel, hasAny);

  const colorBar = {
    green: 'bg-emerald-500',
    yellow: 'bg-amber-500',
    red: 'bg-rose-500',
    gray: 'bg-zinc-400',
  }[status];

  const statusIcon = { green: '🟢', yellow: '🟡', red: '🔴', gray: '⚫' }[status];

  const missing: string[] = [];
  if (funnel.steps_count === 0) missing.push('шаги');
  if (ep && !ep.has_any) missing.push('точки входа');
  if (!funnel.is_active && funnel.steps_count > 0 && hasAny) missing.push('активация');

  const linksCount = ep?.tracking_links.length || 0;
  const triggersCount = ep?.triggers.length || 0;
  const isDefault = ep?.is_product_default || false;

  return (
    <Card padded className="anim-rise relative overflow-hidden">
      <div className={`absolute top-0 left-0 bottom-0 w-1 ${colorBar}`} />

      <div className="flex items-start justify-between gap-3 flex-wrap pl-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-base">{statusIcon}</span>
            <Link href={`/funnels/${funnel.id}/edit`} className="font-semibold text-base hover:text-indigo-600 transition">
              {funnel.name}
            </Link>
            <Pill color={status === 'green' ? 'green' : status === 'yellow' ? 'amber' : 'gray'}>
              {statusLabel(status)}
            </Pill>
            {funnel.active_entries > 0 && (
              <span className="text-xs text-zinc-500">· {funnel.active_entries} в воронке</span>
            )}
          </div>

          <div className="text-xs text-zinc-500 mt-1 truncate">
            {productName && <>Продукт: <b>{productName}</b></>}
            <span> · {funnel.steps_count} {funnel.steps_count === 1 ? 'шаг' : 'шагов'}</span>
            <span> · TTL {funnel.ttl_days} дн.</span>
          </div>

          {ep && ep.has_any && (
            <div className="text-xs text-zinc-600 mt-2 flex flex-wrap items-center gap-2">
              <span className="text-zinc-400">Входы:</span>
              {linksCount > 0 && (
                <span className="inline-flex items-center gap-1">
                  🔗 <b>{linksCount}</b> {linksCount === 1 ? 'ссылка' : 'ссылок'}
                </span>
              )}
              {triggersCount > 0 && (
                <span className="inline-flex items-center gap-1">
                  💬 <b>{triggersCount}</b> {triggersCount === 1 ? 'слово' : 'слов'}
                </span>
              )}
              {isDefault && <span className="inline-flex items-center gap-1">📋 default</span>}
            </div>
          )}

          {missing.length > 0 && (
            <div className="text-xs text-amber-700 mt-2">
              ❗ Не настроено: {missing.join(', ')}
            </div>
          )}

          {funnel.completed_entries > 0 && (
            <div className="text-xs text-zinc-500 mt-1">
              Завершено: <b>{funnel.completed_entries}</b>
            </div>
          )}
        </div>

        <div className="flex gap-1.5 flex-wrap">
          {missing.length > 0 ? (
            <Link
              href={`/funnels/${funnel.id}/edit${missing[0] === 'шаги' ? '#s2' : missing[0] === 'точки входа' ? '#s3' : '#s4'}`}
            >
              <Button size="sm">Завершить настройку →</Button>
            </Link>
          ) : (
            <Link href={`/funnels/${funnel.id}/edit`}>
              <Button size="sm" variant="ghost">Открыть студию ↗</Button>
            </Link>
          )}
          <Link href={`/funnels/${funnel.id}/entries`}>
            <Button size="sm" variant="ghost">Подписчики</Button>
          </Link>
          <Button size="sm" variant="danger" onClick={onDelete}>×</Button>
        </div>
      </div>
    </Card>
  );
}

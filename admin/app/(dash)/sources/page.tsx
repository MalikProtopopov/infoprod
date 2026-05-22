'use client';

import { useMemo, useState } from 'react';
import useSWR from 'swr';
import clsx from 'clsx';

import { fetcher } from '@/lib/api';
import {
  Card, Empty, PageHeader, Pill, Select, TableHead, TableWrap, Td, Th, Tr,
} from '@/components/ui';

type Row = {
  source?: string | null;
  campaign?: string | null;
  medium?: string | null;
  slug?: string | null;
  tracking_link_id?: number | null;
  clicks: number;
  unique_users: number;
  leads: number;
  payments: number;
  revenue: string;
  conv_click_to_lead: number;
  conv_lead_to_payment: number;
  avg_check: number;
};

type Resp = {
  from: string;
  to: string;
  group_by: string;
  rows: Row[];
  totals: { clicks: number; unique_users: number; leads: number; payments: number; revenue: string };
};

type Period = 'today' | '7d' | '30d' | '90d';
const PERIODS: Array<{ key: Period; label: string }> = [
  { key: 'today', label: 'Сегодня' },
  { key: '7d',    label: '7 дней' },
  { key: '30d',   label: '30 дней' },
  { key: '90d',   label: '90 дней' },
];

type Group = 'source' | 'campaign' | 'link';
const GROUPS: Array<{ key: Group; label: string }> = [
  { key: 'source',   label: 'По источнику' },
  { key: 'campaign', label: 'По кампании' },
  { key: 'link',     label: 'По ссылке' },
];

function periodRange(p: Period): { from: string; to: string } {
  const now = new Date();
  const to = now.toISOString();
  let from = new Date(now);
  if (p === 'today') {
    from.setHours(0, 0, 0, 0);
  } else if (p === '7d') {
    from.setDate(from.getDate() - 7);
  } else if (p === '30d') {
    from.setDate(from.getDate() - 30);
  } else {
    from.setDate(from.getDate() - 90);
  }
  return { from: from.toISOString(), to };
}

type Product = { id: number; name: string };

export default function SourcesPage() {
  const [period, setPeriod] = useState<Period>('30d');
  const [group, setGroup] = useState<Group>('source');
  const [productId, setProductId] = useState<number | ''>('');
  const [sortKey, setSortKey] = useState<keyof Row>('revenue');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  // Фиксируем from/to только при смене фильтров — иначе каждый рендер давал бы
  // новые миллисекунды, SWR ловил бы новый ключ и зацикливался.
  const swrKey = useMemo(() => {
    const { from, to } = periodRange(period);
    const params = new URLSearchParams({ from, to, group_by: group });
    if (productId) params.set('product_id', String(productId));
    return `/stats/sources?${params}`;
  }, [period, group, productId]);

  const { data, isLoading } = useSWR<Resp>(swrKey, fetcher, {
    revalidateOnFocus: false,
    revalidateIfStale: false,
    dedupingInterval: 60_000,
  });
  const { data: products } = useSWR<Product[]>('/products', fetcher);

  const rows = useMemo(() => {
    if (!data) return [];
    const r = [...data.rows];
    r.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      const an = typeof av === 'number' ? av : Number(av ?? 0);
      const bn = typeof bv === 'number' ? bv : Number(bv ?? 0);
      return sortDir === 'desc' ? bn - an : an - bn;
    });
    return r;
  }, [data, sortKey, sortDir]);

  function toggleSort(k: keyof Row) {
    if (sortKey === k) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else { setSortKey(k); setSortDir('desc'); }
  }

  function downloadCsv() {
    if (!data) return;
    const headers = ['key', 'clicks', 'unique', 'leads', 'payments', 'revenue', 'conv_c_to_l', 'conv_l_to_p', 'avg_check'];
    const lines = [headers.join(',')];
    for (const r of rows) {
      const key = group === 'link' ? (r.slug ?? '—')
                : group === 'campaign' ? `${r.source ?? '—'} / ${r.campaign ?? '—'}`
                : (r.source ?? '—');
      lines.push([
        JSON.stringify(key),
        r.clicks, r.unique_users, r.leads, r.payments, r.revenue,
        r.conv_click_to_lead.toFixed(4), r.conv_lead_to_payment.toFixed(4), r.avg_check.toFixed(2),
      ].join(','));
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sources_${period}_${group}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <PageHeader title="Источники" subtitle="Куда заливать рекламу — что приводит клиентов" />

      {/* Фильтры */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5 flex-wrap">
        <div className="inline-flex glass rounded-2xl p-1.5">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={clsx(
                'px-3 sm:px-4 h-9 rounded-xl text-sm transition',
                period === p.key ? 'bg-white shadow-soft text-ink' : 'text-zinc-600 hover:text-ink hover:bg-white/60',
              )}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="inline-flex glass rounded-2xl p-1.5">
          {GROUPS.map((g) => (
            <button
              key={g.key}
              onClick={() => setGroup(g.key)}
              className={clsx(
                'px-3 sm:px-4 h-9 rounded-xl text-sm transition',
                group === g.key ? 'bg-white shadow-soft text-ink' : 'text-zinc-600 hover:text-ink hover:bg-white/60',
              )}
            >
              {g.label}
            </button>
          ))}
        </div>

        <Select
          value={productId}
          onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}
          className="!w-auto"
        >
          <option value="">Все продукты</option>
          {(products || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </Select>

        <button
          onClick={downloadCsv}
          className="inline-flex items-center gap-2 px-4 h-10 rounded-xl glass-soft text-sm hover:bg-white/80 transition"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Экспорт CSV
        </button>
      </div>

      {/* Totals */}
      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
          <Totals label="Клики" value={data.totals.clicks} />
          <Totals label="Уник. юзеров" value={data.totals.unique_users} />
          <Totals label="Заявок" value={data.totals.leads} />
          <Totals label="Оплат" value={data.totals.payments} />
          <Totals
            label="Выручка"
            value={Number(data.totals.revenue).toLocaleString('ru-RU') + ' ₽'}
          />
        </div>
      )}

      {/* Таблица */}
      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && rows.length === 0 && <Empty>Нет данных за выбранный период</Empty>}
        {rows.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[940px]">
              <TableHead>
                <Th>{group === 'link' ? 'Slug' : group === 'campaign' ? 'Источник / Кампания' : 'Источник'}</Th>
                {group === 'link' && <Th>Источник</Th>}
                <SortableTh label="Клики" k="clicks" sortKey={sortKey} dir={sortDir} onClick={() => toggleSort('clicks')} />
                <SortableTh label="Уник." k="unique_users" sortKey={sortKey} dir={sortDir} onClick={() => toggleSort('unique_users')} />
                <SortableTh label="Заявок" k="leads" sortKey={sortKey} dir={sortDir} onClick={() => toggleSort('leads')} />
                <SortableTh label="Оплат" k="payments" sortKey={sortKey} dir={sortDir} onClick={() => toggleSort('payments')} />
                <SortableTh label="Выручка" k="revenue" sortKey={sortKey} dir={sortDir} onClick={() => toggleSort('revenue')} />
                <Th>Клик→Заявка</Th>
                <Th>Заявка→Оплата</Th>
                <Th>Ср. чек</Th>
              </TableHead>
              <tbody>
                {rows.map((r, i) => (
                  <Tr key={i}>
                    <Td className="font-medium">
                      {group === 'link' ? (
                        <code className="text-xs">{r.slug ?? '—'}</code>
                      ) : group === 'campaign' ? (
                        <span>{r.source ?? '—'}{r.campaign && <span className="text-zinc-500"> / {r.campaign}</span>}</span>
                      ) : (
                        r.source ?? <Pill color="gray">органика</Pill>
                      )}
                    </Td>
                    {group === 'link' && (
                      <Td className="text-zinc-600">
                        {r.source ?? '—'}{r.medium && <span className="text-zinc-500"> / {r.medium}</span>}
                      </Td>
                    )}
                    <Td>{r.clicks.toLocaleString('ru-RU')}</Td>
                    <Td>{r.unique_users.toLocaleString('ru-RU')}</Td>
                    <Td>{r.leads.toLocaleString('ru-RU')}</Td>
                    <Td>{r.payments.toLocaleString('ru-RU')}</Td>
                    <Td className="font-semibold">{Number(r.revenue).toLocaleString('ru-RU')}</Td>
                    <Td className="text-zinc-600">{(r.conv_click_to_lead * 100).toFixed(1)}%</Td>
                    <Td className="text-zinc-600">{(r.conv_lead_to_payment * 100).toFixed(1)}%</Td>
                    <Td className="text-zinc-600">{r.avg_check.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}</Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}

function Totals({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="glass rounded-2xl px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-zinc-500 font-medium">{label}</div>
      <div className="text-xl font-bold tracking-tight text-ink mt-0.5">
        {typeof value === 'number' ? value.toLocaleString('ru-RU') : value}
      </div>
    </div>
  );
}

function SortableTh({
  label, k, sortKey, dir, onClick,
}: { label: string; k: keyof Row; sortKey: keyof Row; dir: 'asc' | 'desc'; onClick: () => void }) {
  const active = sortKey === k;
  return (
    <th className="px-4 py-3 font-medium cursor-pointer select-none" onClick={onClick}>
      <span className="inline-flex items-center gap-1 hover:text-ink transition">
        {label}
        {active && <span className="text-indigo-500">{dir === 'desc' ? '↓' : '↑'}</span>}
      </span>
    </th>
  );
}

'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { fetcher } from '@/lib/api';
import { Card, Empty, PageHeader, Pill, Select, TableHead, TableWrap, Td, Th, Tr } from '@/components/ui';

type AuditEntry = {
  id: number;
  admin_id: number | null;
  action: string;
  resource_type: string;
  resource_id: number | null;
  method: string | null;
  path: string | null;
  summary: string | null;
  ip: string | null;
  user_agent: string | null;
  payload: unknown;
  created_at: string;
};

type Resp = { total: number; items: AuditEntry[] };

const ACTION_COLORS: Record<string, 'green' | 'amber' | 'red' | 'gray' | 'indigo' | 'violet'> = {
  create: 'green',
  update: 'indigo',
  delete: 'red',
  login: 'gray',
  logout: 'gray',
  gdpr_export: 'amber',
  gdpr_forget: 'red',
  feature_request: 'violet',
};

export default function AuditLogPage() {
  const [resourceType, setResourceType] = useState('');
  const [action, setAction] = useState('');
  const query = [
    resourceType ? `resource_type=${resourceType}` : '',
    action ? `action=${action}` : '',
  ].filter(Boolean).join('&');
  const { data, isLoading } = useSWR<Resp>(`/audit-log${query ? '?' + query : ''}`, fetcher);

  return (
    <div>
      <PageHeader
        title="Аудит-журнал"
        subtitle="Все изменения в системе — кто, когда, что"
      />

      <Card padded className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[180px]">
            <div className="text-xs uppercase tracking-wide text-zinc-500 mb-1.5">Тип ресурса</div>
            <Select value={resourceType} onChange={(e) => setResourceType(e.target.value)}>
              <option value="">— все —</option>
              <option value="product">Продукт</option>
              <option value="bot">Бот</option>
              <option value="channel">Канал</option>
              <option value="payment">Платёж</option>
              <option value="user">Пользователь</option>
              <option value="funnel">Воронка</option>
              <option value="auth">Авторизация</option>
              <option value="feature_request">Feature request</option>
            </Select>
          </div>
          <div className="min-w-[180px]">
            <div className="text-xs uppercase tracking-wide text-zinc-500 mb-1.5">Действие</div>
            <Select value={action} onChange={(e) => setAction(e.target.value)}>
              <option value="">— все —</option>
              <option value="create">create</option>
              <option value="update">update</option>
              <option value="delete">delete</option>
              <option value="login">login</option>
              <option value="logout">logout</option>
              <option value="gdpr_export">gdpr_export</option>
              <option value="gdpr_forget">gdpr_forget</option>
              <option value="feature_request">feature_request</option>
            </Select>
          </div>
        </div>
      </Card>

      <Card>
        {isLoading && <div className="p-6 text-sm text-zinc-500">Загрузка…</div>}
        {!isLoading && (!data || data.items.length === 0) && (
          <Empty>Записей пока нет</Empty>
        )}
        {data && data.items.length > 0 && (
          <TableWrap>
            <table className="w-full text-sm min-w-[820px]">
              <TableHead>
                <Th>Время</Th>
                <Th>Действие</Th>
                <Th>Ресурс</Th>
                <Th>Описание</Th>
                <Th>IP</Th>
              </TableHead>
              <tbody>
                {data.items.map((e) => (
                  <Tr key={e.id}>
                    <Td className="text-xs text-zinc-500 whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString('ru-RU')}
                    </Td>
                    <Td>
                      <Pill color={ACTION_COLORS[e.action] || 'gray'}>{e.action}</Pill>
                    </Td>
                    <Td className="text-xs">
                      <span className="text-zinc-700 font-medium">{e.resource_type}</span>
                      {e.resource_id != null && (
                        <span className="text-zinc-500"> #{e.resource_id}</span>
                      )}
                    </Td>
                    <Td className="text-zinc-700 max-w-[400px]">
                      <span className="block truncate" title={e.summary || ''}>
                        {e.summary || (e.method && e.path ? `${e.method} ${e.path}` : '—')}
                      </span>
                    </Td>
                    <Td className="text-xs text-zinc-500 font-mono">{e.ip || '—'}</Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>

      <div className="mt-3 text-xs text-zinc-500">
        Показано последних {data?.items.length || 0} записей.
        Журнал ведётся для аудита изменений в системе и compliance-целей (GDPR).
      </div>
    </div>
  );
}

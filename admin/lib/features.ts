'use client';

import useSWR from 'swr';

import { fetcher } from '@/lib/api';

/**
 * Канонический список ключей фич. ДОЛЖЕН зеркалить backend
 * `app/core/features.py::FEATURE_REGISTRY`. Типизация `FeatureKey` даёт
 * compile-time защиту от опечаток и «мёртвых» ключей: любой `isOn('typo')`
 * или `feature: 'typo'` не пройдёт `tsc`.
 */
export const FEATURE_KEYS = [
  'leads',
  'monetization',
  'tracking_links',
  'analytics',
  'funnels',
  'funnel_triggers',
  'quizzes',
  'forms',
  'lead_magnets',
] as const;

export type FeatureKey = (typeof FEATURE_KEYS)[number];

export type Features = Record<string, boolean>;

/**
 * Маршрут (по префиксу) → фича. Прямой переход на страницу выключенной фичи
 * редиректит на «/». Ядровые страницы (/, /products, /channels, /bots, /users,
 * /account, /audit-log) здесь не указаны — они всегда доступны.
 */
export const ROUTE_FEATURE: ReadonlyArray<readonly [string, FeatureKey]> = [
  ['/leads', 'leads'],
  ['/payments', 'monetization'],
  ['/subscriptions', 'monetization'],
  ['/funnels', 'funnels'],
  ['/lead-magnets', 'lead_magnets'],
  ['/funnel-triggers', 'funnel_triggers'],
  ['/quizzes', 'quizzes'],
  ['/forms', 'forms'],
  ['/analytics', 'analytics'],
  ['/sources', 'analytics'],
];

export function featureForPath(pathname: string): FeatureKey | undefined {
  for (const [prefix, feature] of ROUTE_FEATURE) {
    if (pathname === prefix || pathname.startsWith(prefix + '/')) return feature;
  }
  return undefined;
}

type ConfigResponse = {
  features: Features;
  registry: { key: string; label: string; depends_on: string[] }[];
};

/**
 * Эффективный набор фичефлагов с бэка (/config/features).
 *
 * Гейтинг — в рантайме (не build-time), поэтому один и тот же образ админки
 * обслуживает всех клиентов; набор приходит из .env конкретного сервера.
 *
 * `isOn(key)` намеренно оптимистичен: пока конфиг не загружен ИЛИ эндпойнт
 * недоступен (старый бэкенд) — считаем фичу включённой, чтобы не мигать меню
 * и не ломать обратную совместимость. Жёсткое выключение (редирект со страницы)
 * срабатывает только когда мы ТОЧНО знаем, что фича выключена — см. `ready`.
 */
export function useFeatures() {
  const { data, error } = useSWR<ConfigResponse>('/config/features', fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 300_000,
  });

  const features = data?.features;
  const ready = data !== undefined || error !== undefined;

  const isOn = (key: FeatureKey): boolean => {
    if (!features) return true; // не загружено / ошибка → оптимистично включено
    return features[key] !== false; // неизвестный ключ → включён по умолчанию
  };

  /** Точно ли фича выключена (для редиректов): только при загруженном конфиге. */
  const isOff = (key: FeatureKey): boolean => !!features && features[key] === false;

  return { features: features ?? {}, ready, isOn, isOff };
}

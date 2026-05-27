import { describe, expect, it } from 'vitest';

import { FEATURE_KEYS, ROUTE_FEATURE, featureForPath } from '@/lib/features';

/**
 * Drift-guard: ключи фич на фронте должны оставаться согласованными.
 * FEATURE_KEYS обязан зеркалить backend FEATURE_REGISTRY — если бэк добавит/
 * переименует фичу, этот тест (и типизация FeatureKey) подсветят рассинхрон.
 */
describe('feature keys', () => {
  it('matches the canonical backend registry set', () => {
    expect([...FEATURE_KEYS].sort()).toEqual(
      [
        'analytics',
        'forms',
        'funnel_triggers',
        'funnels',
        'lead_magnets',
        'leads',
        'monetization',
        'quizzes',
        'tracking_links',
      ].sort(),
    );
  });

  it('has no duplicates', () => {
    expect(new Set(FEATURE_KEYS).size).toBe(FEATURE_KEYS.length);
  });

  it('every ROUTE_FEATURE target is a known feature key', () => {
    for (const [, feature] of ROUTE_FEATURE) {
      expect(FEATURE_KEYS).toContain(feature);
    }
  });
});

describe('featureForPath', () => {
  it('maps page prefixes (incl. nested) to features', () => {
    expect(featureForPath('/funnels')).toBe('funnels');
    expect(featureForPath('/funnels/12/edit')).toBe('funnels');
    expect(featureForPath('/payments')).toBe('monetization');
    expect(featureForPath('/sources')).toBe('analytics');
  });

  it('returns undefined for core/unmapped pages', () => {
    expect(featureForPath('/')).toBeUndefined();
    expect(featureForPath('/products')).toBeUndefined();
    expect(featureForPath('/users/5')).toBeUndefined();
  });
});

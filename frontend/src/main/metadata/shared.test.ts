import { describe, it, expect } from 'vitest';

import { formatMetadataDateTime, normaliseMedalPair, normaliseWeaponSlots } from './shared.ts';

describe('shared metadata utilities', () => {
  it('normaliseWeaponSlots は不足分を補い 4 要素へ揃える', () => {
    expect(normaliseWeaponSlots(['A', 'B'])).toEqual(['A', 'B', '', '']);
  });

  it('normaliseMedalPair は表彰数を 0 から 3 の範囲へ正規化する', () => {
    expect(normaliseMedalPair(2.9, 5)).toEqual({
      goldMedals: 2,
      silverMedals: 1,
    });
  });

  it('formatMetadataDateTime は ISO 風文字列を YYYY-MM-DD HH:mm:ss へ揃える', () => {
    expect(formatMetadataDateTime('2026-03-10T11:47:58.123')).toBe('2026-03-10 11:47:58');
  });
});

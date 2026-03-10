import assert from 'node:assert/strict';
import test from 'node:test';

import { formatMetadataDateTime, normaliseMedalPair, normaliseWeaponSlots } from './shared.ts';

test('normaliseWeaponSlots は不足分を補い 4 要素へ揃える', () => {
  assert.deepEqual(normaliseWeaponSlots(['A', 'B']), ['A', 'B', '', '']);
});

test('normaliseMedalPair は表彰数を 0 から 3 の範囲へ正規化する', () => {
  assert.deepEqual(normaliseMedalPair(2.9, 5), {
    goldMedals: 2,
    silverMedals: 1,
  });
});

test('formatMetadataDateTime は ISO 風文字列を YYYY-MM-DD HH:mm:ss へ揃える', () => {
  assert.equal(formatMetadataDateTime('2026-03-10T11:47:58.123'), '2026-03-10 11:47:58');
});

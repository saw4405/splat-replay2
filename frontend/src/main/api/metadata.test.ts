import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildMetadataOptionMap, clearMetadataOptionsCache, getMetadataOptions } from './metadata';

afterEach(() => {
  clearMetadataOptionsCache();
  vi.unstubAllGlobals();
});

describe('メタデータ選択肢', () => {
  it.each([undefined, [{ key: 'わかばシューター', label: 'わかばシューター' }]])(
    '武器選択肢を変換し、旧レスポンスでは空配列を使う: %j',
    async (weapons) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ weapons }))));
      const options = await getMetadataOptions();
      expect(options.weapons).toEqual(weapons ?? []);
      expect(buildMetadataOptionMap(options).weapons).toEqual(
        weapons ? { わかばシューター: 'わかばシューター' } : {}
      );
    }
  );
});

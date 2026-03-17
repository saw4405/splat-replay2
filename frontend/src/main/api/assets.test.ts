import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import { updateEditUploadProcessOptions } from './assets.ts';

describe('assets API', () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('updateEditUploadProcessOptions はレスポンスを camelCase に変換して返す', async () => {
    globalThis.fetch = async (input, init) => {
      expect(input).toBe('/api/process/edit-upload/options');
      expect(init?.method).toBe('PATCH');
      expect(JSON.parse(String(init?.body))).toEqual({
        sleep_after_upload: true,
      });

      return new Response(
        JSON.stringify({
          state: 'running',
          started_at: null,
          finished_at: null,
          error: null,
          sleep_after_upload_default: false,
          sleep_after_upload_effective: true,
          sleep_after_upload_overridden: true,
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    };

    const status = await updateEditUploadProcessOptions({
      sleepAfterUpload: true,
    });

    expect(status).toEqual({
      state: 'running',
      startedAt: null,
      finishedAt: null,
      error: null,
      sleepAfterUploadDefault: false,
      sleepAfterUploadEffective: true,
      sleepAfterUploadOverridden: true,
    });
  });

  it('updateEditUploadProcessOptions は detail を優先してエラー化する', async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ detail: '編集中ではありません' }), {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      });

    await expect(
      updateEditUploadProcessOptions({
        sleepAfterUpload: false,
      })
    ).rejects.toThrow('編集中ではありません');
  });
});

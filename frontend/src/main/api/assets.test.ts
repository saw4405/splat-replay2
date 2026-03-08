import assert from 'node:assert/strict';
import test from 'node:test';

import { updateEditUploadProcessOptions } from './assets.ts';

test('updateEditUploadProcessOptions はレスポンスを camelCase に変換して返す', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (input, init) => {
    assert.equal(input, '/api/process/edit-upload/options');
    assert.equal(init?.method, 'PATCH');
    assert.deepStrictEqual(JSON.parse(String(init?.body)), {
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

  try {
    const status = await updateEditUploadProcessOptions({
      sleepAfterUpload: true,
    });

    assert.deepStrictEqual(status, {
      state: 'running',
      startedAt: null,
      finishedAt: null,
      error: null,
      sleepAfterUploadDefault: false,
      sleepAfterUploadEffective: true,
      sleepAfterUploadOverridden: true,
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('updateEditUploadProcessOptions は detail を優先してエラー化する', async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: '編集中ではありません' }), {
      status: 409,
      headers: { 'Content-Type': 'application/json' },
    });

  try {
    await assert.rejects(
      () =>
        updateEditUploadProcessOptions({
          sleepAfterUpload: false,
        }),
      /編集中ではありません/
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

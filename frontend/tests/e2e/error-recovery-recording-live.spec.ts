/**
 * エラー回復 E2E テスト: 録画中前提
 *
 * 目的:
 * - 録画中 UI で起こるメタデータ取得・保存エラーからの回復を検証する
 * - 録画中前提のため replay 動画を使用する
 */

import { expect, test } from '@playwright/test';

import {
  ensureAutoRecordingEnabled,
  ensureLiveMetadataVisible,
  environment,
  gotoMain,
  prepareReplayAssetWithScenario,
  replayAssets,
  stopRecordingForTeardown,
  waitForRecordingLifecycle,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_200_000 : 600_000);

const e2eEnvironment = environment();
const firstAsset = replayAssets(e2eEnvironment)[0];
const liveRecordingBootstrapScenario = {
  replay_bootstrap: {
    phase: 'in_game',
    game_mode: 'BATTLE',
  },
};

test('エラー回復 - メタデータオプション読み込み失敗時も録画中 UI を使い続けられる', async ({
  page,
}) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, liveRecordingBootstrapScenario);

  await page.route('**/api/metadata/options', (route) => {
    route.abort('failed');
  });

  try {
    await gotoMain(page);
    await ensureAutoRecordingEnabled(page);
    await waitForRecordingLifecycle(page);
    await ensureLiveMetadataVisible(page);

    const killInput = page.getByLabel('キル数');
    await expect(killInput).toBeVisible();
    await killInput.fill('10');
    await expect(killInput).toHaveValue('10');
  } finally {
    await page.unroute('**/api/metadata/options');
    await stopRecordingForTeardown(page);
  }
});

test('エラー回復 - 録画中メタデータ保存失敗後に再試行できる', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, liveRecordingBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  const killInput = page.getByLabel('キル数');
  await killInput.fill('15');

  await page.route('**/api/recorder/metadata', (route) => {
    if (route.request().method() === 'PATCH') {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal Server Error' }),
      });
      return;
    }
    route.continue();
  });

  try {
    const saveButton = page.getByRole('button', { name: '保存' });
    await saveButton.click();

    const errorDialog = page.getByRole('dialog', { name: 'エラー' });
    await expect(errorDialog).toContainText('メタデータの保存に失敗しました', {
      timeout: 10_000,
    });
    await errorDialog.getByRole('button', { name: '閉じる' }).click();
    await expect(killInput).toHaveValue('15');

    await page.unroute('**/api/recorder/metadata');

    await saveButton.click();
    const completionDialog = page.getByRole('dialog', { name: '完了' });
    await expect(completionDialog).toContainText('メタデータを保存しました', {
      timeout: 10_000,
    });
    await completionDialog.getByRole('button', { name: '閉じる' }).click();
  } finally {
    await page.unroute('**/api/recorder/metadata').catch(() => undefined);
    await stopRecordingForTeardown(page);
  }
});

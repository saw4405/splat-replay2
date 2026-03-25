/**
 * エラー回復ワークフローE2Eテスト
 *
 * 責務：
 * - エラー発生時の UI の振る舞いとユーザーへのフィードバックを検証
 * - エラーダイアログの表示、リトライ、回復フローの確認
 * - ネットワークエラー、API エラー、バリデーションエラーへの対応
 *
 * 分類: workflow (E2E)
 */

import { expect, test } from '@playwright/test';

import {
  ensureAutoRecordingEnabled,
  ensureLiveMetadataVisible,
  environment,
  firstRecordedVideo,
  gotoMain,
  openRecordedVideos,
  prepareReplayAssetWithScenario,
  replayAssets,
  stopRecordingForTeardown,
  waitForRecordedVideoCount,
  waitForRecordedVideoReady,
  waitForRecordingLifecycle,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_200_000 : 600_000);

const e2eEnvironment = environment();

const firstAsset = replayAssets(e2eEnvironment)[0];
const recordedVideoBootstrapScenario = {
  replay_bootstrap: {
    phase: 'matching',
    game_mode: 'BATTLE',
  },
};
const liveRecordingBootstrapScenario = {
  replay_bootstrap: {
    phase: 'in_game',
    game_mode: 'BATTLE',
  },
};

test('エラー回復 - メタデータオプション読み込み失敗時の動作', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, liveRecordingBootstrapScenario);

  // メタデータオプションAPIをブロック
  await page.route('**/api/metadata/options', (route) => {
    route.abort('failed');
  });

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  // オプション読み込み失敗でもフォームは動作する（デフォルト表示）
  const killInput = page.getByLabel('キル数');
  await expect(killInput).toBeVisible();

  // 値を入力できることを確認
  await killInput.fill('10');
  await expect(killInput).toHaveValue('10');
  await stopRecordingForTeardown(page);

  console.log('メタデータオプション読み込み失敗時も基本動作が可能');

  // ルートのブロックを解除
  await page.unroute('**/api/metadata/options');
});

test('エラー回復 - メタデータ保存失敗時のエラーメッセージ', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, liveRecordingBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  // キル数を編集
  const killInput = page.getByLabel('キル数');
  await killInput.fill('15');

  // メタデータ保存APIを500エラーにする
  await page.route('**/api/recorder/metadata', (route) => {
    if (route.request().method() === 'PATCH') {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal Server Error' }),
      });
    } else {
      route.continue();
    }
  });

  // 保存ボタンをクリック
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  // エラーメッセージが表示されることを確認
  await expect(page.getByText('メタデータの保存に失敗しました')).toBeVisible({
    timeout: 10_000,
  });

  console.log('保存失敗時のエラーメッセージが正しく表示されました');

  // エラーダイアログを閉じる
  await page
    .getByRole('dialog', { name: 'エラー' })
    .getByRole('button', { name: '閉じる' })
    .click();

  // フォームはそのまま編集可能な状態を維持
  await expect(killInput).toHaveValue('15');

  // ルートのブロックを解除
  await page.unroute('**/api/recorder/metadata');

  // 再度保存を試みて成功することを確認
  await page.waitForTimeout(500);
  await saveButton.click();
  await expect(page.getByText('メタデータを保存しました')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('dialog', { name: '完了' }).getByRole('button', { name: '閉じる' }).click();
  await stopRecordingForTeardown(page);

  console.log('エラー回復後に再保存が成功しました');
});

test('エラー回復 - 録画済みメタデータ更新失敗', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, recordedVideoBootstrapScenario);

  // 録画を完了させる
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  const recordedVideo = await firstRecordedVideo(page);
  const editButton = recordedVideo.getByTestId('recorded-video-metadata-button');
  await editButton.click();

  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  // キル数を変更
  const killInput = page.getByLabel('キル数');
  await killInput.fill('50');

  // メタデータ更新APIを失敗させる
  let metadataUpdateRequestCount = 0;
  await page.route('**/api/assets/recorded/*/metadata', (route) => {
    if (route.request().method() === 'PATCH') {
      metadataUpdateRequestCount += 1;
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Failed to update metadata' }),
      });
    } else {
      route.continue();
    }
  });

  // 保存ボタンをクリック
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  await expect.poll(() => metadataUpdateRequestCount, { timeout: 10_000 }).toBe(1);
  await expect(page.getByText(/メタデータの保存に失敗しました:/)).toBeVisible({ timeout: 10_000 });
  const errorDialog = page.getByRole('dialog', { name: 'エラー' });
  await errorDialog.getByRole('button', { name: '閉じる' }).click();
  await expect(errorDialog).toBeHidden({ timeout: 10_000 });

  // ルートのブロックを解除
  await page.unroute('**/api/assets/recorded/*/metadata');

  // 正常系で再保存できることを確認
  await openRecordedVideos(page);
  const recordedVideoAfterError = await firstRecordedVideo(page);
  await recordedVideoAfterError.getByTestId('recorded-video-metadata-button').click();
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });
  await page.getByLabel('キル数').fill('50');
  await saveButton.click();
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });
});

test('エラー回復 - 録画済みリスト取得失敗', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, recordedVideoBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリスト取得APIを失敗させる
  let fetchRecordedRequestCount = 0;
  await page.route('**/api/assets/recorded', (route) => {
    fetchRecordedRequestCount += 1;
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Failed to fetch recorded videos' }),
    });
  });

  // データ再取得時に失敗させる
  await page.reload();
  await gotoMain(page);
  await expect.poll(() => fetchRecordedRequestCount, { timeout: 10_000 }).toBeGreaterThan(0);

  // 録画済みリストを開く
  await page.getByTestId('bottom-drawer-toggle').click();
  await expect(page.getByTestId('recorded-video-list')).toBeVisible();
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(0);
  await expect(page.getByText('録画済データはありません')).toBeVisible();

  // ルートのブロックを解除
  await page.unroute('**/api/assets/recorded');

  // ページ再読み込み後は保存済みデータが表示される
  await page.reload();
  await gotoMain(page);
  await page.getByTestId('bottom-drawer-toggle').click();
  await expect(page.getByTestId('recorded-video-list')).toBeVisible();
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(1, {
    timeout: 30_000,
  });
});

test('エラー回復 - 削除確認後のAPI失敗', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, recordedVideoBootstrapScenario);

  // 録画を完了させる
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  const recordedVideo = await firstRecordedVideo(page);

  // 削除APIを失敗させる
  await page.route('**/api/assets/recorded/*', (route) => {
    if (route.request().method() === 'DELETE') {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Failed to delete video' }),
      });
    } else {
      route.continue();
    }
  });

  // 削除ボタンをクリック
  const deleteButton = recordedVideo.locator('button[title="動画を削除"]');
  await deleteButton.click();

  // 確認ダイアログが表示される
  await expect(page.getByRole('dialog', { name: '確認' })).toBeVisible({ timeout: 10_000 });

  // 削除を確定
  const confirmButton = page
    .getByRole('dialog', { name: '確認' })
    .getByRole('button', { name: '削除' });
  await confirmButton.click();

  await expect(page.getByText(/動画の削除に失敗しました:/)).toBeVisible({ timeout: 10_000 });

  // ビデオが削除されていないことを確認
  await expect(recordedVideo).toBeVisible({ timeout: 10_000 });

  // 録画数が1のままであることを確認
  const countDisplay = page.getByTestId('recorded-count');
  await expect(countDisplay).toHaveText('1', { timeout: 10_000 });

  console.log('削除失敗時にビデオが保持されていることを確認しました');

  // ルートのブロックを解除
  await page.unroute('**/api/assets/recorded/*');
});

test('エラー回復 - ネットワーク切断シミュレーション', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, liveRecordingBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  // すべてのAPIをブロック（ネットワーク切断シミュレーション）
  await page.route('**/api/**', (route) => {
    route.abort('failed');
  });

  // キル数を編集
  const killInput = page.getByLabel('キル数');
  await killInput.fill('12');

  // 保存を試みる
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  await expect(page.getByText('メタデータの保存に失敗しました')).toBeVisible({
    timeout: 10_000,
  });
  await page
    .getByRole('dialog', { name: 'エラー' })
    .getByRole('button', { name: '閉じる' })
    .click();

  // ルートのブロックを解除（ネットワーク回復）
  await page.unroute('**/api/**');

  // 再度保存を試みて成功することを確認
  await page.waitForTimeout(500);
  await saveButton.click();

  // 成功メッセージが表示される（ネットワーク回復後）
  await expect(page.getByText('メタデータを保存しました')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('dialog', { name: '完了' }).getByRole('button', { name: '閉じる' }).click();
  await stopRecordingForTeardown(page);

  console.log('ネットワーク回復後に保存が成功しました');
});

test('エラー回復 - バリデーションエラーへの対応', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, recordedVideoBootstrapScenario);

  // 録画を完了させる
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  const recordedVideo = await firstRecordedVideo(page);
  const editButton = recordedVideo.getByTestId('recorded-video-metadata-button');
  await editButton.click();

  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  // 不正な値を入力（例: 負の数）
  const killInput = page.getByLabel('キル数');
  await killInput.fill('-5');

  // メタデータ更新APIをバリデーションエラーにする
  await page.route('**/api/assets/recorded/*/metadata', (route) => {
    if (route.request().method() === 'PATCH') {
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Validation Error',
          detail: 'Kill count must be non-negative',
        }),
      });
    } else {
      route.continue();
    }
  });

  // 保存を試みる
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  await expect(page.getByText(/メタデータの保存に失敗しました:/)).toBeVisible({ timeout: 10_000 });
  const errorDialog = page.getByRole('dialog', { name: 'エラー' });
  await errorDialog.getByRole('button', { name: '閉じる' }).click();
  await expect(errorDialog).toBeHidden({ timeout: 10_000 });

  // ルートのブロックを解除
  await page.unroute('**/api/assets/recorded/*/metadata');

  // 正しい値に修正
  await openRecordedVideos(page);
  const recordedVideoAfterError = await firstRecordedVideo(page);
  await recordedVideoAfterError.getByTestId('recorded-video-metadata-button').click();
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });
  await killInput.fill('10');

  // 再度保存を試みて成功することを確認
  await saveButton.click();

  // ダイアログが閉じることを確認
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  console.log('バリデーションエラー修正後に保存が成功しました');
});

test('エラー回復 - 設定保存失敗時のフィードバック', async ({ page }) => {
  prepareReplayAsset(e2eEnvironment, replayAssets(e2eEnvironment)[0]);

  await gotoMain(page);

  // 設定を開く
  await page.getByTestId('settings-button').click();
  await expect(page.getByRole('dialog', { name: '設定' })).toBeVisible({ timeout: 10_000 });

  // 設定保存APIを失敗させる
  let settingsSaveRequestCount = 0;
  await page.route('**/api/settings', (route) => {
    if (route.request().method() !== 'PUT') {
      route.continue();
      return;
    }
    settingsSaveRequestCount += 1;
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Failed to save settings' }),
    });
  });

  await page.getByTestId('settings-section-behavior').click();
  await expect(
    page.getByTestId('settings-field-behavior-behavior-edit_after_power_off')
  ).toBeVisible();

  // 保存ボタンをクリック
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();
  await expect.poll(() => settingsSaveRequestCount, { timeout: 10_000 }).toBe(1);
  await expect(page.getByText('Failed to save settings')).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.getByRole('dialog', { name: '設定' })).toBeVisible();

  // ルートのブロックを解除
  await page.unroute('**/api/settings');

  // ダイアログを閉じる
  const cancelButton = page.getByRole('button', { name: 'キャンセル' });
  await cancelButton.click();
});

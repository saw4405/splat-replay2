/**
 * 編集・アップロードワークフローE2Eテスト
 *
 * 責務：
 * - 録画完了後の編集・アップロードフローのエンドツーエンド検証
 * - 録画完了 → 編集・アップロード開始 → 進捗表示 → 完了
 * - POST /api/assets/process/edit-upload/start
 *
 * 分類: workflow (E2E)
 */

import { expect, test } from '@playwright/test';

import {
  environment,
  gotoMain,
  openRecordedVideos,
  prepareReplayAsset,
  replayAssets,
  waitForRecordedVideoCount,
  waitForRecordingLifecycle,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_800_000 : 900_000);

const e2eEnvironment = environment();

// 最初のreplay assetで編集・アップロードをテスト
const firstAsset = replayAssets(e2eEnvironment)[0];

// テストスイート開始時にYouTube権限ダイアログを表示済みにする
test.beforeAll(async ({ request }) => {
  await request.post('/api/settings/youtube-permission-dialog', {
    data: { shown: true },
  });
});

test('編集・アップロードワークフロー', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAsset(e2eEnvironment, firstAsset);

  // 1. 録画を完了させる
  await gotoMain(page);
  await waitForRecordingLifecycle(page);
  await waitForRecordedVideoCount(page, 1);

  // 2. 録画済みリストを開く
  await gotoMain(page);
  await openRecordedVideos(page);

  // 録画済み動画があることを確認
  await expect(page.getByTestId('recorded-count')).toHaveText('1', {
    timeout: 30_000,
  });

  // 3. 編集・アップロード開始ボタンをクリック
  const startButton = page.locator('button.process-button').filter({ hasText: '処理開始' });
  await expect(startButton).toBeVisible({ timeout: 30_000 });
  await expect(startButton).toBeEnabled();
  await startButton.click();

  // 4. 進捗ダイアログが開くことを確認
  const progressDialog = page.getByRole('dialog', { name: '進捗ダイアログ' });
  await expect(progressDialog).toBeVisible({ timeout: 30_000 });

  console.log('進捗ダイアログが開きました');

  // 5. 処理の進行を待機
  // 注意: 実装では、編集 → アップロードの順で処理されるが、
  // E2E環境ではYouTube APIがモックされているため、実際の処理時間は短い可能性がある

  // タスクリスト（自動編集 / 自動アップロード）が表示されることを確認
  await expect(progressDialog.getByText(/自動編集|自動アップロード/).first()).toBeVisible({
    timeout: 60_000,
  });

  console.log('編集・アップロードタスクの実行が確認されました');

  // 6. 完了状態を確認（成功バナーまたは完了メッセージ）
  // 最大10分待機（編集処理が重い場合を考慮）
  await expect(progressDialog.getByRole('status').filter({ hasText: /成功|完了/ })).toBeVisible({
    timeout: 600_000,
  });

  console.log('編集・アップロード処理が完了しました');

  // 7. ダイアログを閉じる
  // 注意: ダイアログが自動的に閉じる場合や、既に閉じている場合があるため、
  // エラーを無視して処理を継続する
  try {
    const closeButton = progressDialog.getByRole('button', { name: /閉じる|Close/ });
    if (await closeButton.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await closeButton.click();
      await expect(progressDialog).toBeHidden({ timeout: 5_000 });
    }
  } catch (error) {
    // ダイアログが既に閉じている場合はエラーを無視
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.log('ダイアログ閉じる処理をスキップ:', errorMessage);
  }

  console.log('編集・アップロードワークフローが成功しました');
});

test('編集・アップロードの重複起動防止', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAsset(e2eEnvironment, firstAsset);

  // 録画を完了させる
  await gotoMain(page);

  // 既に録画済みデータがあるかチェック（前のテストで録画済みの場合）
  const recordedVideosResponse = await page.request.get('/api/assets/recorded');
  const recordedVideos = (await recordedVideosResponse.json()) as Array<{ id: string }>;

  if (recordedVideos.length === 0) {
    // 録画が必要な場合のみ録画を待つ
    await waitForRecordingLifecycle(page);
    await waitForRecordedVideoCount(page, 1);
  } else {
    console.log(`既に${recordedVideos.length}件の録画済みデータがあります`);
  }

  await gotoMain(page);
  await openRecordedVideos(page);

  // 編集・アップロード開始
  const startButton = page.locator('button.process-button').filter({ hasText: '処理開始' });
  await expect(startButton).toBeVisible({ timeout: 30_000 });
  await startButton.click();

  // 進捗ダイアログが開く
  const progressDialog = page.getByRole('dialog', { name: '進捗ダイアログ' });
  await expect(progressDialog).toBeVisible({ timeout: 30_000 });

  // タスクが開始されたことを確認
  await expect(progressDialog.getByText(/自動編集|自動アップロード/).first()).toBeVisible({
    timeout: 30_000,
  });

  console.log('処理が開始されました');

  // Bottom Drawer に戻る（進捗ダイアログを閉じる）
  const closeButton = progressDialog.getByRole('button', { name: /閉じる|Close/ });
  await closeButton.click();
  await expect(progressDialog).toBeHidden({ timeout: 5_000 });

  // 処理開始ボタンが無効化されていることを確認
  // （処理実行中は再度実行できないはず）
  await expect(startButton).toBeDisabled();

  console.log('重複起動が防止されています（ボタンが無効化されている）');
});

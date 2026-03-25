/**
 * 録画中メタデータ編集ワークフローE2Eテスト
 *
 * 責務：
 * - 録画中にリアルタイムでメタデータを編集するエンドツーエンドフローを検証
 * - SSE経由の自動更新と手動編集の競合処理
 * - 手動編集後の保存と永続化
 *
 * 分類: workflow (E2E)
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
const autoRecordingBootstrapScenario = {
  replay_bootstrap: {
    phase: 'in_game',
    game_mode: 'BATTLE',
  },
};

// 録画中メタデータ編集のテストは、最初のreplay assetのみで実行
// （全assetで実行すると非常に時間がかかるため）
const firstAsset = replayAssets(e2eEnvironment)[0];

test('録画中メタデータ編集ワークフロー', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, autoRecordingBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  // 初期状態の確認: キル数が表示されている（自動認識の結果）
  const killInput = page.getByLabel('キル数');
  await expect(killInput).toBeVisible();

  // 現在のキル数を取得
  const initialKillValue = await killInput.inputValue();
  console.log('初期キル数:', initialKillValue);

  // キル数を手動で変更
  const newKillValue = '15';
  await killInput.fill(newKillValue);

  // 変更が反映されたことを確認
  await expect(killInput).toHaveValue(newKillValue);

  // デス数も変更
  const deathInput = page.getByLabel('デス数');
  const newDeathValue = '3';
  await deathInput.fill(newDeathValue);
  await expect(deathInput).toHaveValue(newDeathValue);

  // スペシャル数も変更
  const specialInput = page.getByLabel('スペシャル');
  const newSpecialValue = '2';
  await specialInput.fill(newSpecialValue);
  await expect(specialInput).toHaveValue(newSpecialValue);

  // 保存ボタンをクリック
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  // 成功メッセージが表示されることを確認
  await expect(page.getByText('メタデータを保存しました')).toBeVisible({ timeout: 10_000 });

  // ダイアログを閉じる
  await page.getByRole('dialog', { name: '完了' }).getByRole('button', { name: '閉じる' }).click();

  // 編集した値が保持されていることを確認
  await expect(killInput).toHaveValue(newKillValue);
  await expect(deathInput).toHaveValue(newDeathValue);
  await expect(specialInput).toHaveValue(newSpecialValue);
  await stopRecordingForTeardown(page);

  console.log('録画中メタデータ編集ワークフローが成功しました');
});

test('録画中メタデータ編集 - 現在時刻設定', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, autoRecordingBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  // 開始時間フィールドを確認
  const startedAtInput = page.getByLabel('開始時間');
  await expect(startedAtInput).toBeVisible();

  // 現在時刻を設定ボタンをクリック
  const setNowButton = page.getByText('現在時刻を設定');
  await setNowButton.click();

  // 開始日時が設定されたことを確認（YYYY-MM-DD HH:mm:ss 形式）
  const startedAtValue = await startedAtInput.inputValue();
  expect(startedAtValue).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);

  console.log('設定された開始日時:', startedAtValue);

  // 保存
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  // 成功メッセージ確認
  await expect(page.getByText('メタデータを保存しました')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('dialog', { name: '完了' }).getByRole('button', { name: '閉じる' }).click();
  await stopRecordingForTeardown(page);

  console.log('現在時刻設定ワークフローが成功しました');
});

test('録画中メタデータ編集 - リセット機能', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, autoRecordingBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  // キル数を変更
  const killInput = page.getByLabel('キル数');
  const initialValue = await killInput.inputValue();
  await killInput.fill('25');
  await expect(killInput).toHaveValue('25');

  // リセットボタンをクリック
  const resetButton = page.getByRole('button', { name: 'リセット' });
  await resetButton.click();

  // 手動編集がクリアされ、自動認識値に戻ることを待機
  // （リセット後はAPIから最新のメタデータが再取得される）
  await page.waitForTimeout(1000);

  // リセット後の値を確認（初期値または自動認識値に戻る）
  const resetValue = await killInput.inputValue();
  console.log('リセット前:', '25', 'リセット後:', resetValue);

  // 値が変更されたことを確認（25から変わっている）
  expect(resetValue).not.toBe('25');
  await stopRecordingForTeardown(page);

  console.log('リセット機能ワークフローが成功しました');
});

test('録画中メタデータ編集 - 選択フィールドの変更', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, autoRecordingBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  // ステージのselectフィールドを変更
  const stageSelect = page.getByLabel('ステージ');
  await expect(stageSelect).toBeVisible();

  // 現在の値を取得
  const initialStage = await stageSelect.inputValue();
  console.log('初期ステージ:', initialStage);

  // selectの選択肢を取得して、現在と異なる値を選択
  const options = await stageSelect.locator('option').all();
  let newStageValue: string | null = null;

  for (const option of options) {
    const value = await option.getAttribute('value');
    if (value && value !== initialStage && value !== '') {
      newStageValue = value;
      break;
    }
  }

  expect(newStageValue).not.toBeNull();
  await stageSelect.selectOption(newStageValue!);
  await expect(stageSelect).toHaveValue(newStageValue!);
  console.log('新しいステージ:', newStageValue);

  // 保存
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  // 成功メッセージ確認
  await expect(page.getByText('メタデータを保存しました')).toBeVisible({
    timeout: 10_000,
  });
  await page.getByRole('dialog', { name: '完了' }).getByRole('button', { name: '閉じる' }).click();

  // 値が保持されていることを確認
  await expect(stageSelect).toHaveValue(newStageValue!);
  await stopRecordingForTeardown(page);

  console.log('選択フィールド変更ワークフローが成功しました');
});

test('録画中メタデータ編集 - 保存前キャンセル', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAssetWithScenario(e2eEnvironment, firstAsset, autoRecordingBootstrapScenario);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await ensureLiveMetadataVisible(page);

  // キル数を変更
  const killInput = page.getByLabel('キル数');
  const initialValue = await killInput.inputValue();
  await killInput.fill('30');
  await expect(killInput).toHaveValue('30');

  // ページをリロード（保存せずにキャンセル相当）
  await page.reload();

  // 再度メタデータオーバーレイが表示されるのを待つ
  await ensureLiveMetadataVisible(page);

  // キル数が保存されていないことを確認（初期値または自動認識値に戻る）
  const reloadedValue = await page.getByLabel('キル数').inputValue();
  console.log('変更前:', initialValue, '変更後（未保存）:', '30', 'リロード後:', reloadedValue);

  // 未保存の値(30)ではないことを確認
  expect(reloadedValue).not.toBe('30');
  await stopRecordingForTeardown(page);

  console.log('保存前キャンセルワークフローが成功しました');
});

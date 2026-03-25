/**
 * 録画済みメタデータ編集ワークフローE2Eテスト
 *
 * 責務：
 * - 録画済み動画に対するメタデータ編集のエンドツーエンドフローを検証
 * - 録画済みリスト→編集ダイアログ→保存→リスト更新の一連の流れ
 * - PUT /api/assets/recorded/{id}/metadata
 *
 * 分類: workflow (E2E)
 */

import { expect, test } from '@playwright/test';

import {
  ensureAutoRecordingEnabled,
  environment,
  firstRecordedVideo,
  gotoMain,
  openRecordedVideos,
  prepareReplayAsset,
  replayAssets,
  waitForRecordedVideoReady,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_200_000 : 600_000);

const e2eEnvironment = environment();

// 録画済みメタデータ編集のテストは、最初のreplay assetのみで実行
const firstAsset = replayAssets(e2eEnvironment)[0];

test('録画済みメタデータ編集ワークフロー', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAsset(e2eEnvironment, firstAsset);

  // 録画を完了させる
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 最初の録画済み動画を取得
  const recordedVideo = await firstRecordedVideo(page);

  // 編集ボタンをクリック
  const editButton = recordedVideo.getByTestId('recorded-video-metadata-button');
  await expect(editButton).toBeVisible({ timeout: 30_000 });
  await editButton.click();

  // メタデータ編集ダイアログが開くのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  // キル数を変更
  const killInput = page.getByLabel('キル数');
  await expect(killInput).toBeVisible();
  const initialKillValue = await killInput.inputValue();
  console.log('初期キル数:', initialKillValue);

  const newKillValue = '20';
  await killInput.fill(newKillValue);
  await expect(killInput).toHaveValue(newKillValue);

  // デス数を変更
  const deathInput = page.getByLabel('デス数');
  const newDeathValue = '4';
  await deathInput.fill(newDeathValue);
  await expect(deathInput).toHaveValue(newDeathValue);

  // 保存ボタンをクリック
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  // ダイアログが閉じるのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  // 録画済みリストで値が更新されていることを確認
  await page.waitForTimeout(1000); // UIの更新を待つ

  const updatedRecordedVideo = await firstRecordedVideo(page);
  const displayedKill = await updatedRecordedVideo.getByTestId('recorded-video-kill').textContent();
  const displayedDeath = await updatedRecordedVideo
    .getByTestId('recorded-video-death')
    .textContent();

  expect(displayedKill?.trim()).toBe(newKillValue);
  expect(displayedDeath?.trim()).toBe(newDeathValue);

  console.log('録画済みメタデータ編集ワークフローが成功しました');
});

test('録画済みメタデータ編集 - キャンセル', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAsset(e2eEnvironment, firstAsset);

  // 録画を完了させる
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 最初の録画済み動画を取得
  const recordedVideo = await firstRecordedVideo(page);

  // 初期値を取得
  const initialKill = await recordedVideo.getByTestId('recorded-video-kill').textContent();
  console.log('初期キル数:', initialKill);

  // 編集ボタンをクリック
  const editButton = recordedVideo.getByTestId('recorded-video-metadata-button');
  await editButton.click();

  // メタデータ編集ダイアログが開くのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  // キル数を変更
  const killInput = page.getByLabel('キル数');
  await killInput.fill('99');
  await expect(killInput).toHaveValue('99');

  // キャンセルボタンをクリック
  const cancelButton = page.getByRole('button', { name: 'キャンセル' });
  await cancelButton.click();

  // ダイアログが閉じるのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  // リストの値が変更されていないことを確認
  const updatedRecordedVideo = await firstRecordedVideo(page);
  const displayedKill = await updatedRecordedVideo.getByTestId('recorded-video-kill').textContent();

  expect(displayedKill?.trim()).toBe(initialKill?.trim());
  expect(displayedKill?.trim()).not.toBe('99');

  console.log('キャンセルワークフローが成功しました');
});

test('録画済みメタデータ編集 - 選択フィールドの変更', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAsset(e2eEnvironment, firstAsset);

  // 録画を完了させる
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 最初の録画済み動画を取得
  const recordedVideo = await firstRecordedVideo(page);

  // 初期のルールを取得
  const initialRule = await recordedVideo.getByTestId('recorded-video-rule').textContent();
  console.log('初期ルール:', initialRule);

  // 編集ボタンをクリック
  const editButton = recordedVideo.getByTestId('recorded-video-metadata-button');
  await editButton.click();

  // メタデータ編集ダイアログが開くのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  // ルールのselectフィールドを変更
  const ruleSelect = page.getByLabel('ルール');
  await expect(ruleSelect).toBeVisible();

  // 録画済みメタデータ編集ダイアログは options 読み込み後に select 初期値が確定する
  await expect
    .poll(async () => {
      const value = await ruleSelect.inputValue();
      return value.trim();
    })
    .not.toBe('');

  const initialRuleValue = await ruleSelect.inputValue();
  console.log('初期ルール値:', initialRuleValue);

  // selectの選択肢を取得して、現在と異なる値を選択
  const options = await ruleSelect.locator('option').all();
  let newRuleValue: string | null = null;

  for (const option of options) {
    const value = await option.getAttribute('value');
    if (value && value !== initialRuleValue && value !== '') {
      newRuleValue = value;
      break;
    }
  }

  expect(newRuleValue).not.toBeNull();
  await ruleSelect.selectOption(newRuleValue!);
  await expect(ruleSelect).toHaveValue(newRuleValue!);
  console.log('新しいルール値:', newRuleValue);

  // 保存
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  // ダイアログが閉じるのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  // リストで値が更新されていることを確認
  await page.waitForTimeout(1000);

  const updatedRecordedVideo = await firstRecordedVideo(page);
  const displayedRule = await updatedRecordedVideo.getByTestId('recorded-video-rule').textContent();

  console.log('更新後のルール表示:', displayedRule);

  // 値が変わったことを確認（初期値と異なる）
  expect(displayedRule?.trim()).not.toBe('');
  expect(displayedRule?.trim()).not.toBe(initialRule?.trim());

  console.log('選択フィールド変更ワークフローが成功しました');
});

test('録画済みメタデータ編集 - 複数フィールドの一括編集', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAsset(e2eEnvironment, firstAsset);

  // 録画を完了させる
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 最初の録画済み動画を取得
  const recordedVideo = await firstRecordedVideo(page);

  // 編集ボタンをクリック
  const editButton = recordedVideo.getByTestId('recorded-video-metadata-button');
  await editButton.click();

  // メタデータ編集ダイアログが開くのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  // 複数フィールドを一括編集
  const killInput = page.getByLabel('キル数');
  const deathInput = page.getByLabel('デス数');
  const specialInput = page.getByLabel('スペシャル');
  const goldMedalsInput = page.getByLabel('金表彰');
  const silverMedalsInput = page.getByLabel('銀表彰');

  const newValues = {
    kill: '18',
    death: '6',
    special: '4',
    goldMedals: '2',
    silverMedals: '1',
  };

  await killInput.fill(newValues.kill);
  await deathInput.fill(newValues.death);
  await specialInput.fill(newValues.special);
  await goldMedalsInput.fill(newValues.goldMedals);
  await silverMedalsInput.fill(newValues.silverMedals);

  // すべての値が設定されていることを確認
  await expect(killInput).toHaveValue(newValues.kill);
  await expect(deathInput).toHaveValue(newValues.death);
  await expect(specialInput).toHaveValue(newValues.special);
  await expect(goldMedalsInput).toHaveValue(newValues.goldMedals);
  await expect(silverMedalsInput).toHaveValue(newValues.silverMedals);

  // 保存
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  // ダイアログが閉じるのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  // リストで値が更新されていることを確認
  await page.waitForTimeout(1000);

  const updatedRecordedVideo = await firstRecordedVideo(page);

  const displayedKill = await updatedRecordedVideo.getByTestId('recorded-video-kill').textContent();
  const displayedDeath = await updatedRecordedVideo
    .getByTestId('recorded-video-death')
    .textContent();
  const displayedSpecial = await updatedRecordedVideo
    .getByTestId('recorded-video-special')
    .textContent();
  const displayedGoldMedals = await updatedRecordedVideo
    .getByTestId('recorded-video-gold-medals')
    .textContent();
  const displayedSilverMedals = await updatedRecordedVideo
    .getByTestId('recorded-video-silver-medals')
    .textContent();

  expect(displayedKill?.trim()).toBe(newValues.kill);
  expect(displayedDeath?.trim()).toBe(newValues.death);
  expect(displayedSpecial?.trim()).toBe(newValues.special);
  expect(displayedGoldMedals?.trim()).toBe(newValues.goldMedals);
  expect(displayedSilverMedals?.trim()).toBe(newValues.silverMedals);

  console.log('複数フィールド一括編集ワークフローが成功しました');
});

test('録画済みメタデータ編集 - ダイアログ再オープン時の初期値', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareReplayAsset(e2eEnvironment, firstAsset);

  // 録画を完了させる
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 最初の録画済み動画を取得
  const recordedVideo = await firstRecordedVideo(page);

  // 1回目: 編集して保存
  const editButton = recordedVideo.getByTestId('recorded-video-metadata-button');
  await editButton.click();

  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  const killInput = page.getByLabel('キル数');
  const firstEditValue = '22';
  await killInput.fill(firstEditValue);

  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  await page.waitForTimeout(1000);

  // 2回目: 再度編集ダイアログを開く
  const updatedRecordedVideo = await firstRecordedVideo(page);
  const editButtonSecond = updatedRecordedVideo.getByTestId('recorded-video-metadata-button');
  await editButtonSecond.click();

  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  // 前回保存した値が初期値として表示されることを確認
  const killInputSecond = page.getByLabel('キル数');
  await expect(killInputSecond).toHaveValue(firstEditValue);

  console.log('前回保存した値が正しく初期値として表示されました:', firstEditValue);

  // キャンセルして閉じる
  const cancelButton = page.getByRole('button', { name: 'キャンセル' });
  await cancelButton.click();

  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  console.log('ダイアログ再オープン時の初期値ワークフローが成功しました');
});

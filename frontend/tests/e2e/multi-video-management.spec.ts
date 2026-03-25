/**
 * 複数ビデオ管理ワークフローE2Eテスト
 *
 * 責務：
 * - 複数の録画済み動画の管理フローを検証
 * - 一覧表示、削除、選択操作の一連の流れ
 * - ビデオ数の増減と UI の整合性
 *
 * 分類: workflow (E2E)
 */

import { copyFileSync, existsSync, linkSync, mkdirSync } from 'node:fs';
import { basename, extname, join } from 'node:path';

import { expect, test } from '@playwright/test';

import {
  ensureAutoRecordingEnabled,
  environment,
  expectedRecordedVideoCount,
  gotoMain,
  openRecordedVideos,
  prepareReplayAsset,
  replayAssets,
  recordableReplayAssets,
  switchReplayAsset,
  waitForRecordedVideoCount,
  waitForRecordedVideoReady,
} from './support/appHelpers';
import type { ReplayAsset } from './support/e2eEnv';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_800_000 : 900_000);

const e2eEnvironment = environment();
let duplicateAsset: ReplayAsset | null = null;

function ensureDistinctReplayAsset(asset: ReplayAsset): ReplayAsset {
  if (duplicateAsset) {
    return duplicateAsset;
  }

  const duplicateDir = join(e2eEnvironment.rootDir, 'multi-video-assets');
  const duplicateVideoPath = join(duplicateDir, `${asset.id}-duplicate${extname(asset.videoPath)}`);

  mkdirSync(duplicateDir, { recursive: true });
  if (!existsSync(duplicateVideoPath)) {
    try {
      linkSync(asset.videoPath, duplicateVideoPath);
    } catch {
      copyFileSync(asset.videoPath, duplicateVideoPath);
    }
  }

  duplicateAsset = {
    id: `${asset.id}-duplicate`,
    name: basename(duplicateVideoPath),
    videoPath: duplicateVideoPath,
    sidecarPath: asset.sidecarPath,
  };
  return duplicateAsset;
}

function multiVideoAssets() {
  const assets = recordableReplayAssets(e2eEnvironment);
  if (assets.length === 0) {
    return [];
  }
  if (assets.length === 1) {
    return [assets[0], ensureDistinctReplayAsset(assets[0])];
  }
  return [assets[0], assets[1]];
}

test('複数ビデオ管理 - 2本の録画完了と一覧表示', async ({ page }) => {
  const assets = multiVideoAssets();

  if (assets.length < 2) {
    test.skip();
    return;
  }

  // 1本目の録画
  prepareReplayAsset(e2eEnvironment, assets[0]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  console.log('1本目の録画が完了しました');

  // 2本目の録画
  switchReplayAsset(e2eEnvironment, assets[1]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 2);

  console.log('2本目の録画が完了しました');

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 録画数が2と表示されることを確認
  const countDisplay = page.getByTestId('recorded-count');
  await expect(countDisplay).toHaveText('2', { timeout: 30_000 });

  // 2つのビデオアイテムが表示されることを確認
  const videoItems = page.getByTestId('recorded-video-item');
  await expect(videoItems).toHaveCount(2);

  console.log('複数ビデオ一覧表示ワークフローが成功しました');
});

test('複数ビデオ管理 - 個別削除', async ({ page }) => {
  const assets = multiVideoAssets();

  if (assets.length < 2) {
    test.skip();
    return;
  }

  // 2本の録画を作成
  prepareReplayAsset(e2eEnvironment, assets[0]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  switchReplayAsset(e2eEnvironment, assets[1]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 2);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 最初のビデオの削除ボタンをクリック
  const firstVideo = page.getByTestId('recorded-video-item').first();
  const deleteButton = firstVideo.locator('button[title="動画を削除"]');
  await expect(deleteButton).toBeVisible({ timeout: 30_000 });
  await deleteButton.click();

  // 確認ダイアログが表示される
  await expect(page.getByRole('dialog', { name: '確認' })).toBeVisible({ timeout: 10_000 });

  // 削除を確定
  const confirmButton = page
    .getByRole('dialog', { name: '確認' })
    .getByRole('button', { name: '削除' });
  await confirmButton.click();

  // ダイアログが閉じるのを待つ
  await expect(page.getByRole('dialog', { name: '確認' })).toBeHidden({ timeout: 10_000 });

  // 録画数が1に減ることを確認
  await waitForRecordedVideoCount(page, 1);

  const countDisplay = page.getByTestId('recorded-count');
  await expect(countDisplay).toHaveText('1', { timeout: 30_000 });

  // ビデオアイテムが1つになることを確認
  const videoItems = page.getByTestId('recorded-video-item');
  await expect(videoItems).toHaveCount(1);

  console.log('個別削除ワークフローが成功しました');
});

test('複数ビデオ管理 - 削除キャンセル', async ({ page }) => {
  const assets = multiVideoAssets();

  if (assets.length < 2) {
    test.skip();
    return;
  }

  // 2本の録画を作成
  prepareReplayAsset(e2eEnvironment, assets[0]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  switchReplayAsset(e2eEnvironment, assets[1]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 2);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 最初のビデオの削除ボタンをクリック
  const firstVideo = page.getByTestId('recorded-video-item').first();
  const deleteButton = firstVideo.locator('button[title="動画を削除"]');
  await deleteButton.click();

  // 確認ダイアログが表示される
  await expect(page.getByRole('dialog', { name: '確認' })).toBeVisible({ timeout: 10_000 });

  // キャンセルをクリック
  const cancelButton = page.getByRole('button', { name: 'キャンセル' });
  await cancelButton.click();

  // ダイアログが閉じるのを待つ
  await expect(page.getByRole('dialog', { name: '確認' })).toBeHidden({ timeout: 10_000 });

  // 録画数が変わらず2のままであることを確認
  const countDisplay = page.getByTestId('recorded-count');
  await expect(countDisplay).toHaveText('2', { timeout: 10_000 });

  // ビデオアイテムが2つのままであることを確認
  const videoItems = page.getByTestId('recorded-video-item');
  await expect(videoItems).toHaveCount(2);

  console.log('削除キャンセルワークフローが成功しました');
});

test('複数ビデオ管理 - ビデオごとに独立したメタデータ状態', async ({ page }) => {
  const assets = multiVideoAssets();

  if (assets.length < 2) {
    test.skip();
    return;
  }

  // 2本の録画を作成
  prepareReplayAsset(e2eEnvironment, assets[0]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  switchReplayAsset(e2eEnvironment, assets[1]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 2);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  const videoItems = page.getByTestId('recorded-video-item');
  await expect(videoItems).toHaveCount(2);

  const firstVideo = videoItems.first();
  const secondVideo = videoItems.nth(1);
  const firstKillBefore = (
    await firstVideo.getByTestId('recorded-video-kill').textContent()
  )?.trim();
  const secondKillBefore = (
    await secondVideo.getByTestId('recorded-video-kill').textContent()
  )?.trim();

  expect(firstKillBefore).toBeTruthy();
  expect(secondKillBefore).toBeTruthy();

  await secondVideo.getByTestId('recorded-video-metadata-button').click();
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  const newKillValue = String(Number.parseInt(secondKillBefore ?? '0', 10) + 7);
  await page.getByLabel('キル数').fill(newKillValue);
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  await page.waitForTimeout(1000);

  const firstKillAfter = (
    await page
      .getByTestId('recorded-video-item')
      .first()
      .getByTestId('recorded-video-kill')
      .textContent()
  )?.trim();
  const secondKillAfter = (
    await page
      .getByTestId('recorded-video-item')
      .nth(1)
      .getByTestId('recorded-video-kill')
      .textContent()
  )?.trim();

  expect(firstKillAfter).toBe(firstKillBefore);
  expect(secondKillAfter).toBe(newKillValue);
  expect(secondKillAfter).not.toBe(secondKillBefore);
});

test('複数ビデオ管理 - 2本目のみ編集', async ({ page }) => {
  const assets = multiVideoAssets();

  if (assets.length < 2) {
    test.skip();
    return;
  }

  // 2本の録画を作成
  prepareReplayAsset(e2eEnvironment, assets[0]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  switchReplayAsset(e2eEnvironment, assets[1]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 2);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 1本目の初期値を記録
  const firstVideo = page.getByTestId('recorded-video-item').first();
  const firstVideoKillBefore = await firstVideo.getByTestId('recorded-video-kill').textContent();

  // 2本目を編集
  const secondVideo = page.getByTestId('recorded-video-item').nth(1);
  const secondVideoKillBefore = await secondVideo.getByTestId('recorded-video-kill').textContent();

  const editButton = secondVideo.getByTestId('recorded-video-metadata-button');
  await editButton.click();

  // メタデータ編集ダイアログが開くのを待つ
  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeVisible({
    timeout: 10_000,
  });

  // 2本目のキル数を変更
  const killInput = page.getByLabel('キル数');
  const newKillValue = '35';
  await killInput.fill(newKillValue);

  // 保存
  const saveButton = page.getByRole('button', { name: '保存' });
  await saveButton.click();

  await expect(page.getByRole('dialog', { name: 'メタデータ編集' })).toBeHidden({
    timeout: 10_000,
  });

  await page.waitForTimeout(1000);

  // 1本目は変更されていないことを確認
  const firstVideoAfter = page.getByTestId('recorded-video-item').first();
  const firstVideoKillAfter = await firstVideoAfter
    .getByTestId('recorded-video-kill')
    .textContent();
  expect(firstVideoKillAfter).toBe(firstVideoKillBefore);

  // 2本目は変更されていることを確認
  const secondVideoAfter = page.getByTestId('recorded-video-item').nth(1);
  const secondVideoKillAfter = await secondVideoAfter
    .getByTestId('recorded-video-kill')
    .textContent();
  expect(secondVideoKillAfter?.trim()).toBe(newKillValue);
  expect(secondVideoKillAfter).not.toBe(secondVideoKillBefore);

  console.log('2本目のみ編集ワークフローが成功しました');
  console.log('1本目 変更前:', firstVideoKillBefore, '変更後:', firstVideoKillAfter);
  console.log('2本目 変更前:', secondVideoKillBefore, '変更後:', secondVideoKillAfter);
});

test('複数ビデオ管理 - 空リスト時の表示', async ({ page }) => {
  // 空の状態でスタート
  prepareReplayAsset(e2eEnvironment, replayAssets(e2eEnvironment)[0]);
  await gotoMain(page);

  // 録画済みリストを開く（録画前）
  await page.getByTestId('bottom-drawer-toggle').click();
  await expect(page.getByTestId('recorded-video-list')).toBeVisible();

  // 録画数が0と表示されることを確認
  const countDisplay = page.getByTestId('recorded-count');
  await expect(countDisplay).toHaveText('0', { timeout: 10_000 });

  // ビデオアイテムが存在しないことを確認
  const videoItems = page.getByTestId('recorded-video-item');
  await expect(videoItems).toHaveCount(0);

  // 空リストメッセージが表示される（実装により異なる可能性あり）
  // ここでは単に0件であることを確認

  console.log('空リスト表示ワークフローが成功しました');
});

test('複数ビデオ管理 - 全削除後の確認', async ({ page }) => {
  const assets = replayAssets(e2eEnvironment).filter(
    (asset) => expectedRecordedVideoCount(asset) > 0
  );

  if (assets.length < 1) {
    test.skip();
    return;
  }

  // 1本の録画を作成
  prepareReplayAsset(e2eEnvironment, assets[0]);
  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordedVideoReady(page, 1);

  // 録画済みリストを開く
  await openRecordedVideos(page);

  // 録画数が1と表示されることを確認
  const countDisplay = page.getByTestId('recorded-count');
  await expect(countDisplay).toHaveText('1', { timeout: 30_000 });

  // ビデオを削除
  const firstVideo = page.getByTestId('recorded-video-item').first();
  const deleteButton = firstVideo.locator('button[title="動画を削除"]');
  await deleteButton.click();

  // 確認ダイアログで削除を確定
  await expect(page.getByRole('dialog', { name: '確認' })).toBeVisible({ timeout: 10_000 });
  const confirmButton = page
    .getByRole('dialog', { name: '確認' })
    .getByRole('button', { name: '削除' });
  await confirmButton.click();

  await expect(page.getByRole('dialog', { name: '確認' })).toBeHidden({ timeout: 10_000 });

  // 録画数が0に戻ることを確認
  await waitForRecordedVideoCount(page, 0);
  await expect(countDisplay).toHaveText('0', { timeout: 30_000 });

  // ビデオアイテムが存在しないことを確認
  const videoItems = page.getByTestId('recorded-video-item');
  await expect(videoItems).toHaveCount(0);

  console.log('全削除後の確認ワークフローが成功しました');
});

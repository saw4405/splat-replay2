import { expect, test } from '@playwright/test';

import {
  environment,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAssets,
  recordableReplayAssets,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_800_000 : 900_000);

const e2eEnvironment = environment();
const firstAsset = recordableReplayAssets(e2eEnvironment)[0];
const previewPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64'
);
let enableAutoRequestCount = 0;

test.beforeAll(async ({ request }) => {
  await request.post('/api/settings/youtube-permission-dialog', {
    data: { shown: true },
  });
});

test.beforeEach(async ({ page }) => {
  enableAutoRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    enableAutoRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(enableAutoRequestCount, 'edit-upload workflow は動画再生 API を使わない想定です。').toBe(
    0
  );
});

test('進捗ダイアログは一部画像APIが失敗しても動画枠とシークバーを表示して処理を完了する', async ({
  page,
}) => {
  if (!firstAsset) {
    throw new Error('必須のE2E replay動画fixtureが見つかりません。pretest:e2eを確認してください。');
  }

  prepareRecordedSeedAssets(e2eEnvironment, [{ asset: firstAsset }, { asset: firstAsset }]);

  await gotoMain(page);
  await openRecordedVideos(page);

  await expect(page.getByTestId('recorded-count')).toHaveText('2', {
    timeout: 30_000,
  });

  const startButton = page.getByTestId('drawer-process-button');
  await expect(startButton).toBeVisible({ timeout: 30_000 });
  await expect(startButton).toHaveText(/処理開始/);
  await expect(startButton).toBeEnabled();

  const successfulFrameUrls: string[] = [];
  const failedImageUrls: string[] = [];
  await page.route('**/api/assets/recorded/**/frame?*', async (route) => {
    const requestUrl = route.request().url();
    successfulFrameUrls.push(requestUrl);
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      headers: { 'Cache-Control': 'no-store' },
      body: previewPng,
    });
  });
  await page.route('**/thumbnails/edited/**', async (route) => {
    await route.fulfill({ status: 500, contentType: 'application/json', body: '{}' });
    failedImageUrls.push(route.request().url());
  });

  await startButton.click();

  const progressDialog = page.getByRole('dialog', { name: '進捗' });
  await expect(progressDialog).toBeVisible({ timeout: 30_000 });
  await expect(progressDialog.getByRole('navigation', { name: '処理フェーズ' })).toBeVisible({
    timeout: 60_000,
  });
  await expect(
    progressDialog.locator('img[data-testid="progress-main-image"]:visible').first()
  ).toHaveAttribute('src', /^blob:/, {
    timeout: 60_000,
  });
  await expect(
    progressDialog.locator('img[alt="thumb unmerged fg"]:visible').first()
  ).toHaveAttribute('src', /^blob:/, { timeout: 60_000 });
  expect(successfulFrameUrls.length).toBeGreaterThan(0);

  const closeButton = progressDialog.getByRole('button', { name: '閉じる' });
  await expect(closeButton).toBeDisabled();
  await expect(startButton).toBeDisabled();
  await expect(startButton).toHaveText(/処理中/);

  const completionDialog = page.getByRole('dialog', { name: '完了' });
  await expect
    .poll(() => failedImageUrls.length > 0, {
      message: '完成サムネイルAPIが500を返す',
      timeout: 60_000,
    })
    .toBe(true);

  await expect(completionDialog).toBeVisible({ timeout: 600_000 });
  await expect(completionDialog).toContainText('編集・アップロード処理が完了しました');

  const processStatusResponse = await page.request.get('/api/process/status');
  expect(processStatusResponse.ok()).toBeTruthy();
  expect(await processStatusResponse.json()).toMatchObject({ state: 'succeeded', error: null });

  const recordedAssetsResponse = await page.request.get('/api/assets/recorded');
  expect(recordedAssetsResponse.ok()).toBeTruthy();
  expect(await recordedAssetsResponse.json()).toHaveLength(0);

  await completionDialog.getByRole('button', { name: '閉じる' }).click();
});

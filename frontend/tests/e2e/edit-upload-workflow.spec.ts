import { expect, test } from '@playwright/test';

import {
  environment,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAsset,
  recordableReplayAssets,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_800_000 : 900_000);

const e2eEnvironment = environment();
const firstAsset = recordableReplayAssets(e2eEnvironment)[0];
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

test('編集・アップロード開始ワークフロー', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareRecordedSeedAsset(e2eEnvironment, { asset: firstAsset });

  await gotoMain(page);
  await openRecordedVideos(page);

  await expect(page.getByTestId('recorded-count')).toHaveText('1', {
    timeout: 30_000,
  });

  const startButton = page.locator('button.process-button');
  await expect(startButton).toBeVisible({ timeout: 30_000 });
  await expect(startButton).toHaveText(/処理開始/);
  await expect(startButton).toBeEnabled();

  await startButton.click();

  const progressDialog = page.getByRole('dialog', { name: '進捗' });
  await expect(progressDialog).toBeVisible({ timeout: 30_000 });
  await expect(progressDialog.getByRole('navigation', { name: '処理フェーズ' })).toBeVisible({
    timeout: 60_000,
  });

  const closeButton = progressDialog.getByRole('button', { name: '閉じる' });
  await expect(closeButton).toBeDisabled();
  await expect(startButton).toBeDisabled();
  await expect(startButton).toHaveText(/処理中/);

  const completionDialog = page.getByRole('dialog', { name: '完了' });
  await expect(completionDialog).toBeVisible({ timeout: 600_000 });
  await expect(completionDialog).toContainText('編集・アップロード処理が完了しました');

  await completionDialog.getByRole('button', { name: '閉じる' }).click();
});

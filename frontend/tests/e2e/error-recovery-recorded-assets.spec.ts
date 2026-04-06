import { expect, test } from '@playwright/test';

import {
  environment,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAsset,
  recordableReplayAssets,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_200_000 : 600_000);

const e2eEnvironment = environment();
const firstAsset = recordableReplayAssets(e2eEnvironment)[0];
let enableAutoRequestCount = 0;

test.beforeEach(async ({ page }) => {
  enableAutoRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    enableAutoRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(
    enableAutoRequestCount,
    'recorded-assets error recovery は動画再生 API を使わない想定です。'
  ).toBe(0);
});

test('録画済み一覧の取得失敗から再読込で復旧できる', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  prepareRecordedSeedAsset(e2eEnvironment, {
    asset: firstAsset,
    fileStem: 'error-recovery-recorded-list',
  });

  let fetchRecordedRequestCount = 0;
  await page.route('**/api/assets/recorded', (route) => {
    fetchRecordedRequestCount += 1;
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Failed to fetch recorded videos' }),
    });
  });

  await gotoMain(page);
  await expect.poll(() => fetchRecordedRequestCount, { timeout: 10_000 }).toBeGreaterThan(0);
  await openRecordedVideos(page);
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(0);
  await expect(page.getByText('録画済データがありません')).toBeVisible();

  await page.unroute('**/api/assets/recorded');

  await page.reload();
  await gotoMain(page);
  await openRecordedVideos(page);
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(1, {
    timeout: 30_000,
  });
});

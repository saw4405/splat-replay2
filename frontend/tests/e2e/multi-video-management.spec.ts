import { expect, test, type Page } from '@playwright/test';

import {
  environment,
  expectedSidecarMetadata,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAssets,
  recordableReplayAssets,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_800_000 : 900_000);

const e2eEnvironment = environment();
const firstAsset = recordableReplayAssets(e2eEnvironment)[0];
const primaryKill = String(expectedSidecarMetadata(firstAsset)?.kill ?? 13);
const secondaryKill = '28';
const editedSecondaryKill = '35';
let enableAutoRequestCount = 0;

function seedMultiVideoAssets(): void {
  if (!firstAsset) {
    return;
  }

  prepareRecordedSeedAssets(e2eEnvironment, [
    {
      asset: firstAsset,
      fileStem: 'multi-video-primary',
    },
    {
      asset: firstAsset,
      fileStem: 'multi-video-secondary',
      metadataOverride: {
        started_at: '2026-03-12T22:30:00.000000',
        kill: Number.parseInt(secondaryKill, 10),
        death: 8,
        special: 4,
        gold_medals: 2,
        silver_medals: 1,
      },
    },
  ]);
}

async function openSeededMultiVideoList(page: Page): Promise<void> {
  seedMultiVideoAssets();
  await gotoMain(page);
  await openRecordedVideos(page);
  await expect(page.getByTestId('recorded-count')).toHaveText('2', { timeout: 30_000 });
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(2);
}

function recordedVideoByKill(page: Page, kill: string) {
  return page.getByTestId('recorded-video-item').filter({
    has: page.locator('[data-testid="recorded-video-kill"]', {
      hasText: new RegExp(`^${kill}$`),
    }),
  });
}

test.beforeEach(async ({ page }) => {
  enableAutoRequestCount = 0;
  await page.route('**/api/recorder/enable-auto', async (route) => {
    enableAutoRequestCount += 1;
    await route.continue();
  });
});

test.afterEach(() => {
  expect(enableAutoRequestCount, 'multi-video-management は動画再生 API を使わない想定です。').toBe(
    0
  );
});

test('複数動画でもメタデータ編集は対象動画だけに反映される', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  await openSeededMultiVideoList(page);

  const firstVideo = recordedVideoByKill(page, primaryKill);
  const secondVideo = recordedVideoByKill(page, secondaryKill);
  await expect(firstVideo).toHaveCount(1);
  await expect(secondVideo).toHaveCount(1);

  const firstKillBefore = (
    await firstVideo.getByTestId('recorded-video-kill').textContent()
  )?.trim();

  await secondVideo.getByTestId('recorded-video-metadata-button').click();
  const metadataDialog = page.getByRole('dialog', { name: 'メタデータ編集' });
  await expect(metadataDialog).toBeVisible({ timeout: 10_000 });

  await page.getByLabel('キル数').fill(editedSecondaryKill);
  await page.getByRole('button', { name: '保存' }).click();
  await expect(metadataDialog).toBeHidden({ timeout: 10_000 });

  await expect(recordedVideoByKill(page, primaryKill)).toHaveCount(1);
  await expect(recordedVideoByKill(page, editedSecondaryKill)).toHaveCount(1);
  await expect(
    recordedVideoByKill(page, primaryKill).getByTestId('recorded-video-kill')
  ).toHaveText(primaryKill);
  await expect(
    recordedVideoByKill(page, editedSecondaryKill).getByTestId('recorded-video-kill')
  ).toHaveText(editedSecondaryKill);
  expect(firstKillBefore).toBe(primaryKill);
});

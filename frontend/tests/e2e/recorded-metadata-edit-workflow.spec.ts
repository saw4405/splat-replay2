import { expect, test, type Locator, type Page } from '@playwright/test';

import {
  environment,
  firstRecordedVideo,
  gotoMain,
  openRecordedVideos,
  prepareRecordedSeedAsset,
  recordableReplayAssets,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_200_000 : 600_000);

const e2eEnvironment = environment();
const firstAsset = recordableReplayAssets(e2eEnvironment)[0];
let enableAutoRequestCount = 0;

async function openSeededRecordedVideo(page: Page): Promise<Locator> {
  if (!firstAsset) {
    throw new Error('Recorded metadata edit test requires at least one recordable replay asset.');
  }

  prepareRecordedSeedAsset(e2eEnvironment, {
    asset: firstAsset,
    fileStem: 'recorded-metadata-edit',
  });

  await gotoMain(page);
  await openRecordedVideos(page);
  return firstRecordedVideo(page);
}

async function openMetadataDialog(page: Page, recordedVideo: Locator): Promise<Locator> {
  await recordedVideo.getByTestId('recorded-video-metadata-button').click();
  const dialog = page.getByRole('dialog', { name: 'メタデータ編集' });
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  return dialog;
}

async function selectDifferentRule(ruleSelect: Locator): Promise<void> {
  await expect
    .poll(async () => {
      const value = await ruleSelect.inputValue();
      return value.trim();
    })
    .not.toBe('');

  const initialRuleValue = await ruleSelect.inputValue();
  const options = await ruleSelect.locator('option').all();

  for (const option of options) {
    const value = await option.getAttribute('value');
    if (value && value !== initialRuleValue && value !== '') {
      await ruleSelect.selectOption(value);
      await expect(ruleSelect).toHaveValue(value);
      return;
    }
  }

  throw new Error('メタデータ編集用の別ルール option が見つかりませんでした。');
}

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
    'recorded-metadata-edit workflow は動画再生 API を使わない想定です。'
  ).toBe(0);
});

test('録画済みメタデータ編集の代表保存', async ({ page }) => {
  if (!firstAsset) {
    test.skip();
    return;
  }

  const recordedVideo = await openSeededRecordedVideo(page);
  const initialRule = (
    await recordedVideo.getByTestId('recorded-video-rule').textContent()
  )?.trim();

  const dialog = await openMetadataDialog(page, recordedVideo);

  await page.getByLabel('キル数').fill('20');
  await page.getByLabel('デス数').fill('4');
  await selectDifferentRule(page.getByLabel('ルール'));

  await page.getByRole('button', { name: '保存' }).click();
  await expect(dialog).toBeHidden({ timeout: 10_000 });

  const updatedRecordedVideo = await firstRecordedVideo(page);
  await expect(updatedRecordedVideo.getByTestId('recorded-video-kill')).toHaveText('20');
  await expect(updatedRecordedVideo.getByTestId('recorded-video-death')).toHaveText('4');
  await expect(updatedRecordedVideo.getByTestId('recorded-video-rule')).not.toHaveText(
    initialRule ?? ''
  );
});

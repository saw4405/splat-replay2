import { expect, test } from '@playwright/test';

import {
  environment,
  expectSidecarToMatchRecordedVideoItem,
  expectedSidecarMetadata,
  firstRecordedVideo,
  gotoMain,
  openRecordedVideos,
  prepareReplayAsset,
  replayAssets,
  waitForRecordedVideoCount,
  waitForRecordingLifecycle,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_200_000 : 600_000);

const e2eEnvironment = environment();

for (const replayAsset of replayAssets(e2eEnvironment)) {
  test(`auto-recording-workflow [${replayAsset.name}]`, async ({ page }) => {
    prepareReplayAsset(e2eEnvironment, replayAsset);

    await gotoMain(page);
    await waitForRecordingLifecycle(page);
    await waitForRecordedVideoCount(page, 1);
    await gotoMain(page);
    await openRecordedVideos(page);

    await expect(page.getByTestId('recorded-count')).toHaveText('1', {
      timeout: 300_000,
    });

    const recordedVideo = await firstRecordedVideo(page);
    const expectedMetadata = expectedSidecarMetadata(replayAsset);

    if (!expectedMetadata) {
      await expect(recordedVideo).toBeVisible();
      return;
    }

    await expectSidecarToMatchRecordedVideoItem(page, recordedVideo, expectedMetadata);
  });
}

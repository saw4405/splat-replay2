import { expect, test } from '@playwright/test';

import {
  ensureAutoRecordingEnabled,
  environment,
  expectedRecordedVideoCount,
  expectSidecarToMatchRecordedVideoItem,
  expectedSidecarMetadata,
  firstRecordedVideo,
  gotoMain,
  openRecordedVideos,
  prepareReplayAsset,
  recordableReplayAssets,
  replayAssets,
  waitForRecordedVideoCount,
  waitForRecordingLifecycle,
  waitForVideoPreviewReady,
} from './support/appHelpers';

test.setTimeout(process.env.SPLAT_REPLAY_E2E_MODE === 'full' ? 1_200_000 : 600_000);

const e2eEnvironment = environment();
const earlyAbortAsset = replayAssets(e2eEnvironment).find(
  (asset) => expectedRecordedVideoCount(asset) === 0
);

async function stopAutoRecordingForNextSpec(): Promise<void> {
  const deadline = Date.now() + 10_000;

  while (Date.now() < deadline) {
    try {
      const stateResponse = await fetch('http://127.0.0.1:8000/api/recorder/state');
      if (stateResponse.ok) {
        const body = (await stateResponse.json()) as { state?: string | null };
        if (body.state === 'STOPPED') {
          return;
        }
      }
    } catch {
      return;
    }

    try {
      await fetch('http://127.0.0.1:8000/api/recorder/stop', { method: 'POST' });
    } catch {
      return;
    }

    try {
      await fetch('http://127.0.0.1:8000/api/recorder/disable-auto', { method: 'POST' });
    } catch {
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 500));
  }
}

test.afterAll(async () => {
  await stopAutoRecordingForNextSpec();
});

test('auto-recording early abort resets metadata and does not save recording', async ({ page }) => {
  if (!earlyAbortAsset) {
    test.skip();
    return;
  }

  prepareReplayAsset(e2eEnvironment, earlyAbortAsset);

  await gotoMain(page);
  await ensureAutoRecordingEnabled(page);
  await waitForRecordingLifecycle(page);
  await expect(page.getByTestId('video-preview-status')).toHaveText('Stopped', {
    timeout: 300_000,
  });
  await page.getByTestId('metadata-toggle-button').click();
  await expect(page.getByLabel('開始時間')).toHaveValue('');
  await expect(page.getByLabel('キル数')).toHaveValue('0');
  await expect(page.getByLabel('デス数')).toHaveValue('0');
  await expect(page.getByLabel('スペシャル')).toHaveValue('0');

  await waitForRecordedVideoCount(page, 0);
  await openRecordedVideos(page);
  await expect(page.getByTestId('recorded-count')).toHaveText('0', {
    timeout: 300_000,
  });
  await expect(page.getByTestId('recorded-video-item')).toHaveCount(0);
});

for (const replayAsset of recordableReplayAssets(e2eEnvironment)) {
  test(`auto-recording-workflow [${replayAsset.name}]`, async ({ page }) => {
    prepareReplayAsset(e2eEnvironment, replayAsset);
    const expectedRecordedCount = expectedRecordedVideoCount(replayAsset);

    await gotoMain(page);
    await ensureAutoRecordingEnabled(page);
    await waitForRecordingLifecycle(page);
    await waitForVideoPreviewReady(page);
    await waitForRecordedVideoCount(page, expectedRecordedCount);
    await gotoMain(page);
    await openRecordedVideos(page);

    await expect(page.getByTestId('recorded-count')).toHaveText(String(expectedRecordedCount), {
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

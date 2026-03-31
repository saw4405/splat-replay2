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
const firstAsset = replayAssets(e2eEnvironment)[0];
const autoRecordingBootstrapScenario = {
  replay_bootstrap: {
    phase: 'in_game',
    game_mode: 'BATTLE',
  },
};

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

  const killInput = page.getByLabel('キル数');
  const deathInput = page.getByLabel('デス数');
  const specialInput = page.getByLabel('スペシャル');
  const stageSelect = page.getByLabel('ステージ');

  await expect(killInput).toBeVisible();
  await killInput.fill('15');
  await deathInput.fill('3');
  await specialInput.fill('2');

  const initialStage = await stageSelect.inputValue();
  const options = await stageSelect.locator('option').all();
  let nextStageValue: string | null = null;

  for (const option of options) {
    const value = await option.getAttribute('value');
    if (value && value !== initialStage && value !== '') {
      nextStageValue = value;
      break;
    }
  }

  expect(nextStageValue).not.toBeNull();
  await stageSelect.selectOption(nextStageValue!);

  await page.getByRole('button', { name: '保存' }).click();

  const completionDialog = page.getByRole('dialog', { name: '完了' });
  await expect(completionDialog).toContainText('メタデータを保存しました', {
    timeout: 10_000,
  });
  await completionDialog.getByRole('button', { name: '閉じる' }).click();

  await expect(killInput).toHaveValue('15');
  await expect(deathInput).toHaveValue('3');
  await expect(specialInput).toHaveValue('2');
  await expect(stageSelect).toHaveValue(nextStageValue!);

  await stopRecordingForTeardown(page);
});

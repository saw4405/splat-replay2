import { expect, test } from '@playwright/test';
import { join } from 'node:path';

import {
  environment,
  gotoMain,
  resetReplayTestState,
  saveBehaviorSettings,
  verifyPersistedBehaviorSettings,
} from './support/appHelpers';

const e2eEnvironment = environment();

test('settings-persistence', async ({ page }) => {
  resetReplayTestState(e2eEnvironment);
  await gotoMain(page);
  await saveBehaviorSettings(page);
  await verifyPersistedBehaviorSettings(page);

  await page.getByRole('radio', { name: 'すべての設定' }).click();
  await page.getByTestId('settings-section-storage').click();
  const recordedField = page.getByTestId(
    'settings-field-storage-storage-keep_recordings_after_edit'
  );
  const editedField = page.getByTestId('settings-field-storage-storage-keep_edited_after_upload');
  const recordedLabel = '編集後も元録画を保持';
  const editedLabel = 'アップロード後も編集済み動画を保持';

  await expect(recordedField.getByRole('checkbox', { name: recordedLabel })).toBeChecked({
    checked: false,
  });
  await expect(editedField.getByRole('checkbox', { name: editedLabel })).toBeChecked({
    checked: false,
  });
  await expect(recordedField).toContainText(
    join(e2eEnvironment.storageDir, 'retained', 'recorded')
  );
  await expect(editedField).toContainText(join(e2eEnvironment.storageDir, 'retained', 'edited'));

  await recordedField.getByText(recordedLabel, { exact: true }).click();
  await editedField.getByText(editedLabel, { exact: true }).click();
  await page.getByRole('button', { name: '保存' }).click();
  await expect(page.getByRole('dialog', { name: '設定' })).toBeHidden();

  await page.getByTestId('settings-button').click();
  await page.getByRole('radio', { name: 'すべての設定' }).click();
  await page.getByTestId('settings-section-storage').click();
  await expect(recordedField.getByRole('checkbox', { name: recordedLabel })).toBeChecked();
  await expect(editedField.getByRole('checkbox', { name: editedLabel })).toBeChecked();
});

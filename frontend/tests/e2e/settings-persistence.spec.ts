import { test } from '@playwright/test';

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
});

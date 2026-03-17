import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from '@playwright/test';

import { bootstrapE2EEnvironment } from './tests/e2e/support/e2eEnv';

const frontendDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendDir, '..');
const backendDir = resolve(repoRoot, 'backend');
const e2eEnvironment = bootstrapE2EEnvironment();

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 180_000,
  expect: {
    timeout: 30_000,
  },
  globalSetup: './tests/e2e/support/globalSetup.ts',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command:
        'uv run python -m uvicorn splat_replay.bootstrap.web_app:app --factory --host 127.0.0.1 --port 8000',
      cwd: backendDir,
      env: {
        ...process.env,
        SPLAT_REPLAY_SETTINGS_FILE: e2eEnvironment.settingsFile,
      },
      timeout: 180_000,
      url: 'http://127.0.0.1:8000/api/settings',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1',
      cwd: frontendDir,
      env: {
        ...process.env,
      },
      timeout: 120_000,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
    },
  ],
});

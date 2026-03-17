import type { FullConfig } from '@playwright/test';

import { bootstrapE2EEnvironment } from './e2eEnv';

async function globalSetup(_config: FullConfig): Promise<void> {
  bootstrapE2EEnvironment(true);
}

export default globalSetup;

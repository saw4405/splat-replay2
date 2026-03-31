import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { bootstrapE2EEnvironment } from '../tests/e2e/support/e2eEnv';

const temporaryRoots: string[] = [];

describe('e2eEnv installation state bootstrap', () => {
  afterEach(() => {
    vi.unstubAllEnvs();

    while (temporaryRoots.length > 0) {
      const root = temporaryRoots.pop();
      if (!root) {
        continue;
      }
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('writes a completed installer state next to settings.toml', () => {
    const rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-e2e-vitest-'));
    const settingsFile = join(rootDir, 'config', 'settings.toml');
    temporaryRoots.push(rootDir);

    vi.stubEnv('SPLAT_REPLAY_E2E_ROOT', rootDir);
    vi.stubEnv('SPLAT_REPLAY_SETTINGS_FILE', settingsFile);
    vi.stubEnv('SPLAT_REPLAY_E2E_MODE', 'smoke');

    const environment = bootstrapE2EEnvironment(true);
    const installationStateFile = join(
      dirname(environment.settingsFile),
      'installation_state.toml'
    );

    const content = readFileSync(installationStateFile, 'utf-8');

    expect(content).toContain('[installer]');
    expect(content).toContain('is_completed = true');
    expect(content).toContain('youtube_permission_dialog_shown = true');
    expect(content).not.toContain('[setup]');
  });
});

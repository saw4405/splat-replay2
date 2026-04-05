import { afterEach, describe, expect, it, vi } from 'vitest';

const BACKEND_SETTINGS_URL = 'http://127.0.0.1:8000/api/settings';

// playwright.config はモジュールレベルで bootstrapE2EEnvironment() を実行するため
// ファイル IO を避けてインポート速度を改善するためにモック化する
vi.mock('../tests/e2e/support/e2eEnv', () => ({
  bootstrapE2EEnvironment: vi.fn(() => ({
    mode: 'smoke',
    rootDir: '/tmp/splat-replay-e2e-test',
    settingsFile: '/tmp/splat-replay-e2e-test/settings.toml',
    replayInputFile: '/tmp/splat-replay-e2e-test/replay.json',
    storageDir: '/tmp/splat-replay-e2e-test/videos',
    autoRecordingReplayDir: '/tmp/splat-replay-e2e-test/auto-recording',
    replayAssets: [],
  })),
}));

describe('playwright config', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('passes noop upload flag to backend webServer env', async () => {
    vi.stubEnv('CI', '');
    vi.stubEnv('SPLAT_REPLAY_E2E_MODE', 'smoke');
    vi.stubEnv('SPLAT_REPLAY_E2E_NOOP_UPLOAD', '');

    const { default: config } = await import('../playwright.config');
    const servers = Array.isArray(config.webServer) ? config.webServer : [config.webServer];
    const backendServer = servers.find((server) => server.url === BACKEND_SETTINGS_URL);

    expect(backendServer?.env?.SPLAT_REPLAY_E2E_NOOP_UPLOAD).toBe('1');
    expect(backendServer?.reuseExistingServer).toBe(false);
  });
});

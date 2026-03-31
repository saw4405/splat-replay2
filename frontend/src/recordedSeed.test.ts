import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, extname, join } from 'node:path';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { bootstrapE2EEnvironment, type E2EEnvironment } from '../tests/e2e/support/e2eEnv';
import { seedRecordedVideos } from '../tests/e2e/support/recordedSeed';

const temporaryRoots: string[] = [];

function bootstrapTestEnvironment(): E2EEnvironment {
  const rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-recorded-seed-'));
  const settingsFile = join(rootDir, 'config', 'settings.toml');
  temporaryRoots.push(rootDir);

  vi.stubEnv('SPLAT_REPLAY_E2E_ROOT', rootDir);
  vi.stubEnv('SPLAT_REPLAY_SETTINGS_FILE', settingsFile);
  vi.stubEnv('SPLAT_REPLAY_E2E_MODE', 'smoke');

  return bootstrapE2EEnvironment(true);
}

describe('recordedSeed', () => {
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

  it('recorded 配下へ動画と metadata を作成し scenario を除外する', () => {
    const environment = bootstrapTestEnvironment();
    const asset = environment.replayAssets[0];

    const [seeded] = seedRecordedVideos(environment, [{ asset }]);
    const metadata = JSON.parse(readFileSync(seeded.metadataPath, 'utf-8')) as Record<
      string,
      unknown
    >;

    expect(basename(seeded.videoPath, extname(seeded.videoPath))).toBe(asset.id);
    expect(seeded.videoPath).toContain(join(environment.storageDir, 'recorded'));
    expect(extname(seeded.videoPath)).toBe(extname(asset.videoPath));
    expect(existsSync(seeded.videoPath)).toBe(true);
    expect(existsSync(seeded.metadataPath)).toBe(true);
    expect(metadata).toMatchObject({
      game_mode: 'BATTLE',
      judgement: 'WIN',
      started_at: '2026-03-12T22:22:00.999005',
    });
    expect(metadata.scenario).toBeUndefined();
  });

  it('fileStem と metadataOverride を適用して同一 asset を複数 seed できる', () => {
    const environment = bootstrapTestEnvironment();
    const asset = environment.replayAssets[0];

    const seeded = seedRecordedVideos(environment, [
      {
        asset,
        fileStem: 'battle-primary',
      },
      {
        asset,
        fileStem: 'battle-secondary',
        metadataOverride: {
          started_at: '2026-03-13T00:00:00',
          kill: 99,
          stage: 'MANTA_MARIA',
        },
      },
    ]);

    const secondMetadata = JSON.parse(readFileSync(seeded[1].metadataPath, 'utf-8')) as Record<
      string,
      unknown
    >;

    expect(seeded).toHaveLength(2);
    expect(basename(seeded[0].videoPath, extname(seeded[0].videoPath))).toBe('battle-primary');
    expect(basename(seeded[1].videoPath, extname(seeded[1].videoPath))).toBe('battle-secondary');
    expect(secondMetadata).toMatchObject({
      started_at: '2026-03-13T00:00:00',
      kill: 99,
      stage: 'MANTA_MARIA',
      game_mode: 'BATTLE',
    });
    expect(secondMetadata.scenario).toBeUndefined();
  });
});

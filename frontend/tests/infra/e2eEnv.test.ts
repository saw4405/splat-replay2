// @vitest-environment node
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  bootstrapE2EEnvironment,
  configureReplayAsset,
  isWslRuntime,
  loadSidecarMetadata,
  type ReplayAsset,
} from '../../tests/e2e/support/e2eEnv';

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

  it('identifies WSL without treating native macOS as a mounted Windows path runtime', () => {
    expect(isWslRuntime('linux', { WSL_DISTRO_NAME: 'Ubuntu' }, '')).toBe(true);
    expect(isWslRuntime('linux', {}, '5.15.153.1-microsoft-standard-WSL2')).toBe(true);
    expect(isWslRuntime('darwin', {}, '')).toBe(false);
  });

  it('sidecar の scenario と observations だけを replay input に転記する', () => {
    const rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-e2e-sidecar-'));
    const settingsFile = join(rootDir, 'config', 'settings.toml');
    temporaryRoots.push(rootDir);

    vi.stubEnv('SPLAT_REPLAY_E2E_ROOT', rootDir);
    vi.stubEnv('SPLAT_REPLAY_SETTINGS_FILE', settingsFile);
    vi.stubEnv('SPLAT_REPLAY_E2E_MODE', 'full');

    const environment = bootstrapE2EEnvironment(true);
    const defaultReplayInput = JSON.parse(readFileSync(environment.replayInputFile, 'utf-8')) as {
      video_path: string;
      scenario?: unknown;
      observations?: unknown;
    };
    const regularAsset = environment.replayAssets.find(
      (asset) => asset.id === 'regular-turf-war-mincemeat-win'
    );
    if (!regularAsset) {
      throw new Error('regular-turf-war-mincemeat-win replay asset was not found.');
    }

    expect(defaultReplayInput.video_path).toBe(environment.replayAssets[0].videoPath);
    expect(defaultReplayInput.scenario).toEqual({
      expected_recorded_count: 0,
      replay_bootstrap: {
        phase: 'matching',
        game_mode: 'battle',
      },
    });
    expect(defaultReplayInput.observations).toEqual({});
    expect(defaultReplayInput).not.toHaveProperty('expected');
    expect(defaultReplayInput).not.toHaveProperty('schema_version');

    configureReplayAsset(environment, regularAsset);
    const replayInput = JSON.parse(readFileSync(environment.replayInputFile, 'utf-8')) as {
      video_path: string;
      scenario?: unknown;
      observations?: {
        weapon_recognition?: {
          display?: unknown;
          slots?: Record<string, unknown>;
        };
        ocr?: Record<string, unknown>;
        battle_medals?: Record<string, unknown>;
      };
    };

    expect(replayInput.video_path).toBe(regularAsset.videoPath);
    expect(replayInput.scenario).toEqual({});
    expect(replayInput.observations?.weapon_recognition?.display).toEqual({
      is_visible: true,
      should_recognize: true,
    });
    expect(replayInput.observations?.weapon_recognition?.slots).toMatchObject({
      ally_1: { weapon: 'トライストリンガー', matched: true },
      enemy_4: { weapon: 'ホットブラスターカスタム', matched: true },
    });
    expect(Object.keys(replayInput.observations?.weapon_recognition?.slots ?? {})).toHaveLength(8);
    expect(replayInput.observations?.ocr).toEqual({
      battle_kill: '13',
      battle_death: '2',
      battle_special: '3',
    });
    expect(replayInput.observations?.battle_medals).toEqual({
      gold: 3,
      silver: 0,
    });
    expect(replayInput).not.toHaveProperty('expected');
    expect(replayInput).not.toHaveProperty('schema_version');
  });

  it('旧 root metadata 形式の sidecar を受け入れない', () => {
    const rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-e2e-legacy-sidecar-'));
    const sidecarPath = join(rootDir, 'legacy.json');
    temporaryRoots.push(rootDir);
    writeFileSync(sidecarPath, JSON.stringify({ game_mode: 'BATTLE' }), 'utf-8');
    const legacyAsset: ReplayAsset = {
      id: 'legacy',
      name: 'legacy.mkv',
      videoPath: join(rootDir, 'legacy.mkv'),
      sidecarPath,
    };

    expect(() => loadSidecarMetadata(legacyAsset)).toThrow('Invalid replay sidecar metadata');
  });

  it('OCR observation の値型を検証する', () => {
    const rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-e2e-invalid-ocr-'));
    const sidecarPath = join(rootDir, 'invalid-ocr.json');
    temporaryRoots.push(rootDir);
    writeFileSync(
      sidecarPath,
      JSON.stringify({
        schema_version: 1,
        scenario: {},
        observations: {
          ocr: {
            battle_kill: 13,
          },
        },
        expected: null,
      }),
      'utf-8'
    );
    const asset: ReplayAsset = {
      id: 'invalid-ocr',
      name: 'invalid-ocr.mkv',
      videoPath: join(rootDir, 'invalid-ocr.mkv'),
      sidecarPath,
    };

    expect(() => loadSidecarMetadata(asset)).toThrow('Invalid replay sidecar metadata');
  });

  it('武器認識 observation の8スロット契約を検証する', () => {
    const rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-e2e-invalid-weapon-'));
    const sidecarPath = join(rootDir, 'invalid-weapon.json');
    temporaryRoots.push(rootDir);
    writeFileSync(
      sidecarPath,
      JSON.stringify({
        schema_version: 1,
        scenario: {},
        observations: {
          weapon_recognition: {
            display: {
              is_visible: true,
              should_recognize: true,
            },
            slots: {
              ally_1: { weapon: 'トライストリンガー', matched: true },
            },
          },
        },
        expected: null,
      }),
      'utf-8'
    );
    const asset: ReplayAsset = {
      id: 'invalid-weapon',
      name: 'invalid-weapon.mkv',
      videoPath: join(rootDir, 'invalid-weapon.mkv'),
      sidecarPath,
    };

    expect(() => loadSidecarMetadata(asset)).toThrow('Invalid replay sidecar metadata');
  });

  it('表彰認識 observation の値型とキーを検証する', () => {
    const rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-e2e-invalid-medals-'));
    const sidecarPath = join(rootDir, 'invalid-medals.json');
    temporaryRoots.push(rootDir);
    writeFileSync(
      sidecarPath,
      JSON.stringify({
        schema_version: 1,
        scenario: {},
        observations: {
          battle_medals: {
            gold: true,
            bronze: 0,
          },
        },
        expected: null,
      }),
      'utf-8'
    );
    const asset: ReplayAsset = {
      id: 'invalid-medals',
      name: 'invalid-medals.mkv',
      videoPath: join(rootDir, 'invalid-medals.mkv'),
      sidecarPath,
    };

    expect(() => loadSidecarMetadata(asset)).toThrow('Invalid replay sidecar metadata');
  });
});

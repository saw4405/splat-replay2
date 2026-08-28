import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { release, tmpdir } from 'node:os';
import { basename, dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const WINDOWS_PATH_RE = /^(?<drive>[a-zA-Z]):[\\/](?<rest>.*)$/;
const WSL_PATH_RE = /^\/mnt\/(?<drive>[a-zA-Z])\/(?<rest>.*)$/;
const BOOTSTRAP_FLAG = 'SPLAT_REPLAY_E2E_BOOTSTRAPPED';
const E2E_MODE_ENV = 'SPLAT_REPLAY_E2E_MODE';
const E2E_FRAME_STRIDE_ENV = 'SPLAT_REPLAY_E2E_FRAME_STRIDE';
const SUPPORT_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_AUTO_RECORDING_REPLAY_DIR = resolve(
  SUPPORT_DIR,
  '..',
  '..',
  'fixtures',
  'e2e',
  'auto-recording'
);

export type E2EMode = 'smoke' | 'full';

export type E2EEnvironment = {
  mode: E2EMode;
  rootDir: string;
  settingsFile: string;
  replayInputFile: string;
  storageDir: string;
  autoRecordingReplayDir: string;
  replayAssets: ReplayAsset[];
};

export type ReplayAsset = {
  id: string;
  name: string;
  videoPath: string;
  sidecarPath: string | null;
};

export type ReplayScenario = {
  expected_recorded_count?: number | null;
  replay_bootstrap?: {
    phase?: string | null;
    game_mode?: string | null;
  } | null;
};

export type ReplayWeaponSlotName =
  | 'ally_1'
  | 'ally_2'
  | 'ally_3'
  | 'ally_4'
  | 'enemy_1'
  | 'enemy_2'
  | 'enemy_3'
  | 'enemy_4';

export type ReplayWeaponSlotObservation = {
  weapon: string;
  matched: boolean;
};

export type ReplayWeaponRecognitionObservation = {
  display: {
    is_visible: boolean;
    should_recognize: boolean;
  };
  slots: Record<ReplayWeaponSlotName, ReplayWeaponSlotObservation>;
};

export type ReplayOcrObservationKey =
  | 'battle_kill'
  | 'battle_death'
  | 'battle_special'
  | 'battle_xp'
  | 'battle_event_power'
  | 'battle_kill_record';

export type ReplayOcrObservations = Partial<Record<ReplayOcrObservationKey, string | null>>;

export type ReplayBattleMedalObservation = {
  gold: number;
  silver: number;
};

export type ReplayObservations = {
  weapon_recognition?: ReplayWeaponRecognitionObservation | null;
  ocr?: ReplayOcrObservations | null;
  battle_medals?: ReplayBattleMedalObservation | null;
};

export type ExpectedSidecarMetadata = {
  game_mode?: string | null;
  started_at?: string | null;
  rate?: string | null;
  judgement?: string | null;
  match?: string | null;
  rule?: string | null;
  stage?: string | null;
  kill?: number | null;
  death?: number | null;
  special?: number | null;
  gold_medals?: number | null;
  silver_medals?: number | null;
  allies?: string[] | null;
  enemies?: string[] | null;
};

export type SidecarMetadata = {
  schema_version: 1;
  scenario: ReplayScenario | null;
  observations: ReplayObservations;
  expected: ExpectedSidecarMetadata | null;
};

export function isWslRuntime(
  platform = process.platform,
  environment: { WSL_DISTRO_NAME?: string; WSL_INTEROP?: string } = process.env,
  kernelRelease = release()
): boolean {
  return (
    platform === 'linux' &&
    Boolean(
      environment.WSL_DISTRO_NAME ||
      environment.WSL_INTEROP ||
      kernelRelease.toLowerCase().includes('microsoft')
    )
  );
}

function escapeTomlString(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

export function normalizeInputPath(rawPath: string): string {
  const trimmed = rawPath.trim();
  if (!trimmed) {
    throw new Error('E2E video input path is empty.');
  }

  const match = trimmed.match(WINDOWS_PATH_RE);
  if (match?.groups) {
    if (process.platform === 'win32') {
      return trimmed;
    }
    if (isWslRuntime()) {
      const drive = match.groups.drive.toLowerCase();
      const rest = match.groups.rest.replace(/\\/g, '/').replace(/^\/+/, '');
      return `/mnt/${drive}/${rest}`;
    }
  }

  const wslMatch = trimmed.match(WSL_PATH_RE);
  if (wslMatch?.groups && process.platform === 'win32') {
    const drive = wslMatch.groups.drive.toUpperCase();
    const rest = wslMatch.groups.rest.replace(/\//g, '\\');
    return `${drive}:\\${rest}`;
  }

  return trimmed;
}

export function resolveVideoInputPath(rawPath: string): string {
  const normalizedPath = resolve(normalizeInputPath(rawPath));
  if (!existsSync(normalizedPath)) {
    throw new Error(`E2E video input was not found: ${normalizedPath}`);
  }

  const currentStat = statSync(normalizedPath);
  if (currentStat.isFile()) {
    return normalizedPath;
  }

  const selectedVideo = readdirSync(normalizedPath, { withFileTypes: true })
    .filter((entry) => entry.isFile() && extname(entry.name).toLowerCase() === '.mkv')
    .map((entry) => resolve(normalizedPath, entry.name))
    .sort((left, right) => {
      const sizeDiff = statSync(left).size - statSync(right).size;
      if (sizeDiff !== 0) {
        return sizeDiff;
      }
      return basename(left).localeCompare(basename(right), 'ja');
    });

  if (selectedVideo.length === 0) {
    throw new Error(`No .mkv file was found in: ${normalizedPath}`);
  }

  return selectedVideo[0];
}

export function listReplayAssets(replayDir: string): ReplayAsset[] {
  const normalizedReplayDir = resolve(normalizeInputPath(replayDir));
  if (!existsSync(normalizedReplayDir)) {
    throw new Error(`E2E replay directory was not found: ${normalizedReplayDir}`);
  }

  const replayRoot = statSync(normalizedReplayDir).isDirectory()
    ? normalizedReplayDir
    : dirname(normalizedReplayDir);

  const replayAssets = readdirSync(replayRoot, { withFileTypes: true })
    .filter((entry) => entry.isFile() && extname(entry.name).toLowerCase() === '.mkv')
    .map((entry) => {
      const videoPath = resolve(replayRoot, entry.name);
      const stem = basename(videoPath, extname(videoPath));
      const sidecarPath = resolve(replayRoot, `${stem}.json`);
      return {
        id: stem,
        name: entry.name,
        videoPath,
        sidecarPath: existsSync(sidecarPath) ? sidecarPath : null,
      } satisfies ReplayAsset;
    })
    .sort((left, right) => left.name.localeCompare(right.name, 'ja'));

  if (replayAssets.length === 0) {
    throw new Error(`No .mkv file was found in: ${replayRoot}`);
  }

  return replayAssets;
}

function buildSettingsToml(storageDir: string): string {
  return [
    '[behavior]',
    'edit_after_power_off = false',
    'sleep_after_upload = false',
    'record_battle_history = false',
    '',
    '[speech_transcriber]',
    'enabled = false',
    'mic_device_name = ""',
    'groq_api_key = ""',
    'groq_model = "whisper-large-v3"',
    'integrator_model = "openai/gpt-oss-20b"',
    'language = "ja-JP"',
    'phrase_time_limit = 3.0',
    'custom_dictionary = []',
    'vad_aggressiveness = 2',
    'vad_min_speech_frames = 3',
    'vad_min_speech_ratio = 0.1',
    '',
    '[storage]',
    `base_dir = "${escapeTomlString(storageDir)}"`,
    '',
  ].join('\n');
}

function buildInstallationStateToml(): string {
  return [
    '[installer]',
    'is_completed = true',
    'current_step = "youtube_setup"',
    'completed_steps = [',
    '  "hardware_check",',
    '  "ffmpeg_setup",',
    '  "obs_setup",',
    '  "tesseract_setup",',
    '  "font_installation",',
    '  "transcription_setup",',
    '  "youtube_setup",',
    ']',
    'skipped_steps = []',
    'camera_permission_dialog_shown = false',
    'youtube_permission_dialog_shown = true',
    '',
  ].join('\n');
}

function buildReplayInputJson(
  videoPath: string,
  scenario: ReplayScenario | null,
  observations: ReplayObservations
): string {
  return JSON.stringify(
    {
      video_path: videoPath,
      ...(scenario ? { scenario } : {}),
      observations,
    },
    null,
    2
  );
}

function writeDefaultReplayInput(environment: E2EEnvironment): void {
  const asset = environment.replayAssets[0];
  if (!asset) {
    throw new Error('E2E replay asset was not found.');
  }
  const sidecar = requireSidecarMetadata(asset);
  writeFileSync(
    environment.replayInputFile,
    buildReplayInputJson(asset.videoPath, sidecar.scenario, sidecar.observations),
    'utf-8'
  );
}

function clearDirectoryContents(directory: string): void {
  mkdirSync(directory, { recursive: true });
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const targetPath = join(directory, entry.name);
    try {
      rmSync(targetPath, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 });
    } catch {
      if (entry.isDirectory()) {
        clearDirectoryContents(targetPath);
      }
    }
  }
}

function resolveE2EMode(): E2EMode {
  const configured = (process.env[E2E_MODE_ENV] ?? 'full').trim().toLowerCase();
  if (configured === 'smoke' || configured === 'full') {
    return configured;
  }

  throw new Error(`${E2E_MODE_ENV} must be "smoke" or "full", received: ${configured}`);
}

export function ensureE2EEnvironment(): E2EEnvironment {
  const mode = resolveE2EMode();
  const autoRecordingReplayDir = resolve(normalizeInputPath(DEFAULT_AUTO_RECORDING_REPLAY_DIR));
  let rootDir = process.env.SPLAT_REPLAY_E2E_ROOT;
  if (!rootDir) {
    rootDir = mkdtempSync(join(tmpdir(), 'splat-replay-e2e-'));
    process.env.SPLAT_REPLAY_E2E_ROOT = rootDir;
  }

  const settingsFile = process.env.SPLAT_REPLAY_SETTINGS_FILE ?? join(rootDir, 'settings.toml');
  const replayInputFile = join(rootDir, 'e2e-replay-input.json');
  const storageDir = process.env.SPLAT_REPLAY_E2E_STORAGE_DIR ?? join(rootDir, 'videos');
  const allReplayAssets = listReplayAssets(autoRecordingReplayDir);
  const replayAssets = mode === 'smoke' ? [allReplayAssets[0]] : allReplayAssets;

  mkdirSync(rootDir, { recursive: true });
  mkdirSync(storageDir, { recursive: true });
  mkdirSync(dirname(settingsFile), { recursive: true });

  process.env.SPLAT_REPLAY_SETTINGS_FILE = settingsFile;
  process.env.SPLAT_REPLAY_E2E_STORAGE_DIR = storageDir;
  process.env[E2E_MODE_ENV] = mode;
  process.env[E2E_FRAME_STRIDE_ENV] ??= mode === 'smoke' ? '3' : '1';

  return {
    mode,
    rootDir,
    settingsFile,
    replayInputFile,
    storageDir,
    autoRecordingReplayDir,
    replayAssets,
  };
}

export function bootstrapE2EEnvironment(force = false): E2EEnvironment {
  const environment = ensureE2EEnvironment();
  if (force || process.env[BOOTSTRAP_FLAG] !== '1' || !existsSync(environment.settingsFile)) {
    writeFileSync(environment.settingsFile, buildSettingsToml(environment.storageDir), 'utf-8');

    // installation_state.tomlファイルを作成（YouTube権限ダイアログを承認済みに設定）
    const installationStateFile = join(
      dirname(environment.settingsFile),
      'installation_state.toml'
    );
    writeFileSync(installationStateFile, buildInstallationStateToml(), 'utf-8');

    // バックエンドはlifespan開始時から自動録画を常駐起動する。
    // 最初のspecが入力を切り替える前に実OBSへフォールバックしないよう、
    // 起動時点から代表リプレイ入力を公開しておく。
    writeDefaultReplayInput(environment);
    process.env[BOOTSTRAP_FLAG] = '1';
  }
  return environment;
}

export function configureReplayAsset(
  environment: E2EEnvironment,
  asset: ReplayAsset,
  scenarioOverride?: ReplayScenario | null
): void {
  const sidecar = requireSidecarMetadata(asset);
  const baseScenario = sidecar.scenario;
  const scenario = scenarioOverride
    ? {
        ...(baseScenario ?? {}),
        ...scenarioOverride,
        replay_bootstrap:
          scenarioOverride.replay_bootstrap ?? baseScenario?.replay_bootstrap ?? null,
      }
    : baseScenario;
  writeFileSync(
    environment.replayInputFile,
    buildReplayInputJson(asset.videoPath, scenario, sidecar.observations),
    'utf-8'
  );
}

export function resetE2EState(environment: E2EEnvironment): void {
  clearDirectoryContents(environment.storageDir);
  writeFileSync(environment.settingsFile, buildSettingsToml(environment.storageDir), 'utf-8');

  // installation_state.tomlファイルを作成（YouTube権限ダイアログを承認済みに設定）
  const installationStateFile = join(dirname(environment.settingsFile), 'installation_state.toml');
  writeFileSync(installationStateFile, buildInstallationStateToml(), 'utf-8');

  // lifespan常駐録画はspec間も動作するため、リセット後も実OBSへ戻さない。
  // 個別の録画workflowは、この直後にconfigureReplayAssetで入力を上書きする。
  writeDefaultReplayInput(environment);
}

export function loadSidecarMetadata(asset: ReplayAsset): SidecarMetadata | null {
  if (!asset.sidecarPath) {
    return null;
  }
  const parsed: unknown = JSON.parse(readFileSync(asset.sidecarPath, 'utf-8'));
  if (!isSidecarMetadata(parsed)) {
    throw new Error(`Invalid replay sidecar metadata: ${asset.sidecarPath}`);
  }
  return parsed;
}

function requireSidecarMetadata(asset: ReplayAsset): SidecarMetadata {
  const sidecar = loadSidecarMetadata(asset);
  if (!sidecar) {
    throw new Error(`Replay sidecar metadata was not found for asset: ${asset.name}`);
  }
  return sidecar;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isSidecarMetadata(value: unknown): value is SidecarMetadata {
  if (!isRecord(value) || value.schema_version !== 1) {
    return false;
  }
  if (value.scenario !== null && !isRecord(value.scenario)) {
    return false;
  }
  if (!isReplayObservations(value.observations)) {
    return false;
  }
  return value.expected === null || isRecord(value.expected);
}

const REPLAY_OCR_OBSERVATION_KEYS = [
  'battle_kill',
  'battle_death',
  'battle_special',
  'battle_xp',
  'battle_event_power',
  'battle_kill_record',
] as const satisfies readonly ReplayOcrObservationKey[];

const REPLAY_WEAPON_SLOT_NAMES = [
  'ally_1',
  'ally_2',
  'ally_3',
  'ally_4',
  'enemy_1',
  'enemy_2',
  'enemy_3',
  'enemy_4',
] as const satisfies readonly ReplayWeaponSlotName[];

function isReplayWeaponRecognitionObservation(
  value: unknown
): value is ReplayWeaponRecognitionObservation {
  if (!isRecord(value) || !isRecord(value.display) || !isRecord(value.slots)) {
    return false;
  }
  if (
    typeof value.display.is_visible !== 'boolean' ||
    typeof value.display.should_recognize !== 'boolean'
  ) {
    return false;
  }
  const slots = value.slots;
  if (Object.keys(slots).length !== REPLAY_WEAPON_SLOT_NAMES.length) {
    return false;
  }
  return REPLAY_WEAPON_SLOT_NAMES.every((slot) => {
    const observation = slots[slot];
    return (
      isRecord(observation) &&
      typeof observation.weapon === 'string' &&
      observation.weapon.trim().length > 0 &&
      typeof observation.matched === 'boolean'
    );
  });
}

function isReplayBattleMedalObservation(value: unknown): value is ReplayBattleMedalObservation {
  if (!isRecord(value)) {
    return false;
  }
  const expectedKeys = ['gold', 'silver'];
  if (Object.keys(value).length !== expectedKeys.length) {
    return false;
  }
  return expectedKeys.every((key) => {
    const count = value[key];
    return typeof count === 'number' && Number.isInteger(count) && count >= 0;
  });
}

function isReplayObservations(value: unknown): value is ReplayObservations {
  if (!isRecord(value)) {
    return false;
  }
  if (
    value.weapon_recognition !== undefined &&
    value.weapon_recognition !== null &&
    !isReplayWeaponRecognitionObservation(value.weapon_recognition)
  ) {
    return false;
  }
  if (
    value.battle_medals !== undefined &&
    value.battle_medals !== null &&
    !isReplayBattleMedalObservation(value.battle_medals)
  ) {
    return false;
  }
  if (value.ocr === undefined || value.ocr === null) {
    return true;
  }
  if (!isRecord(value.ocr)) {
    return false;
  }
  return Object.entries(value.ocr).every(
    ([key, observation]) =>
      REPLAY_OCR_OBSERVATION_KEYS.includes(key as ReplayOcrObservationKey) &&
      (typeof observation === 'string' || observation === null)
  );
}

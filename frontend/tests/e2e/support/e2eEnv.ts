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
import { tmpdir } from 'node:os';
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

export type SidecarMetadata = {
  game_mode?: string | null;
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
  scenario?: ReplayScenario | null;
};

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

    const drive = match.groups.drive.toLowerCase();
    const rest = match.groups.rest.replace(/\\/g, '/').replace(/^\/+/, '');
    return `/mnt/${drive}/${rest}`;
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

function buildReplayInputJson(videoPath: string, scenario?: ReplayScenario | null): string {
  return JSON.stringify(
    {
      video_path: videoPath,
      ...(scenario ? { scenario } : {}),
    },
    null,
    2
  );
}

function clearReplayInputFile(replayInputFile: string): void {
  try {
    rmSync(replayInputFile, { force: true, maxRetries: 20, retryDelay: 100 });
  } catch {
    writeFileSync(replayInputFile, buildReplayInputJson(''), 'utf-8');
  }
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

    clearReplayInputFile(environment.replayInputFile);
    process.env[BOOTSTRAP_FLAG] = '1';
  }
  return environment;
}

export function configureReplayAsset(
  environment: E2EEnvironment,
  asset: ReplayAsset,
  scenarioOverride?: ReplayScenario | null
): void {
  const baseScenario = loadSidecarMetadata(asset)?.scenario ?? null;
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
    buildReplayInputJson(asset.videoPath, scenario),
    'utf-8'
  );
}

export function resetE2EState(environment: E2EEnvironment): void {
  clearDirectoryContents(environment.storageDir);
  writeFileSync(environment.settingsFile, buildSettingsToml(environment.storageDir), 'utf-8');

  // installation_state.tomlファイルを作成（YouTube権限ダイアログを承認済みに設定）
  const installationStateFile = join(dirname(environment.settingsFile), 'installation_state.toml');
  writeFileSync(installationStateFile, buildInstallationStateToml(), 'utf-8');

  clearReplayInputFile(environment.replayInputFile);
}

export function loadSidecarMetadata(asset: ReplayAsset): SidecarMetadata | null {
  if (!asset.sidecarPath) {
    return null;
  }
  return JSON.parse(readFileSync(asset.sidecarPath, 'utf-8')) as SidecarMetadata;
}

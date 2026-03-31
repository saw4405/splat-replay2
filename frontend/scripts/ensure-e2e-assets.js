import { execFile as execFileCallback } from 'node:child_process';
import { existsSync } from 'node:fs';
import { open, readdir } from 'node:fs/promises';
import { dirname, relative, resolve } from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

const execFilePromise = promisify(execFileCallback);

export const E2E_ASSET_DIR = 'frontend/tests/fixtures/e2e';
const GIT_LFS_POINTER_HEADER = 'version https://git-lfs.github.com/spec/v1';
const POINTER_READ_BYTES = 256;

/**
 * @param {string} text
 * @returns {boolean}
 */
export function isGitLfsPointerText(text) {
  const normalized = text.replace(/\r\n/g, '\n');
  return (
    normalized.startsWith(`${GIT_LFS_POINTER_HEADER}\n`) &&
    /\noid sha256:[0-9a-f]+\n/i.test(normalized) &&
    /\nsize \d+\n?$/i.test(normalized)
  );
}

/**
 * @param {string} filePath
 * @returns {Promise<string>}
 */
async function readFilePrefix(filePath) {
  const fileHandle = await open(filePath, 'r');
  try {
    const buffer = Buffer.alloc(POINTER_READ_BYTES);
    const { bytesRead } = await fileHandle.read(buffer, 0, buffer.length, 0);
    return buffer.subarray(0, bytesRead).toString('utf8');
  } finally {
    await fileHandle.close();
  }
}

/**
 * @param {string} directory
 * @returns {Promise<string[]>}
 */
async function listMkvFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const fullPath = resolve(directory, entry.name);
      if (entry.isDirectory()) {
        return listMkvFiles(fullPath);
      }
      if (entry.isFile() && entry.name.toLowerCase().endsWith('.mkv')) {
        return [fullPath];
      }
      return [];
    })
  );
  return files.flat();
}

/**
 * @param {{ repoRoot?: string; assetDir?: string }} [options]
 * @returns {Promise<string[]>}
 */
export async function findGitLfsPointerMkvFiles(options = {}) {
  const repoRoot = resolve(options.repoRoot ?? defaultRepoRoot());
  const assetDir = options.assetDir ?? E2E_ASSET_DIR;
  const absoluteAssetDir = resolve(repoRoot, assetDir);
  if (!existsSync(absoluteAssetDir)) {
    return [];
  }

  const mkvFiles = await listMkvFiles(absoluteAssetDir);
  const pointerFiles = [];
  for (const mkvFile of mkvFiles) {
    const prefix = await readFilePrefix(mkvFile);
    if (isGitLfsPointerText(prefix)) {
      pointerFiles.push(relative(repoRoot, mkvFile).replace(/\\/g, '/'));
    }
  }
  return pointerFiles.sort();
}

/**
 * @param {unknown} error
 * @returns {string}
 */
function formatExecError(error) {
  if (error instanceof Error) {
    const stderr = 'stderr' in error && typeof error.stderr === 'string' ? error.stderr.trim() : '';
    const stdout = 'stdout' in error && typeof error.stdout === 'string' ? error.stdout.trim() : '';
    return [stderr, stdout, error.message].find((value) => value.length > 0) ?? error.message;
  }
  return String(error);
}

/**
 * @param {{
 *   repoRoot?: string;
 *   assetDir?: string;
 *   execFile?: (
 *     file: string,
 *     args: string[],
 *     options: { cwd: string }
 *   ) => Promise<{ stdout?: string; stderr?: string }>;
 * }} [options]
 * @returns {Promise<{ fetched: boolean; fetchedFiles: string[] }>}
 */
export async function ensureE2EAssetsAvailable(options = {}) {
  const repoRoot = resolve(options.repoRoot ?? defaultRepoRoot());
  const assetDir = options.assetDir ?? E2E_ASSET_DIR;
  const execFile = options.execFile ?? execFilePromise;
  const pointerFiles = await findGitLfsPointerMkvFiles({ repoRoot, assetDir });

  if (pointerFiles.length === 0) {
    return { fetched: false, fetchedFiles: [] };
  }

  try {
    await execFile('git', ['lfs', 'pull', '--include', assetDir], { cwd: repoRoot });
  } catch (error) {
    throw new Error(
      `E2E 用 replay 動画の取得に失敗しました。Git LFS が利用できるか確認してください: ${formatExecError(error)}`
    );
  }

  const remainingPointerFiles = await findGitLfsPointerMkvFiles({ repoRoot, assetDir });
  if (remainingPointerFiles.length > 0) {
    throw new Error(
      `Git LFS 取得後も E2E 用 replay 動画が実体化されていません: ${remainingPointerFiles.join(', ')}`
    );
  }

  return { fetched: true, fetchedFiles: pointerFiles };
}

/**
 * @returns {string}
 */
function defaultRepoRoot() {
  return resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
}

async function main() {
  const result = await ensureE2EAssetsAvailable();
  if (result.fetched) {
    console.log(`E2E 用 replay 動画を取得しました: ${result.fetchedFiles.join(', ')}`);
    return;
  }
  console.log('E2E 用 replay 動画は取得済みです。');
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    console.error(message);
    process.exitCode = 1;
  });
}

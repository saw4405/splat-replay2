import { afterEach, describe, expect, it, vi } from 'vitest';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const GIT_LFS_POINTER = [
  'version https://git-lfs.github.com/spec/v1',
  'oid sha256:0123456789abcdef',
  'size 123456',
  '',
].join('\n');

function createTempRepo(): {
  repoRoot: string;
  e2eAssetDir: string;
} {
  const repoRoot = mkdtempSync(join(tmpdir(), 'splat-replay-e2e-assets-'));
  const e2eAssetDir = join(repoRoot, 'frontend', 'tests', 'fixtures', 'e2e', 'auto-recording');
  mkdirSync(e2eAssetDir, { recursive: true });
  return { repoRoot, e2eAssetDir };
}

describe('ensure e2e assets', () => {
  const tempDirs: string[] = [];

  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    for (const tempDir of tempDirs.splice(0)) {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it('detects Git LFS pointer text', async () => {
    const { isGitLfsPointerText } = await import('../scripts/ensure-e2e-assets.js');

    expect(isGitLfsPointerText(GIT_LFS_POINTER)).toBe(true);
    expect(isGitLfsPointerText('not an lfs pointer')).toBe(false);
  });

  it('finds mkv pointer files under bundled e2e assets', async () => {
    const { repoRoot, e2eAssetDir } = createTempRepo();
    tempDirs.push(repoRoot);
    writeFileSync(join(e2eAssetDir, 'pointer-video.mkv'), GIT_LFS_POINTER, 'utf-8');
    writeFileSync(join(e2eAssetDir, 'real-video.mkv'), 'real video bytes', 'utf-8');
    writeFileSync(join(e2eAssetDir, 'sidecar.json'), '{}', 'utf-8');

    const { findGitLfsPointerMkvFiles } = await import('../scripts/ensure-e2e-assets.js');

    await expect(findGitLfsPointerMkvFiles({ repoRoot })).resolves.toEqual([
      'frontend/tests/fixtures/e2e/auto-recording/pointer-video.mkv',
    ]);
  });

  it('runs git lfs pull when bundled assets are still pointers', async () => {
    const { repoRoot, e2eAssetDir } = createTempRepo();
    tempDirs.push(repoRoot);
    const pointerFile = join(e2eAssetDir, 'pointer-video.mkv');
    writeFileSync(pointerFile, GIT_LFS_POINTER, 'utf-8');

    const execFile = vi.fn(async () => {
      writeFileSync(pointerFile, 'materialized video bytes', 'utf-8');
      return { stderr: '', stdout: 'pulled' };
    });

    const { ensureE2EAssetsAvailable } = await import('../scripts/ensure-e2e-assets.js');
    const result = await ensureE2EAssetsAvailable({ repoRoot, execFile });

    expect(execFile).toHaveBeenCalledWith(
      'git',
      ['lfs', 'pull', '--include', 'frontend/tests/fixtures/e2e'],
      expect.objectContaining({ cwd: repoRoot })
    );
    expect(result).toEqual({
      fetched: true,
      fetchedFiles: ['frontend/tests/fixtures/e2e/auto-recording/pointer-video.mkv'],
    });
  });

  it('skips git lfs pull when bundled assets are already materialized', async () => {
    const { repoRoot, e2eAssetDir } = createTempRepo();
    tempDirs.push(repoRoot);
    writeFileSync(join(e2eAssetDir, 'real-video.mkv'), 'materialized video bytes', 'utf-8');
    const execFile = vi.fn();

    const { ensureE2EAssetsAvailable } = await import('../scripts/ensure-e2e-assets.js');
    const result = await ensureE2EAssetsAvailable({ repoRoot, execFile });

    expect(execFile).not.toHaveBeenCalled();
    expect(result).toEqual({ fetched: false, fetchedFiles: [] });
  });
});

import { describe, expect, it } from 'vitest';

type CommandResult = {
  status: number;
  stdout?: string;
  stderr?: string;
};

function commandKey(command: string, args: string[]): string {
  return [command, ...args].join('\0');
}

function createHealthyCommands(overrides: Record<string, CommandResult> = {}) {
  const commands: Record<string, CommandResult> = {
    [commandKey('git', ['--version'])]: { status: 0, stdout: 'git version 2.53.0.windows.1\n' },
    [commandKey('git', ['lfs', 'version'])]: { status: 0, stdout: 'git-lfs/3.7.1\n' },
    [commandKey('git', ['config', '--show-origin', '--show-scope', '--get', 'core.hooksPath'])]: {
      status: 0,
      stdout: 'worktree\tfile:C:/repo/splat-replay2/.git/config.worktree\t.githooks\n',
    },
    [commandKey('git', [
      'ls-files',
      '--error-unmatch',
      '.githooks/pre-commit',
      '.githooks/pre-push',
    ])]: {
      status: 0,
      stdout: '.githooks/pre-commit\n.githooks/pre-push\n',
    },
    [commandKey('git', ['status', '--short'])]: { status: 0, stdout: '' },
    [commandKey('uv', ['--version'])]: { status: 0, stdout: 'uv 0.5.29\n' },
    [commandKey('backend/.venv/Scripts/python.exe', ['--version'])]: {
      status: 0,
      stdout: 'Python 3.13.2\n',
    },
    [commandKey('backend/.venv/Scripts/python.exe', ['-m', 'pre_commit', '--version'])]: {
      status: 0,
      stdout: 'pre-commit 4.0.0\n',
    },
    [commandKey('backend/.venv/Scripts/ruff.exe', ['--version'])]: {
      status: 0,
      stdout: 'ruff 0.12.0\n',
    },
    [commandKey('backend/.venv/Scripts/ty.exe', ['--version'])]: {
      status: 0,
      stdout: 'ty 0.0.4\n',
    },
    [commandKey('backend/.venv/Scripts/lint-imports.exe', ['--help'])]: {
      status: 0,
      stdout: 'Usage: lint-imports [OPTIONS]\n',
    },
    [commandKey('node', ['--version'])]: { status: 0, stdout: 'v24.12.0\n' },
    [commandKey('npm', ['--version'])]: { status: 0, stdout: '11.6.2\n' },
    [commandKey('task.exe', ['--version'])]: { status: 0, stdout: '3.45.5\n' },
    ...overrides,
  };
  return async (command: string, args: string[]): Promise<CommandResult> => {
    const result = commands[commandKey(command, args)];
    if (!result) {
      return { status: 127, stderr: `unexpected command: ${command} ${args.join(' ')}` };
    }
    return result;
  };
}

function createHealthyFiles(overrides: Record<string, string | null> = {}) {
  const files: Record<string, string | null> = {
    '.githooks/pre-commit':
      '#!/usr/bin/env sh\nbackend/.venv/Scripts/python.exe -m pre_commit hook-impl --hook-type=pre-commit "$@"\n',
    '.githooks/pre-push':
      '#!/usr/bin/env sh\nbackend/.venv/Scripts/python.exe -m pre_commit hook-impl --hook-type=pre-push "$@"\n',
    'frontend/node_modules/prettier/package.json': '{"version":"3.8.1"}',
    'frontend/node_modules/eslint/package.json': '{"version":"9.39.4"}',
    'frontend/node_modules/svelte-check/package.json': '{"version":"4.4.6"}',
    'frontend/node_modules/vitest/package.json': '{"version":"4.1.2"}',
    ...overrides,
  };
  return {
    exists: async (relativePath: string): Promise<boolean> =>
      files[relativePath] !== null && files[relativePath] !== undefined,
    readText: async (relativePath: string): Promise<string> => {
      const value = files[relativePath];
      if (value === null || value === undefined) {
        throw new Error(`missing file: ${relativePath}`);
      }
      return value;
    },
  };
}

async function runDoctorWith(
  overrides: {
    commands?: Record<string, CommandResult>;
    files?: Record<string, string | null>;
    pointerFiles?: string[];
  } = {}
) {
  const { runDoctor } = await import('../../scripts/dev-doctor.mjs');
  const files = createHealthyFiles(overrides.files);
  return runDoctor({
    repoRoot: 'C:/repo/splat-replay2',
    runCommand: createHealthyCommands(overrides.commands),
    fileExists: files.exists,
    readTextFile: files.readText,
    ensureWritableDirectory: async () => undefined,
    findGitLfsPointerMkvFiles: async () => overrides.pointerFiles ?? [],
  });
}

describe('dev doctor', () => {
  it('fails when core.hooksPath is missing', async () => {
    const report = await runDoctorWith({
      commands: {
        [commandKey('git', ['config', '--show-origin', '--show-scope', '--get', 'core.hooksPath'])]:
          { status: 1, stdout: '' },
      },
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'git-hooks-path', status: 'fail' })
    );
  });

  it('fails when core.hooksPath is set in shared repo config', async () => {
    const report = await runDoctorWith({
      commands: {
        [commandKey('git', ['config', '--show-origin', '--show-scope', '--get', 'core.hooksPath'])]:
          {
            status: 0,
            stdout: 'local\tfile:C:/repo/splat-replay2/.git/config\t.githooks\n',
          },
      },
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'git-hooks-path', status: 'fail' })
    );
  });

  it('fails when tracked hook launchers contain checkout-specific absolute paths', async () => {
    const report = await runDoctorWith({
      files: {
        '.githooks/pre-commit':
          "INSTALL_PYTHON='C:\\Users\\someone\\repo\\splat-replay2\\backend\\.venv\\Scripts\\python.exe'\n",
      },
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'git-hooks-launcher', status: 'fail' })
    );
  });

  it('fails when hook launchers exist but are not tracked by Git', async () => {
    const report = await runDoctorWith({
      commands: {
        [commandKey('git', [
          'ls-files',
          '--error-unmatch',
          '.githooks/pre-commit',
          '.githooks/pre-push',
        ])]: {
          status: 1,
          stderr: "error: pathspec '.githooks/pre-commit' did not match any file(s) known to git\n",
        },
      },
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'git-hooks-launcher', status: 'fail' })
    );
  });

  it('fails when backend venv Python cannot start', async () => {
    const report = await runDoctorWith({
      commands: {
        [commandKey('backend/.venv/Scripts/python.exe', ['--version'])]: {
          status: 1,
          stderr: 'Unable to create process',
        },
      },
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'backend-python', status: 'fail' })
    );
  });

  it('fails when a required frontend local tool is missing', async () => {
    const report = await runDoctorWith({
      files: {
        'frontend/node_modules/prettier/package.json': null,
      },
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'frontend-prettier', status: 'fail' })
    );
  });

  it('fails when a required backend hook tool is missing', async () => {
    const report = await runDoctorWith({
      commands: {
        [commandKey('backend/.venv/Scripts/ruff.exe', ['--version'])]: {
          status: 1,
          stderr: 'file not found',
        },
      },
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'backend-ruff', status: 'fail' })
    );
  });

  it('fails when Git LFS assets are still pointers', async () => {
    const report = await runDoctorWith({
      pointerFiles: ['frontend/tests/fixtures/e2e/auto-recording/pointer-video.mkv'],
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'lfs-assets', status: 'fail' })
    );
  });

  it('classifies a dirty worktree as a warning, not an environment failure', async () => {
    const report = await runDoctorWith({
      commands: {
        [commandKey('git', ['status', '--short'])]: {
          status: 0,
          stdout: ' M docs/DEVELOPMENT.md\n',
        },
      },
    });

    expect(report.status).toBe('warn');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'git-worktree-clean', status: 'warn' })
    );
  });

  it('fails when normal git status fails before returning worktree state', async () => {
    const report = await runDoctorWith({
      commands: {
        [commandKey('git', ['status', '--short'])]: {
          status: 1,
          stderr: "fatal: clean filter 'lfs' failed",
        },
      },
    });

    expect(report.status).toBe('fail');
    expect(report.checks).toContainEqual(
      expect.objectContaining({ id: 'git-status', status: 'fail' })
    );
  });
});

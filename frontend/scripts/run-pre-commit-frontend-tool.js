import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { dirname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(scriptDir, '..', '..');
const frontendRoot = resolve(repoRoot, 'frontend');

function normalizeFrontendPaths(filePaths) {
  return [
    ...new Set(
      filePaths
        .map((filePath) => {
          const absolutePath = resolve(repoRoot, filePath);
          const frontendRelativePath = relative(frontendRoot, absolutePath);
          if (frontendRelativePath === '..' || frontendRelativePath.startsWith(`..${sep}`)) {
            return null;
          }
          return frontendRelativePath.replace(/\\/g, '/');
        })
        .filter((filePath) => filePath !== null)
    ),
  ];
}

async function resolvePackageBin(packageName, binName) {
  const packageJsonPath = resolve(frontendRoot, 'node_modules', packageName, 'package.json');
  const packageJson = JSON.parse(await readFile(packageJsonPath, 'utf8'));
  if (typeof packageJson.bin === 'string') {
    return resolve(frontendRoot, 'node_modules', packageName, packageJson.bin);
  }

  const relativeBinPath = packageJson.bin?.[binName];
  if (typeof relativeBinPath !== 'string') {
    throw new Error(`Could not resolve bin "${binName}" for package "${packageName}".`);
  }
  return resolve(frontendRoot, 'node_modules', packageName, relativeBinPath);
}

async function buildCommand(toolName, filePaths) {
  const nodeCommand = process.execPath;
  switch (toolName) {
    case 'prettier-check':
      return {
        command: nodeCommand,
        args: [
          await resolvePackageBin('prettier', 'prettier'),
          '--check',
          '--ignore-unknown',
          ...filePaths,
        ],
      };
    case 'eslint':
      return {
        command: nodeCommand,
        args: [
          await resolvePackageBin('eslint', 'eslint'),
          '--no-warn-ignored',
          '--ext',
          '.ts,.svelte',
          ...filePaths,
        ],
      };
    default:
      throw new Error(`Unsupported frontend pre-commit tool: ${toolName}`);
  }
}

async function main() {
  const toolName = process.argv[2];
  if (!toolName) {
    throw new Error('Tool name is required.');
  }

  // pre-commit passes repo-root-relative paths, so convert them before
  // invoking frontend-local tooling and configuration.
  const filePaths = normalizeFrontendPaths(process.argv.slice(3));
  if (filePaths.length === 0) {
    return;
  }

  const { command, args } = await buildCommand(toolName, filePaths);
  await new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, args, {
      cwd: frontendRoot,
      stdio: 'inherit',
    });
    child.on('error', rejectPromise);
    child.on('exit', (code, signal) => {
      if (signal) {
        rejectPromise(new Error(`Frontend hook exited with signal: ${signal}`));
        return;
      }
      if (code !== 0) {
        process.exitCode = code ?? 1;
      }
      resolvePromise();
    });
  });
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(message);
  process.exitCode = 1;
});

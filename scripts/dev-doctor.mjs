import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { findGitLfsPointerMkvFiles } from "../frontend/scripts/ensure-e2e-assets.js";

const FRONTEND_TOOLS = ["prettier", "eslint", "svelte-check", "vitest"];
const BACKEND_TOOLS = [
  ["backend-ruff", "backend ruff", "backend/.venv/Scripts/ruff.exe", ["--version"]],
  ["backend-ty", "backend ty", "backend/.venv/Scripts/ty.exe", ["--version"]],
  [
    "backend-import-lint",
    "backend import-lint",
    "backend/.venv/Scripts/lint-imports.exe",
    ["--help"],
  ],
];
const HOOKS_PATH = ".githooks";
const HOOK_FILES = [".githooks/pre-commit", ".githooks/pre-push"];
const PRE_COMMIT_HOME = ".pre-commit-cache";
const VIRTUALENV_APP_DATA = ".pre-commit-cache/virtualenv-app-data";
const CHECKOUT_SPECIFIC_PATTERN =
  /(?:INSTALL_PYTHON|[A-Za-z]:[\\/]|\\\\Users\\\\|\/mnt\/[a-z]\/Users\/)/i;

/**
 * @typedef {'pass' | 'warn' | 'fail'} CheckStatus
 * @typedef {{ id: string; name: string; status: CheckStatus; message: string; details?: string }} DoctorCheck
 * @typedef {{ status: CheckStatus; checks: DoctorCheck[] }} DoctorReport
 * @typedef {{ status: number; stdout?: string; stderr?: string }} CommandResult
 */

function defaultRepoRoot() {
  return resolve(dirname(fileURLToPath(import.meta.url)), "..");
}

function makeCheck(id, name, status, message, details = undefined) {
  return { id, name, status, message, ...(details ? { details } : {}) };
}

function summarizeStatus(checks) {
  if (checks.some((check) => check.status === "fail")) {
    return "fail";
  }
  if (checks.some((check) => check.status === "warn")) {
    return "warn";
  }
  return "pass";
}

function commandOutput(result) {
  return [result.stderr?.trim(), result.stdout?.trim()]
    .filter(Boolean)
    .join("\n");
}

async function defaultRunCommand(command, args, options = {}) {
  return new Promise((resolvePromise) => {
    const executable =
      process.platform === "win32" && command === "npm" ? "cmd.exe" : command;
    const executableArgs =
      process.platform === "win32" && command === "npm"
        ? ["/d", "/s", "/c", "npm.cmd", ...args]
        : args;
    const child = spawn(executable, executableArgs, {
      cwd: options.cwd,
      env: {
        ...process.env,
        UV_CACHE_DIR:
          process.env.UV_CACHE_DIR ?? resolve(options.cwd, ".uv-cache"),
        UV_PYTHON_INSTALL_DIR:
          process.env.UV_PYTHON_INSTALL_DIR ??
          resolve(options.cwd, ".uv-python"),
        PRE_COMMIT_HOME:
          process.env.PRE_COMMIT_HOME ??
          resolve(options.cwd, PRE_COMMIT_HOME),
        VIRTUALENV_OVERRIDE_APP_DATA:
          process.env.VIRTUALENV_OVERRIDE_APP_DATA ??
          resolve(options.cwd, VIRTUALENV_APP_DATA),
      },
      shell: false,
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    child.stdout?.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      resolvePromise({ status: 127, stderr: error.message });
    });
    child.on("close", (code) => {
      resolvePromise({ status: code ?? 1, stdout, stderr });
    });
  });
}

async function checkCommand(id, name, command, args, runCommand, repoRoot) {
  const result = await runCommand(command, args, { cwd: repoRoot });
  if (result.status !== 0) {
    return makeCheck(
      id,
      name,
      "fail",
      `${command} ${args.join(" ")} failed`,
      commandOutput(result),
    );
  }
  return makeCheck(
    id,
    name,
    "pass",
    commandOutput(result) || `${command} is available`,
  );
}

function parseGitConfigShowOriginLine(output) {
  const line = output.trim().split(/\r?\n/).at(-1) ?? "";
  const tabParts = line.split("\t");
  if (tabParts.length >= 3) {
    return {
      scope: tabParts[0],
      origin: tabParts[1],
      value: tabParts.slice(2).join("\t").trim(),
    };
  }

  return { scope: "", origin: "", value: line.trim() };
}

async function checkFrontendPackage(toolName, fileExists, readTextFile) {
  const id = `frontend-${toolName}`;
  const packageJsonPath = `frontend/node_modules/${toolName}/package.json`;
  if (!(await fileExists(packageJsonPath))) {
    return makeCheck(
      id,
      `frontend ${toolName}`,
      "fail",
      `${packageJsonPath} is missing`,
    );
  }

  try {
    const packageJson = JSON.parse(await readTextFile(packageJsonPath));
    const version =
      typeof packageJson.version === "string"
        ? packageJson.version
        : "unknown version";
    return makeCheck(
      id,
      `frontend ${toolName}`,
      "pass",
      `${toolName} ${version}`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return makeCheck(
      id,
      `frontend ${toolName}`,
      "fail",
      `${packageJsonPath} is unreadable`,
      message,
    );
  }
}

async function checkGitHooksPath(runCommand, repoRoot) {
  const result = await runCommand(
    "git",
    ["config", "--show-origin", "--show-scope", "--get", "core.hooksPath"],
    { cwd: repoRoot },
  );
  const { origin, value: hooksPath } = parseGitConfigShowOriginLine(
    result.stdout ?? "",
  );
  if (result.status !== 0 || hooksPath.length === 0) {
    return makeCheck(
      "git-hooks-path",
      "Git hooks path",
      "fail",
      "core.hooksPath is not set to .githooks",
    );
  }
  if (hooksPath.replace(/\\/g, "/") !== HOOKS_PATH) {
    return makeCheck(
      "git-hooks-path",
      "Git hooks path",
      "fail",
      `core.hooksPath is ${hooksPath}; expected ${HOOKS_PATH}`,
    );
  }
  if (!origin.replace(/\\/g, "/").endsWith("config.worktree")) {
    return makeCheck(
      "git-hooks-path",
      "Git hooks path",
      "fail",
      "core.hooksPath must be set in this worktree config, not shared repo config",
      origin || result.stdout?.trim(),
    );
  }
  return makeCheck(
    "git-hooks-path",
    "Git hooks path",
    "pass",
    `core.hooksPath=${HOOKS_PATH}`,
  );
}

async function checkWritableRepoDirectory(
  id,
  name,
  relativePath,
  repoRoot,
  ensureWritableDirectory,
) {
  try {
    await ensureWritableDirectory(relativePath, repoRoot);
    return makeCheck(id, name, "pass", `${relativePath} is writable`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return makeCheck(
      id,
      name,
      "fail",
      `${relativePath} is not writable`,
      message,
    );
  }
}

async function defaultEnsureWritableDirectory(relativePath, repoRoot) {
  const directory = resolve(repoRoot, relativePath);
  await mkdir(directory, { recursive: true });
  const probePath = resolve(
    directory,
    `.doctor-write-test-${process.pid}-${Date.now()}`,
  );
  await writeFile(probePath, "ok", "utf8");
  await rm(probePath, { force: true });
}

async function checkGitHookLaunchers(
  fileExists,
  readTextFile,
  runCommand,
  repoRoot,
) {
  const missingHooks = [];
  const checkoutSpecificHooks = [];
  const trackedResult = await runCommand(
    "git",
    ["ls-files", "--error-unmatch", ...HOOK_FILES],
    { cwd: repoRoot },
  );

  if (trackedResult.status !== 0) {
    return makeCheck(
      "git-hooks-launcher",
      "Git hook launchers",
      "fail",
      `hook launcher(s) must be tracked by Git: ${HOOK_FILES.join(", ")}`,
      commandOutput(trackedResult),
    );
  }

  for (const hookFile of HOOK_FILES) {
    if (!(await fileExists(hookFile))) {
      missingHooks.push(hookFile);
      continue;
    }
    const content = await readTextFile(hookFile);
    if (CHECKOUT_SPECIFIC_PATTERN.test(content)) {
      checkoutSpecificHooks.push(hookFile);
    }
  }

  if (missingHooks.length > 0) {
    return makeCheck(
      "git-hooks-launcher",
      "Git hook launchers",
      "fail",
      `missing tracked hook launcher(s): ${missingHooks.join(", ")}`,
    );
  }
  if (checkoutSpecificHooks.length > 0) {
    return makeCheck(
      "git-hooks-launcher",
      "Git hook launchers",
      "fail",
      `hook launcher(s) contain checkout-specific paths: ${checkoutSpecificHooks.join(", ")}`,
    );
  }
  return makeCheck(
    "git-hooks-launcher",
    "Git hook launchers",
    "pass",
    "tracked hook launchers are portable",
  );
}

async function checkGitStatus(runCommand, repoRoot) {
  const result = await runCommand("git", ["status", "--short"], {
    cwd: repoRoot,
  });
  if (result.status !== 0) {
    return [
      makeCheck(
        "git-status",
        "Git status",
        "fail",
        "git status failed before returning worktree state",
        commandOutput(result),
      ),
    ];
  }
  const statusText = result.stdout?.trim() ?? "";
  if (statusText.length > 0) {
    return [
      makeCheck("git-status", "Git status", "pass", "git status completed"),
      makeCheck(
        "git-worktree-clean",
        "Worktree cleanliness",
        "warn",
        "worktree has local changes",
        statusText,
      ),
    ];
  }
  return [
    makeCheck("git-status", "Git status", "pass", "git status completed"),
    makeCheck(
      "git-worktree-clean",
      "Worktree cleanliness",
      "pass",
      "worktree is clean",
    ),
  ];
}

async function checkLfsAssets(repoRoot, findPointerFiles) {
  try {
    const pointerFiles = await findPointerFiles({ repoRoot });
    if (pointerFiles.length > 0) {
      return makeCheck(
        "lfs-assets",
        "Git LFS assets",
        "fail",
        "bundled E2E replay assets are still Git LFS pointers",
        pointerFiles.join("\n"),
      );
    }
    return makeCheck(
      "lfs-assets",
      "Git LFS assets",
      "pass",
      "bundled E2E replay assets are materialized",
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return makeCheck(
      "lfs-assets",
      "Git LFS assets",
      "fail",
      "failed to inspect bundled E2E replay assets",
      message,
    );
  }
}

/**
 * @param {{
 *   repoRoot?: string;
 *   runCommand?: (command: string, args: string[], options: { cwd: string }) => Promise<CommandResult>;
 *   fileExists?: (relativePath: string) => Promise<boolean>;
 *   readTextFile?: (relativePath: string) => Promise<string>;
 *   ensureWritableDirectory?: (relativePath: string, repoRoot: string) => Promise<void>;
 *   findGitLfsPointerMkvFiles?: (options: { repoRoot: string }) => Promise<string[]>;
 * }} options
 * @returns {Promise<DoctorReport>}
 */
export async function runDoctor(options = {}) {
  const repoRoot = resolve(options.repoRoot ?? defaultRepoRoot());
  const runCommand = options.runCommand ?? defaultRunCommand;
  const fileExists =
    options.fileExists ??
    (async (relativePath) => existsSync(resolve(repoRoot, relativePath)));
  const readTextFile =
    options.readTextFile ??
    (async (relativePath) => readFile(resolve(repoRoot, relativePath), "utf8"));
  const ensureWritableDirectory =
    options.ensureWritableDirectory ?? defaultEnsureWritableDirectory;
  const findPointerFiles =
    options.findGitLfsPointerMkvFiles ?? findGitLfsPointerMkvFiles;

  const checks = [];
  checks.push(
    await checkCommand(
      "git",
      "Git",
      "git",
      ["--version"],
      runCommand,
      repoRoot,
    ),
  );
  checks.push(
    await checkWritableRepoDirectory(
      "pre-commit-cache",
      "pre-commit cache",
      PRE_COMMIT_HOME,
      repoRoot,
      ensureWritableDirectory,
    ),
  );
  checks.push(
    await checkWritableRepoDirectory(
      "virtualenv-app-data",
      "virtualenv app data",
      VIRTUALENV_APP_DATA,
      repoRoot,
      ensureWritableDirectory,
    ),
  );
  for (const [id, name, command, args] of BACKEND_TOOLS) {
    checks.push(await checkCommand(id, name, command, args, runCommand, repoRoot));
  }
  checks.push(
    await checkCommand(
      "git-lfs",
      "Git LFS",
      "git",
      ["lfs", "version"],
      runCommand,
      repoRoot,
    ),
  );
  checks.push(await checkGitHooksPath(runCommand, repoRoot));
  checks.push(
    await checkGitHookLaunchers(fileExists, readTextFile, runCommand, repoRoot),
  );
  checks.push(...(await checkGitStatus(runCommand, repoRoot)));
  checks.push(
    await checkCommand("uv", "uv", "uv", ["--version"], runCommand, repoRoot),
  );
  checks.push(
    await checkCommand(
      "backend-python",
      "backend Python",
      "backend/.venv/Scripts/python.exe",
      ["--version"],
      runCommand,
      repoRoot,
    ),
  );
  checks.push(
    await checkCommand(
      "backend-pre-commit",
      "backend pre-commit",
      "backend/.venv/Scripts/python.exe",
      ["-m", "pre_commit", "--version"],
      runCommand,
      repoRoot,
    ),
  );
  checks.push(
    await checkCommand(
      "node",
      "Node.js",
      "node",
      ["--version"],
      runCommand,
      repoRoot,
    ),
  );
  checks.push(
    await checkCommand(
      "npm",
      "npm",
      "npm",
      ["--version"],
      runCommand,
      repoRoot,
    ),
  );
  checks.push(
    await checkCommand(
      "task",
      "Task",
      "task.exe",
      ["--version"],
      runCommand,
      repoRoot,
    ),
  );
  for (const toolName of FRONTEND_TOOLS) {
    checks.push(await checkFrontendPackage(toolName, fileExists, readTextFile));
  }
  checks.push(await checkLfsAssets(repoRoot, findPointerFiles));

  return { status: summarizeStatus(checks), checks };
}

export function formatTextReport(report) {
  const lines = [`Checkout diagnostics: ${report.status.toUpperCase()}`];
  for (const check of report.checks) {
    lines.push(`[${check.status}] ${check.name}: ${check.message}`);
    if (check.details) {
      lines.push(`  ${check.details.replace(/\n/g, "\n  ")}`);
    }
  }
  return `${lines.join("\n")}\n`;
}

async function main() {
  const json = process.argv.includes("--json");
  const report = await runDoctor();
  if (json) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    process.stdout.write(formatTextReport(report));
  }
  if (report.status === "fail") {
    process.exitCode = 1;
  }
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    console.error(message);
    process.exitCode = 1;
  });
}

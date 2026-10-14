#!/usr/bin/env sh
set -eu

if [ "${1:-}" = "1" ]; then
  echo "WARNING: SKIP_HOOKS=1 のため Git hooks 初期化をスキップしました。"
  exit 0
fi

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"
git config extensions.worktreeConfig true

shared_hooks_path=$(git config --local --get core.hooksPath || true)
if [ "$shared_hooks_path" = ".githooks" ]; then
  git config --local --unset core.hooksPath
fi
git config --worktree core.hooksPath .githooks

python=backend/.venv/bin/python
if [ ! -x "$python" ]; then
  echo "backend venv Python が見つかりません: $python" >&2
  exit 1
fi

export PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-$repo_root/.pre-commit-cache}"
export VIRTUALENV_OVERRIDE_APP_DATA="${VIRTUALENV_OVERRIDE_APP_DATA:-$PRE_COMMIT_HOME/virtualenv-app-data}"
mkdir -p "$PRE_COMMIT_HOME" "$VIRTUALENV_OVERRIDE_APP_DATA"
"$python" -m pre_commit install-hooks --config .pre-commit-config.yaml

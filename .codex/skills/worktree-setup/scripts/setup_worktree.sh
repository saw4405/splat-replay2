#!/usr/bin/env bash
set -euo pipefail

branch_name=""
base_ref="HEAD"
worktree_root=""
install_cmd=""
skip_install=0
dry_run=0

declare -a copy_lists=()

usage() {
  cat <<'EOF'
Usage:
  setup_worktree.sh --branch <branch-name> [options]

Options:
  --branch <name>         Branch name (required)
  --base <ref>            Base ref when creating a new branch (default: HEAD)
  --worktree-root <path>  Root directory for worktrees (default: <repo>.worktrees beside repo)
  --copy-list <path>      Extra copy list file (repeatable)
  --install-cmd <command> Command used for initial setup
  --skip-install          Skip initial setup command
  --dry-run               Show planned commands only
  -h, --help              Show help
EOF
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

log() {
  printf '[worktree-setup] %s\n' "$*"
}

warn() {
  printf '[worktree-setup][warn] %s\n' "$*" >&2
}

die() {
  printf '[worktree-setup][error] %s\n' "$*" >&2
  exit 1
}

run_cmd() {
  if ((dry_run)); then
    printf '[dry-run]'
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n'
    return 0
  fi
  "$@"
}

run_shell() {
  local command="$1"
  if ((dry_run)); then
    printf '[dry-run] bash -lc %q\n' "$command"
    return 0
  fi
  bash -lc "$command"
}

resolve_absolute_path() {
  local target="$1"
  if command -v realpath >/dev/null 2>&1; then
    realpath -m "$target"
    return 0
  fi

  case "$target" in
    /*) printf '%s\n' "$target" ;;
    *) printf '%s/%s\n' "$(pwd -P)" "$target" ;;
  esac
}

# Convert Unix-style or WSL paths to Windows absolute paths (C:\Users\... format)
# This is essential for --no-relative-paths to work correctly across different shells
# Examples:
#   /mnt/c/Users/foo       -> C:\Users\foo       (WSL)
#   /c/Users/foo           -> C:\Users\foo       (Git Bash without cygpath)
#   C:\Users\foo           -> C:\Users\foo       (already Windows format)
convert_to_windows_path() {
  local path="$1"
  
  # WSL: use wslpath
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -w "$path"
    return 0
  fi
  
  # Git Bash/MSYS2/Cygwin: use cygpath
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$path"
    return 0
  fi
  
  # Native Windows or path is already Windows-style: ensure it's absolute
  case "$path" in
    [A-Za-z]:*)
      # Already Windows absolute path (C:\..., D:\..., etc.)
      printf '%s\n' "$path"
      return 0
      ;;
    /[A-Za-z]/*)
      # Git Bash style without cygpath: /c/Users/... -> C:\Users\...
      local drive="${path:1:1}"
      local rest="${path:3}"
      printf '%s:\\%s\n' "${drive^^}" "${rest//\//\\}"
      return 0
      ;;
    *)
      # Fallback: return as-is
      printf '%s\n' "$path"
      return 0
      ;;
  esac
}

# Detect which git binary to use
# Prefers git.exe in WSL for consistency with Windows paths in --no-relative-paths mode
detect_git_binary() {
  # Prefer Windows native git.exe in WSL environment for better compatibility
  if command -v wslpath >/dev/null 2>&1 && command -v git.exe >/dev/null 2>&1; then
    printf 'git.exe'
    return 0
  fi
  
  # Use system git
  printf 'git'
  return 0
}

supports_no_relative_paths() {
  local git_bin="$1"
  local help_text
  help_text="$("$git_bin" worktree add -h 2>&1 || true)"
  grep -Eq -- "--(\\[no-\\])?relative-paths|--no-relative-paths" <<<"$help_text"
}

validate_worktree_root() {
  local path="$1"
  local normalized_path
  normalized_path="$(resolve_absolute_path "$path")"
  
  # Prevent worktree creation in dangerous system directories
  case "$normalized_path" in
    /|/etc|/etc/*|/usr|/usr/*|/bin|/bin/*|/sbin|/sbin/*|/boot|/boot/*|/sys|/sys/*|/proc|/proc/*)
      die "dangerous worktree root: $normalized_path (system directory)"
      ;;
    /tmp|/tmp/*)
      warn "worktree root in temporary directory: $normalized_path"
      ;;
  esac
  
  # On Windows/WSL, also check Windows system paths (via wslpath if available)
  if command -v wslpath >/dev/null 2>&1; then
    local windows_path
    windows_path="$(wslpath -w "$normalized_path" 2>/dev/null || echo "")"
    case "$windows_path" in
      C:\\Windows\\*|C:\\Program\ Files\\*|C:\\Program\ Files\ \(x86\)\\*)
        die "dangerous worktree root: $windows_path (Windows system directory)"
        ;;
    esac
  fi
}

parse_args() {
  while (($# > 0)); do
    case "$1" in
      --branch)
        [[ $# -ge 2 ]] || die "--branch requires a value"
        branch_name="$2"
        shift 2
        ;;
      --base)
        [[ $# -ge 2 ]] || die "--base requires a value"
        base_ref="$2"
        shift 2
        ;;
      --worktree-root)
        [[ $# -ge 2 ]] || die "--worktree-root requires a value"
        worktree_root="$2"
        shift 2
        ;;
      --copy-list)
        [[ $# -ge 2 ]] || die "--copy-list requires a value"
        copy_lists+=("$2")
        shift 2
        ;;
      --install-cmd)
        [[ $# -ge 2 ]] || die "--install-cmd requires a value"
        install_cmd="$2"
        shift 2
        ;;
      --skip-install)
        skip_install=1
        shift
        ;;
      --dry-run)
        dry_run=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done
}

copy_non_tracked_files() {
  local repo_root="$1"
  local worktree_path="$2"
  local copied=0
  local skipped_tracked=0
  local skipped_missing=0
  local failed=0

  declare -A seen_paths=()
  local list_file

  for list_file in "${copy_lists[@]}"; do
    if [[ ! -f "$list_file" ]]; then
      warn "copy list not found: $list_file"
      continue
    fi

    while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
      local line
      line="$(trim "${raw_line%%#*}")"
      [[ -n "$line" ]] || continue

      local -a matches=()
      # compgen -G returns exit code 1 when no matches found, which is expected behavior
      mapfile -t matches < <(cd "$repo_root" && compgen -G "$line" || true)

      if ((${#matches[@]} == 0)); then
        ((skipped_missing += 1))
        continue
      fi

      local relative_path
      for relative_path in "${matches[@]}"; do
        relative_path="${relative_path#./}"

        if [[ -n "${seen_paths[$relative_path]:-}" ]]; then
          continue
        fi
        seen_paths["$relative_path"]=1

        if git -C "$repo_root" ls-files --error-unmatch -- "$relative_path" >/dev/null 2>&1; then
          ((skipped_tracked += 1))
          continue
        fi

        local src="$repo_root/$relative_path"
        local dest="$worktree_path/$relative_path"

        if ! run_cmd mkdir -p "$(dirname "$dest")"; then
          warn "failed to create directory for: $relative_path"
          ((failed += 1))
          continue
        fi
        
        if ! run_cmd cp -a "$src" "$dest"; then
          warn "failed to copy file: $relative_path"
          ((failed += 1))
          continue
        fi
        
        ((copied += 1))
      done
    done <"$list_file"
  done

  log "copied non-tracked paths: $copied"
  log "skipped tracked paths: $skipped_tracked"
  log "patterns with no matches: $skipped_missing"
  
  if ((failed > 0)); then
    warn "failed to copy $failed file(s)"
  fi
}

open_vscode_new_window() {
  local worktree_path="$1"
  local windows_path="$worktree_path"
  
  # Convert WSL path to Windows path if needed
  if command -v wslpath >/dev/null 2>&1; then
    windows_path="$(wslpath -w "$worktree_path")"
  fi
  
  # On WSL, prefer cmd.exe /C to avoid batch file parsing issues
  if command -v cmd.exe >/dev/null 2>&1 && cmd.exe /C where code.cmd >/dev/null 2>&1; then
    log "opening worktree in new VS Code window: $worktree_path"
    if ! run_cmd cmd.exe /C code.cmd --new-window "$windows_path"; then
      warn "failed to open worktree in new VS Code window"
      return 1
    fi
  elif command -v code.cmd >/dev/null 2>&1; then
    log "opening worktree in new VS Code window: $worktree_path"
    if ! run_cmd code.cmd --new-window "$windows_path"; then
      warn "failed to open worktree in new VS Code window"
      return 1
    fi
  else
    warn "VS Code launcher (code.cmd) not found, skipped opening editor"
    return 1
  fi
  
  return 0
}

main() {
  parse_args "$@"

  [[ -n "$branch_name" ]] || die "--branch is required"

  git check-ref-format --branch "$branch_name" >/dev/null 2>&1 || die "invalid branch name: $branch_name"

  local repo_root
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [[ -n "$repo_root" ]] || die "must run inside a git repository"

  local repo_name
  repo_name="$(basename "$repo_root")"

  if [[ -z "$worktree_root" ]]; then
    worktree_root="$(dirname "$repo_root")/${repo_name}.worktrees"
  fi
  worktree_root="$(resolve_absolute_path "$worktree_root")"
  
  # Validate worktree root to prevent creation in dangerous directories
  validate_worktree_root "$worktree_root"

  # VS Code default style: feature/foo -> feature-foo
  local worktree_name="${branch_name//\//-}"
  local worktree_path="${worktree_root}/${worktree_name}"
  if [[ -e "$worktree_path" ]]; then
    die "worktree path already exists: $worktree_path"
  fi

  local branch_exists=0
  if git -C "$repo_root" show-ref --verify --quiet "refs/heads/$branch_name"; then
    branch_exists=1
  else
    git -C "$repo_root" rev-parse --verify --quiet "${base_ref}^{commit}" >/dev/null \
      || die "base ref not found: $base_ref"
  fi

  run_cmd mkdir -p "$worktree_root"

  local git_add_bin
  git_add_bin="$(detect_git_binary)"
  
  local repo_root_for_add="$repo_root"
  local worktree_path_for_add="$worktree_path"
  local use_windows_paths=0

  # ============================================================================
  # Worktree creation strategy:
  # 1. Check if git supports --no-relative-paths flag (Git 2.15+)
  # 2. If supported, convert paths to Windows absolute format (C:\Users\...)
  # 3. Use --no-relative-paths to store absolute paths in .git/worktrees/<name>/gitdir
  #
  # Why this matters:
  # - Without --no-relative-paths, Git stores relative paths which can break
  #   when accessing the worktree from different shells (Git Bash, WSL, PowerShell)
  # - Windows absolute paths work consistently across all Windows-based environments
  # - This prevents "prunable" worktrees and gitdir pointing to non-existent locations
  # ============================================================================
  
  local supports_no_relative=0
  if supports_no_relative_paths "$git_add_bin"; then
    supports_no_relative=1
    # When using --no-relative-paths, prefer Windows absolute paths for better compatibility
    # This ensures .git/worktrees/<name>/gitdir contains Windows-native paths
    if [[ "$git_add_bin" == "git.exe" ]] || command -v wslpath >/dev/null 2>&1 || command -v cygpath >/dev/null 2>&1; then
      use_windows_paths=1
      repo_root_for_add="$(convert_to_windows_path "$repo_root")"
      worktree_path_for_add="$(convert_to_windows_path "$worktree_path")"
      log "using Windows absolute paths with --no-relative-paths for worktree add"
      log "  repo: $repo_root_for_add"
      log "  worktree: $worktree_path_for_add"
    fi
  else
    warn "git does not support --no-relative-paths; using absolute path without flag"
  fi

  local -a worktree_add_cmd=("$git_add_bin" -C "$repo_root_for_add" worktree add)
  if ((supports_no_relative)); then
    worktree_add_cmd+=(--no-relative-paths)
  fi

  if ((branch_exists)); then
    run_cmd "${worktree_add_cmd[@]}" "$worktree_path_for_add" "$branch_name"
  else
    run_cmd "${worktree_add_cmd[@]}" -b "$branch_name" "$worktree_path_for_add" "$base_ref"
  fi

  local repo_local_copy_list="${repo_root}/.worktree-copy-paths"
  local -a resolved_copy_lists=()

  if [[ -f "$repo_local_copy_list" ]]; then
    resolved_copy_lists+=("$repo_local_copy_list")
    log "using repository copy list: $repo_local_copy_list"
  fi

  if ((${#copy_lists[@]} > 0)); then
    resolved_copy_lists+=("${copy_lists[@]}")
  fi
  copy_lists=("${resolved_copy_lists[@]}")

  if ((${#copy_lists[@]} == 0)); then
    die "no copy list resolved. create .worktree-copy-paths or pass --copy-list"
  fi
  copy_non_tracked_files "$repo_root" "$worktree_path"

  if ((skip_install)); then
    log "initial setup skipped (--skip-install)"
  else
    if [[ -z "$install_cmd" ]]; then
      if command -v task.exe >/dev/null 2>&1; then
        install_cmd="task.exe install"
      elif command -v task >/dev/null 2>&1; then
        install_cmd="task install"
      else
        warn "task command not found, skipped install step"
        install_cmd=""
      fi
    fi

    if [[ -n "$install_cmd" ]]; then
      log "running initial setup: $install_cmd"
      (
        cd "$worktree_path"
        run_shell "$install_cmd"
      )
    fi
  fi

  open_vscode_new_window "$worktree_path" || true
  log "worktree ready: $worktree_path"
}

main "$@"

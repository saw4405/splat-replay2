# GitHub Release Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** このリポジトリ専用の GitHub Release 作成スキルを追加し、`1.2.3` 入力から `v1.2.3` の draft release とビルド zip 添付を安全に実行できるようにし、引数なしなら前回リリースから次バージョン候補を提案できるようにする。

**Architecture:** リリースノート本文の検討と草案化、ならびに候補バージョンの推奨判断はエージェントが担当し、Python 補助スクリプトはリリース境界取得、差分素材収集、候補バージョン算出、タグ重複確認、dirty check、build、zip、draft release 作成のような決定的処理だけを担当する。スクリプトは `prepare` と `execute` に責務分離し、`prepare` は version optional、`execute` は version required のままとする。

**Tech Stack:** Markdown skill, Python 3 stdlib (`argparse`, `dataclasses`, `json`, `pathlib`, `re`, `subprocess`, `tempfile`), `git`, `gh`, `cmd.exe`, `powershell.exe`, `task.exe`

---

## File Structure

- `.codex/skills/create-github-release/SKILL.md`
  - スキルの発火条件、対話フロー、承認ゲート、リリースノート本文はエージェントが作成することを定義する。
- `.codex/skills/create-github-release/scripts/create_github_release.py`
  - `prepare` / `execute` の CLI と、バージョン正規化、前回リリース取得、差分素材収集、候補バージョン算出、build / zip / release 作成を実装する。
- `.codex/skills/create-github-release/tests/test_create_github_release.py`
  - スクリプトの純粋関数と dry-run 向けのテストを `unittest` で持つ。
- `.codex/skills/create-github-release/agents/openai.yaml`
  - スキル UI メタデータを持つ。必要最低限の `display_name`, `short_description`, `default_prompt` のみ入れる。
- `docs/superpowers/specs/2026-03-28-github-release-skill-design.md`
  - 今回の責務分離に合わせた設計書。必要に応じて本文表現だけ追記する。

### Task 1: スキル雛形とバージョン正規化テストを作る

**Files:**
- Create: `.codex/skills/create-github-release/SKILL.md`
- Create: `.codex/skills/create-github-release/scripts/create_github_release.py`
- Create: `.codex/skills/create-github-release/tests/test_create_github_release.py`
- Create: `.codex/skills/create-github-release/agents/openai.yaml`

- [ ] **Step 1: スキル用ディレクトリを作る**

Run:
```bash
mkdir -p .codex/skills/create-github-release/scripts
mkdir -p .codex/skills/create-github-release/tests
mkdir -p .codex/skills/create-github-release/agents
```

Expected: 3 ディレクトリが作成される。

- [ ] **Step 2: バージョン正規化の失敗テストを書く**

Create: `.codex/skills/create-github-release/tests/test_create_github_release.py`

```python
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_github_release.py"
SPEC = importlib.util.spec_from_file_location("create_github_release", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VersionNormalizationTests(unittest.TestCase):
    def test_normalize_plain_semver_to_prefixed_release_names(self) -> None:
        version = MODULE.normalize_version("1.2.3")
        self.assertEqual(version.plain, "1.2.3")
        self.assertEqual(version.tag, "v1.2.3")
        self.assertEqual(version.release_name, "v1.2.3")
        self.assertFalse(version.prerelease)

    def test_zero_major_is_prerelease(self) -> None:
        version = MODULE.normalize_version("0.5.0")
        self.assertTrue(version.prerelease)

    def test_rejects_non_semver_input(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.normalize_version("release-1.2.3")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: テストを実行して RED を確認する**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
```

Expected: `create_github_release.py` が未作成、または `normalize_version` 未定義で FAIL する。

- [ ] **Step 4: 最小実装でテストを通す**

Create: `.codex/skills/create-github-release/scripts/create_github_release.py`

```python
from __future__ import annotations

from dataclasses import dataclass
import re


SEMVER_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")


@dataclass(frozen=True)
class NormalizedVersion:
    plain: str
    tag: str
    release_name: str
    prerelease: bool


def normalize_version(raw: str) -> NormalizedVersion:
    candidate = raw.removeprefix("v").strip()
    match = SEMVER_RE.fullmatch(candidate)
    if match is None:
        raise ValueError(f"unsupported version: {raw}")
    major = int(match.group("major"))
    tag = f"v{candidate}"
    return NormalizedVersion(
        plain=candidate,
        tag=tag,
        release_name=tag,
        prerelease=major == 0,
    )
```

- [ ] **Step 5: テストを再実行して GREEN を確認する**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
```

Expected: `VersionNormalizationTests` がすべて PASS する。

### Task 2: `prepare` サブコマンドで差分素材を収集できるようにする

**Files:**
- Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`
- Modify: `.codex/skills/create-github-release/tests/test_create_github_release.py`

- [ ] **Step 1: 前回リリース判定とペイロード生成の失敗テストを書く**

Modify: `.codex/skills/create-github-release/tests/test_create_github_release.py`

```python
SAMPLE_RELEASE_LIST = "\n".join(
    [
        "0.4.0\tPre-release\tv0.4.0\t2026-03-25T15:23:26Z",
        "0.3.0\tPre-release\tv0.3.0\t2026-01-25T14:14:43Z",
    ]
)

SAMPLE_TAG_LIST = "v0.4.0\nv0.3.0\n"


class PreparePayloadTests(unittest.TestCase):
    def test_pick_previous_release_tag_from_gh_release_list(self) -> None:
        self.assertEqual(MODULE.pick_previous_release_tag(SAMPLE_RELEASE_LIST), "v0.4.0")

    def test_fallback_to_git_tags_when_release_list_missing(self) -> None:
        self.assertEqual(MODULE.pick_previous_tag(SAMPLE_TAG_LIST), "v0.4.0")

    def test_build_prepare_payload_uses_prefixed_release_identity(self) -> None:
        version = MODULE.normalize_version("1.2.3")
        payload = MODULE.build_prepare_payload(
            version=version,
            previous_release_tag="v0.4.0",
            commits=[{"sha": "abc1234", "subject": "fix: retry upload"}],
            changed_files=["frontend/src/main/MainApp.svelte"],
        )
        self.assertEqual(payload["tag_name"], "v1.2.3")
        self.assertEqual(payload["release_name"], "v1.2.3")
        self.assertTrue(payload["draft"])
        self.assertFalse(payload["prerelease"])
        self.assertEqual(payload["compare_range"], "v0.4.0..HEAD")
```

- [ ] **Step 2: テストを実行して RED を確認する**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
```

Expected: `pick_previous_release_tag`, `pick_previous_tag`, `build_prepare_payload` が未定義で FAIL する。

- [ ] **Step 3: `prepare` 用の最小実装を書く**

Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`

```python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def pick_previous_release_tag(release_list_output: str) -> str | None:
    for line in release_list_output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2].startswith("v"):
            return parts[2]
    return None


def pick_previous_tag(tag_list_output: str) -> str | None:
    for line in tag_list_output.splitlines():
        if line.startswith("v"):
            return line.strip()
    return None


def run_command(args: list[str]) -> str:
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    return completed.stdout


def build_prepare_payload(
    *,
    version: NormalizedVersion,
    previous_release_tag: str | None,
    commits: list[dict[str, str]],
    changed_files: list[str],
) -> dict[str, object]:
    compare_range = f"{previous_release_tag}..HEAD" if previous_release_tag else None
    return {
        "input_version": version.plain,
        "tag_name": version.tag,
        "release_name": version.release_name,
        "draft": True,
        "prerelease": version.prerelease,
        "previous_release_tag": previous_release_tag,
        "compare_range": compare_range,
        "commits": commits,
        "changed_files": changed_files,
    }


def list_commits(compare_range: str | None) -> list[dict[str, str]]:
    range_expr = compare_range or "HEAD~20..HEAD"
    output = run_command(["git", "log", "--pretty=format:%H%x09%s", range_expr])
    commits: list[dict[str, str]] = []
    for line in output.splitlines():
        sha, subject = line.split("\t", 1)
        commits.append({"sha": sha[:7], "subject": subject})
    return commits


def list_changed_files(compare_range: str | None) -> list[str]:
    range_expr = compare_range or "HEAD~20..HEAD"
    output = run_command(["git", "diff", "--name-only", range_expr])
    return [line for line in output.splitlines() if line]


def detect_previous_release_tag() -> str | None:
    try:
        release_list_output = run_command(["gh", "release", "list", "--limit", "20"])
    except subprocess.CalledProcessError:
        release_list_output = ""
    previous = pick_previous_release_tag(release_list_output)
    if previous is not None:
        return previous
    tag_list_output = run_command(["git", "tag", "--sort=-creatordate"])
    return pick_previous_tag(tag_list_output)


def cmd_prepare(raw_version: str) -> int:
    version = normalize_version(raw_version)
    previous = detect_previous_release_tag()
    compare_range = f"{previous}..HEAD" if previous else None
    payload = build_prepare_payload(
        version=version,
        previous_release_tag=previous,
        commits=list_commits(compare_range),
        changed_files=list_changed_files(compare_range),
    )
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("version")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare":
        return cmd_prepare(args.version)
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: テストを再実行して GREEN を確認する**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
```

Expected: `PreparePayloadTests` まで PASS する。

- [ ] **Step 5: リポジトリ実データで `prepare` を手動確認する**

Run:
```bash
python3 .codex/skills/create-github-release/scripts/create_github_release.py prepare 1.2.3
```

Expected: JSON に `tag_name: "v1.2.3"`, `release_name: "v1.2.3"`, `draft: true`, `previous_release_tag`, `compare_range`, `commits`, `changed_files` が含まれる。ここではリリースノート本文は出さない。

### Task 3: `prepare` 引数なし時の候補バージョンを追加する

**Files:**
- Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`
- Modify: `.codex/skills/create-github-release/tests/test_create_github_release.py`

- [ ] **Step 1: 候補バージョン算出の失敗テストを書く**

Modify: `.codex/skills/create-github-release/tests/test_create_github_release.py`

```python
class SuggestedVersionTests(unittest.TestCase):
    def test_parse_previous_release_version_from_tag(self) -> None:
        previous = MODULE.parse_previous_release_version("v0.4.0")
        self.assertEqual(previous.plain, "0.4.0")

    def test_build_next_version_candidates(self) -> None:
        candidates = MODULE.build_version_candidates("v0.4.0")
        self.assertEqual(candidates["patch"], "0.4.1")
        self.assertEqual(candidates["minor"], "0.5.0")
        self.assertEqual(candidates["major"], "1.0.0")

    def test_prepare_payload_without_version_includes_candidates(self) -> None:
        payload = MODULE.build_prepare_payload(
            version=None,
            previous_release_tag="v0.4.0",
            commits=[],
            changed_files=[],
        )
        self.assertIsNone(payload["tag_name"])
        self.assertEqual(payload["version_candidates"]["patch"], "0.4.1")
```

- [ ] **Step 2: テストを実行して RED を確認する**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
```

Expected: `parse_previous_release_version`, `build_version_candidates`, `version=None` 対応が未実装で FAIL する。

- [ ] **Step 3: 最小実装を書く**

Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`

```python
def parse_previous_release_version(previous_release_tag: str | None) -> NormalizedVersion | None:
    if previous_release_tag is None:
        return None
    return normalize_version(previous_release_tag)


def build_version_candidates(previous_release_tag: str | None) -> dict[str, str]:
    previous = parse_previous_release_version(previous_release_tag)
    if previous is None:
        return {"patch": "0.0.1", "minor": "0.1.0", "major": "1.0.0"}
    major_str, minor_str, patch_str = previous.plain.split(".")
    major = int(major_str)
    minor = int(minor_str)
    patch = int(patch_str)
    return {
        "patch": f"{major}.{minor}.{patch + 1}",
        "minor": f"{major}.{minor + 1}.0",
        "major": f"{major + 1}.0.0",
    }
```

`build_prepare_payload()` は `version: NormalizedVersion | None` を受け、`version is None` の場合は `tag_name`, `release_name`, `prerelease` を `None` にし、`version_candidates` を返す。

`prepare` の `version` 引数は optional に変更し、未指定時は候補だけを返す。

- [ ] **Step 4: テストと実データ確認を行う**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
python3 .codex/skills/create-github-release/scripts/create_github_release.py prepare
```

Expected: JSON に `previous_release_tag`, `version_candidates`, `commits`, `changed_files` が含まれる。

### Task 4: `execute` サブコマンドで dry-run と実行フェーズを分ける

**Files:**
- Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`
- Modify: `.codex/skills/create-github-release/tests/test_create_github_release.py`

- [ ] **Step 1: 実行フェーズの失敗テストを書く**

Modify: `.codex/skills/create-github-release/tests/test_create_github_release.py`

```python
class ExecutePlanTests(unittest.TestCase):
    def test_archive_name_uses_prefixed_tag(self) -> None:
        self.assertEqual(MODULE.build_archive_name("v1.2.3"), "SplatReplay-v1.2.3.zip")

    def test_rejects_dirty_worktree(self) -> None:
        with self.assertRaises(MODULE.ReleaseAbort):
            MODULE.ensure_clean_worktree(" M frontend/src/main/MainApp.svelte\n")

    def test_build_release_command_keeps_draft_and_verify_tag(self) -> None:
        command = MODULE.build_release_command(
            tag_name="v0.5.0",
            notes_file=Path("notes.md"),
            asset_path=Path("SplatReplay-v0.5.0.zip"),
            prerelease=True,
        )
        self.assertIn("--draft", command)
        self.assertIn("--prerelease", command)
        self.assertIn("--verify-tag", command)
```

- [ ] **Step 2: テストを実行して RED を確認する**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
```

Expected: `ReleaseAbort`, `build_archive_name`, `ensure_clean_worktree`, `build_release_command` が未定義で FAIL する。

- [ ] **Step 3: `execute` と `--dry-run` を最小実装する**

Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`

```python
class ReleaseAbort(RuntimeError):
    pass


def build_archive_name(tag_name: str) -> str:
    return f"SplatReplay-{tag_name}.zip"


def ensure_clean_worktree(status_output: str) -> None:
    if status_output.strip():
        raise ReleaseAbort("dirty worktree")


def build_release_command(
    *,
    tag_name: str,
    notes_file: Path,
    asset_path: Path,
    prerelease: bool,
) -> list[str]:
    command = [
        "gh",
        "release",
        "create",
        tag_name,
        str(asset_path),
        "--title",
        tag_name,
        "--notes-file",
        str(notes_file),
        "--draft",
        "--verify-tag",
    ]
    if prerelease:
        command.append("--prerelease")
    return command


def ensure_tag_absent(tag_name: str) -> None:
    existing = run_command(["git", "tag", "--list", tag_name]).strip()
    if existing:
        raise ReleaseAbort(f"tag already exists: {tag_name}")


def ensure_release_absent(tag_name: str) -> None:
    existing = run_command(["gh", "release", "view", tag_name, "--json", "name"]).strip()
    if existing:
        raise ReleaseAbort(f"release already exists: {tag_name}")


def cmd_execute(raw_version: str, notes_file: Path, dry_run: bool) -> int:
    version = normalize_version(raw_version)
    status_output = run_command(["git", "status", "--short"])
    ensure_clean_worktree(status_output)
    ensure_tag_absent(version.tag)
    try:
        ensure_release_absent(version.tag)
    except subprocess.CalledProcessError:
        pass

    planned_commands = [
        ["git", "tag", version.tag],
        ["git", "push", "origin", version.tag],
        ["cmd.exe", "/c", "task.exe", "build"],
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "Compress-Archive "
                "-Path 'dist\\SplatReplay\\*' "
                "-DestinationPath $env:TEMP\\"
                + build_archive_name(version.tag)
                + " -Force"
            ),
        ],
    ]

    if dry_run:
        json.dump(
            {
                "tag_name": version.tag,
                "draft": True,
                "prerelease": version.prerelease,
                "planned_commands": planned_commands
                + [build_release_command(
                    tag_name=version.tag,
                    notes_file=notes_file,
                    asset_path=Path("%TEMP%") / build_archive_name(version.tag),
                    prerelease=version.prerelease,
                )],
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    raise NotImplementedError("live execute implementation goes here after dry-run is validated")
```

- [ ] **Step 4: `execute` サブコマンドの CLI をつなぐ**

Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`

```python
    execute = subparsers.add_parser("execute")
    execute.add_argument("version")
    execute.add_argument("--notes-file", type=Path, required=True)
    execute.add_argument("--dry-run", action="store_true")
```

```python
    if args.command == "execute":
        return cmd_execute(args.version, args.notes_file, args.dry_run)
```

- [ ] **Step 5: dry-run まで GREEN にする**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
printf -- "- 仕様追加・変更\n  - dry-run 追加\n" > /tmp/release-notes.md
python3 .codex/skills/create-github-release/scripts/create_github_release.py execute 1.2.3 --notes-file /tmp/release-notes.md --dry-run
```

Expected: テストが PASS し、dry-run は JSON の実行計画だけを出力する。タグも release も作られない。

- [ ] **Step 6: live execute を実装する**

Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`

```python
import os
import tempfile


def run_command_live(args: list[str]) -> None:
    subprocess.run(args, check=True)


def cmd_execute(raw_version: str, notes_file: Path, dry_run: bool) -> int:
    version = normalize_version(raw_version)
    status_output = run_command(["git", "status", "--short"])
    ensure_clean_worktree(status_output)
    ensure_tag_absent(version.tag)
    try:
        ensure_release_absent(version.tag)
    except subprocess.CalledProcessError:
        pass

    archive_path = Path(tempfile.gettempdir()) / build_archive_name(version.tag)
    release_command = build_release_command(
        tag_name=version.tag,
        notes_file=notes_file,
        asset_path=archive_path,
        prerelease=version.prerelease,
    )

    if dry_run:
        ...

    try:
        run_command_live(["git", "tag", version.tag])
        run_command_live(["git", "push", "origin", version.tag])
        run_command_live(["cmd.exe", "/c", "task.exe", "build"])
        if archive_path.exists():
            archive_path.unlink()
        run_command_live(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                (
                    "Compress-Archive "
                    "-Path 'dist\\SplatReplay\\*' "
                    f"-DestinationPath '{archive_path}' "
                    "-Force"
                ),
            ]
        )
        run_command_live(release_command)
        return 0
    finally:
        if archive_path.exists():
            archive_path.unlink()
```

- [ ] **Step 7: live 実行はコードレビュー後にだけ手動確認する**

Run:
```bash
python3 .codex/skills/create-github-release/scripts/create_github_release.py execute 1.2.3 --notes-file /tmp/release-notes.md --dry-run
```

Expected: まず dry-run のみ確認する。実 release 作成はユーザーの明示依頼が出るまで実行しない。

### Task 5: スキル本文と UI メタデータを仕上げる

**Files:**
- Modify: `.codex/skills/create-github-release/SKILL.md`
- Modify: `.codex/skills/create-github-release/agents/openai.yaml`
- Modify: `docs/superpowers/specs/2026-03-28-github-release-skill-design.md`

- [ ] **Step 1: SKILL.md の骨子を書く**

Modify: `.codex/skills/create-github-release/SKILL.md`

```md
---
name: create-github-release
description: Use when this repository needs a GitHub Release created from a version like 1.2.3, with user-approved release notes, Windows build packaging, zip attachment, and draft release creation.
---

# Create GitHub Release

## Overview

このスキルは、このリポジトリ向けの GitHub Release 作成フローを安全に実行する。リリースノート本文はエージェントが差分から作成し、補助スクリプトは release 境界取得、差分素材収集、タグ重複確認、dirty check、build、zip、release 作成だけを行う。

## Workflow

1. `python3 .codex/skills/create-github-release/scripts/create_github_release.py prepare [version]` を実行する。
2. version 指定がない場合は、返却 JSON の `version_candidates` を見て、エージェントが推奨版を決める。
3. 返却 JSON の `commits` と `changed_files` を読み、エージェントがリリースノート本文を作成する。
4. ユーザーへ、候補バージョン、推奨版、予定タグ名、予定リリース名、`draft` / `prerelease` 判定、本文、build / zip 添付予定を提示する。
5. 明示的な許可があるまで、`execute` を実行しない。
6. 許可後に、`execute <version> --notes-file <path>` を実行する。
```

- [ ] **Step 2: 異常系と停止条件を書く**

Modify: `.codex/skills/create-github-release/SKILL.md`

```md
## Stop Conditions

- 入力が `1.2.3` / `v1.2.3` のどちらでも解釈できない場合は停止する。
- dirty worktree の場合は停止する。
- 同名タグまたは同名 release がある場合は停止する。
- `task.exe build` が失敗した場合は停止する。
- 添付 zip は一時ファイルとして扱い、release 作成後は削除する。
```

- [ ] **Step 3: UI メタデータを生成する**

Run:
```bash
python3 /home/j0314888/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py \
  .codex/skills/create-github-release \
  --interface display_name="GitHub Release" \
  --interface short_description="GitHub Release を下書き作成" \
  --interface default_prompt='Use $create-github-release to prepare and create a draft GitHub release for this repository.'
```

Expected: `.codex/skills/create-github-release/agents/openai.yaml` が生成される。

- [ ] **Step 4: スキルの基本妥当性を確認する**

Run:
```bash
python3 /home/j0314888/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .codex/skills/create-github-release
```

Expected: frontmatter と命名ルールの検証が PASS する。

### Task 6: ローカル検証と手動レビューを完了する

**Files:**
- Modify: `.codex/skills/create-github-release/scripts/create_github_release.py`
- Modify: `.codex/skills/create-github-release/tests/test_create_github_release.py`
- Modify: `.codex/skills/create-github-release/SKILL.md`

- [ ] **Step 1: スクリプトテストを通す**

Run:
```bash
python3 -m unittest discover -s .codex/skills/create-github-release/tests -p 'test_*.py' -v
```

Expected: すべて PASS する。

- [ ] **Step 2: `prepare` を実リポジトリで確認する**

Run:
```bash
python3 .codex/skills/create-github-release/scripts/create_github_release.py prepare > /tmp/create-github-release-prepare-no-version.json
sed -n '1,120p' /tmp/create-github-release-prepare-no-version.json
python3 .codex/skills/create-github-release/scripts/create_github_release.py prepare 1.2.3 > /tmp/create-github-release-prepare.json
sed -n '1,120p' /tmp/create-github-release-prepare.json
```

Expected: 引数なしでは前回リリース境界、候補バージョン、差分素材が出力される。引数ありでは従来どおり `draft` / `prerelease` 判定つきの準備情報が出力される。本文は含まれない。

- [ ] **Step 3: dry-run 実行計画を確認する**

Run:
```bash
cat <<'EOF' > /tmp/create-github-release-notes.md
- 仕様追加・変更
  - リリース作成フローをスキル化しました。
EOF
python3 .codex/skills/create-github-release/scripts/create_github_release.py execute 1.2.3 --notes-file /tmp/create-github-release-notes.md --dry-run > /tmp/create-github-release-execute.json
sed -n '1,160p' /tmp/create-github-release-execute.json
```

Expected: `git tag`, `git push`, `task.exe build`, `Compress-Archive`, `gh release create` の予定が並ぶ。実際の tag/release は作られない。

- [ ] **Step 4: スキル本文を読み直して運用ルールと一致させる**

Check:
- リリースノート本文はエージェント担当と明記されているか
- 実行前に必ず許可取得と明記されているか
- 常に draft、メジャー 0 のみ prerelease と明記されているか
- build と zip 添付が含まれているか

- [ ] **Step 5: 完了報告ではコミットを作らない**

Check:
- ユーザーが明示的に指示するまで `git commit` を実行しない
- 追加した一時ファイルは `/tmp` 配下のみとし、作業終了前に削除する

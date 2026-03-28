from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$"
)


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


class ReleaseAbort(RuntimeError):
    pass


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


def run_command_result(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def run_command_live(args: list[str]) -> None:
    subprocess.run(args, check=True)


def parse_previous_release_version(previous_release_tag: str | None) -> NormalizedVersion | None:
    if previous_release_tag is None:
        return None
    return normalize_version(previous_release_tag)


def build_version_candidates(previous_release_tag: str | None) -> dict[str, str]:
    previous = parse_previous_release_version(previous_release_tag)
    if previous is None:
        return {
            "patch": "0.0.1",
            "minor": "0.1.0",
            "major": "1.0.0",
        }
    major_str, minor_str, patch_str = previous.plain.split(".")
    major = int(major_str)
    minor = int(minor_str)
    patch = int(patch_str)
    return {
        "patch": f"{major}.{minor}.{patch + 1}",
        "minor": f"{major}.{minor + 1}.0",
        "major": f"{major + 1}.0.0",
    }


def build_prepare_payload(
    *,
    version: NormalizedVersion | None,
    previous_release_tag: str | None,
    commits: list[dict[str, str]],
    changed_files: list[str],
) -> dict[str, object]:
    compare_range = f"{previous_release_tag}..HEAD" if previous_release_tag else None
    version_candidates = build_version_candidates(previous_release_tag)
    return {
        "input_version": version.plain if version is not None else None,
        "tag_name": version.tag if version is not None else None,
        "release_name": version.release_name if version is not None else None,
        "draft": True,
        "prerelease": version.prerelease if version is not None else None,
        "previous_release_tag": previous_release_tag,
        "previous_release_version": (
            parse_previous_release_version(previous_release_tag).plain
            if parse_previous_release_version(previous_release_tag) is not None
            else None
        ),
        "version_candidates": version_candidates,
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


def build_archive_name(tag_name: str) -> str:
    return f"SplatReplay-{tag_name}.zip"


def to_windows_path(path: Path) -> str:
    path_str = str(path)
    match = re.match(r"^/mnt/(?P<drive>[a-zA-Z])/(?P<rest>.*)$", path_str)
    if match is None:
        return path_str
    drive = match.group("drive").upper()
    rest = match.group("rest").replace("/", "\\")
    return f"{drive}:\\{rest}"


def ensure_clean_worktree(status_output: str) -> None:
    if status_output.strip():
        raise ReleaseAbort("dirty worktree")


def ensure_tag_absent(tag_name: str) -> None:
    existing = run_command(["git", "tag", "--list", tag_name]).strip()
    if existing:
        raise ReleaseAbort(f"tag already exists: {tag_name}")


def ensure_release_absent(tag_name: str) -> None:
    result = run_command_result(["gh", "release", "view", tag_name, "--json", "name"])
    if result.returncode == 0 and result.stdout.strip():
        raise ReleaseAbort(f"release already exists: {tag_name}")


def build_archive_command(archive_path: Path) -> list[str]:
    windows_archive_path = to_windows_path(archive_path)
    return [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        (
            "Compress-Archive "
            "-Path 'dist\\SplatReplay\\*' "
            f"-DestinationPath '{windows_archive_path}' "
            "-Force"
        ),
    ]


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


def cmd_prepare(raw_version: str | None) -> int:
    version = normalize_version(raw_version) if raw_version is not None else None
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


def cmd_execute(raw_version: str, notes_file: Path, dry_run: bool) -> int:
    version = normalize_version(raw_version)
    ensure_clean_worktree(run_command(["git", "status", "--short"]))
    ensure_tag_absent(version.tag)
    ensure_release_absent(version.tag)

    archive_path = Path(tempfile.gettempdir()) / build_archive_name(version.tag)
    planned_commands = [
        ["git", "tag", version.tag],
        ["git", "push", "origin", version.tag],
        ["cmd.exe", "/c", "task.exe", "build"],
        build_archive_command(archive_path),
        build_release_command(
            tag_name=version.tag,
            notes_file=notes_file,
            asset_path=archive_path,
            prerelease=version.prerelease,
        ),
    ]
    if dry_run:
        json.dump(
            {
                "tag_name": version.tag,
                "release_name": version.release_name,
                "draft": True,
                "prerelease": version.prerelease,
                "archive_path": str(archive_path),
                "planned_commands": planned_commands,
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    try:
        run_command_live(planned_commands[0])
        run_command_live(planned_commands[1])
        run_command_live(planned_commands[2])
        if archive_path.exists():
            archive_path.unlink()
        run_command_live(planned_commands[3])
        run_command_live(planned_commands[4])
        return 0
    finally:
        if archive_path.exists():
            archive_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("version", nargs="?")
    execute = subparsers.add_parser("execute")
    execute.add_argument("version")
    execute.add_argument("--notes-file", type=Path, required=True)
    execute.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "prepare":
        return cmd_prepare(args.version)
    if args.command == "execute":
        return cmd_execute(args.version, args.notes_file, args.dry_run)
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

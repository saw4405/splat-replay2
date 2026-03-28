from __future__ import annotations

import importlib.util
import io
import sys
import unittest.mock as mock
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "create_github_release.py"
SPEC = importlib.util.spec_from_file_location("create_github_release", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class VersionNormalizationTests(unittest.TestCase):
    def test_normalize_plain_semver_to_prefixed_release_names(self) -> None:
        version = MODULE.normalize_version("1.2.3")
        self.assertEqual(version.plain, "1.2.3")
        self.assertEqual(version.tag, "v1.2.3")
        self.assertEqual(version.release_name, "v1.2.3")
        self.assertFalse(version.prerelease)

    def test_accepts_prefixed_input_but_normalizes_to_plain_version(self) -> None:
        version = MODULE.normalize_version("v1.2.3")
        self.assertEqual(version.plain, "1.2.3")
        self.assertEqual(version.tag, "v1.2.3")

    def test_zero_major_is_prerelease(self) -> None:
        version = MODULE.normalize_version("0.5.0")
        self.assertTrue(version.prerelease)

    def test_rejects_non_semver_input(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.normalize_version("release-1.2.3")

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

    def test_parse_previous_release_version_from_tag(self) -> None:
        previous = MODULE.parse_previous_release_version("v0.4.0")
        self.assertIsNotNone(previous)
        assert previous is not None
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
        self.assertIsNone(payload["release_name"])
        self.assertIsNone(payload["prerelease"])
        self.assertEqual(payload["version_candidates"]["patch"], "0.4.1")


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

    def test_build_archive_command_uses_windows_path_for_powershell(self) -> None:
        command = MODULE.build_archive_command(
            Path("/mnt/c/Users/shogo/AppData/Local/Temp/SplatReplay-v1.2.3.zip")
        )
        self.assertIn("C:\\Users\\shogo\\AppData\\Local\\Temp\\SplatReplay-v1.2.3.zip", command[3])

    def test_cmd_execute_dry_run_outputs_release_plan(self) -> None:
        release_view = MODULE.subprocess.CompletedProcess(
            args=["gh", "release", "view", "v1.2.3", "--json", "name"],
            returncode=1,
            stdout="",
            stderr="release not found",
        )
        buffer = io.StringIO()
        with (
            mock.patch.object(
                MODULE,
                "run_command",
                side_effect=["", ""],
            ),
            mock.patch.object(MODULE, "run_command_result", return_value=release_view),
            mock.patch("sys.stdout", buffer),
        ):
            exit_code = MODULE.cmd_execute(
                "1.2.3",
                notes_file=Path("notes.md"),
                dry_run=True,
            )
        self.assertEqual(exit_code, 0)
        payload = MODULE.json.loads(buffer.getvalue())
        self.assertEqual(payload["tag_name"], "v1.2.3")
        self.assertTrue(payload["draft"])
        self.assertFalse(payload["prerelease"])
        self.assertEqual(
            payload["planned_commands"][0],
            ["git", "tag", "v1.2.3"],
        )


if __name__ == "__main__":
    unittest.main()

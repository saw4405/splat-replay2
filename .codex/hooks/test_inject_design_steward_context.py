"""design_steward の SubagentStart フック契約テスト。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = Path(__file__).with_name("inject_design_steward_context.py")


def run_hook(payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    """フックスクリプトを実際の標準入出力契約で実行する。"""

    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPT_PATH)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


class DesignStewardHookTest(unittest.TestCase):
    def test_resolves_parent_transcript_from_parent_session_id(self) -> None:
        parent_session_id = "019fc5ae-95c2-7520-9197-dc22b7177351"
        child_session_id = "019fe634-11b5-7461-8ed2-d98c02762374"
        with tempfile.TemporaryDirectory() as temporary_directory:
            sessions_root = Path(temporary_directory) / "sessions"
            parent_transcript = (
                sessions_root
                / "2026"
                / "08"
                / "03"
                / f"rollout-parent-{parent_session_id}.jsonl"
            )
            child_transcript = (
                sessions_root
                / "2026"
                / "08"
                / "09"
                / f"rollout-child-{child_session_id}.jsonl"
            )
            parent_transcript.parent.mkdir(parents=True)
            child_transcript.parent.mkdir(parents=True)
            parent_transcript.write_text("parent", encoding="utf-8")
            child_transcript.write_text("child", encoding="utf-8")

            result = run_hook(
                {
                    "hook_event_name": "SubagentStart",
                    "agent_type": "design_steward",
                    "session_id": parent_session_id,
                    "transcript_path": str(child_transcript),
                }
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(parent_transcript), context)
        self.assertNotIn(str(child_transcript), context)
        self.assertEqual(
            output["hookSpecificOutput"]["hookEventName"], "SubagentStart"
        )

    def test_ignores_other_agent_types(self) -> None:
        result = run_hook(
            {
                "hook_event_name": "SubagentStart",
                "agent_type": "explorer",
                "session_id": "019fc5ae-95c2-7520-9197-dc22b7177351",
                "transcript_path": r"C:\tmp\rollout.jsonl",
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_reports_missing_parent_transcript_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            child_transcript = (
                Path(temporary_directory)
                / "sessions"
                / "2026"
                / "08"
                / "09"
                / "rollout-child.jsonl"
            )
            child_transcript.parent.mkdir(parents=True)
            child_transcript.write_text("child", encoding="utf-8")
            result = run_hook(
                {
                    "hook_event_name": "SubagentStart",
                    "agent_type": "design_steward",
                    "session_id": "019fc5ae-95c2-7520-9197-dc22b7177351",
                    "transcript_path": str(child_transcript),
                }
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("利用できません", context)
        self.assertIn("代替保存をせず", context)


if __name__ == "__main__":
    unittest.main()

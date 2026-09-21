"""design_recorder の SubagentStart フック契約テスト。"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = Path(__file__).with_name("inject_design_recorder_context.py")


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


class DesignRecorderHookTest(unittest.TestCase):
    def test_resolves_parent_from_child_root_turn_id(self) -> None:
        parent_session_id = "019fc5ae-95c2-7520-9197-dc22b7177351"
        continuation_id = "019fc5af-1234-7520-9197-dc22b7177351"
        child_session_id = "019fe634-11b5-7461-8ed2-d98c02762374"
        root_turn_id = "019fc5b0-1234-7520-9197-dc22b7177351"
        child_turn_id = "019fe635-11b5-7461-8ed2-d98c02762374"
        with tempfile.TemporaryDirectory() as temporary_directory:
            sessions_root = Path(temporary_directory) / "sessions"
            parent_transcript = (
                sessions_root
                / "2026"
                / "08"
                / "03"
                / f"rollout-parent-{parent_session_id}.jsonl"
            )
            resumed_parent_transcript = (
                sessions_root
                / "2026"
                / "08"
                / "09"
                / f"rollout-parent-{parent_session_id}_{continuation_id}.jsonl"
            )
            child_transcript = (
                sessions_root
                / "2026"
                / "08"
                / "09"
                / f"rollout-child-{child_session_id}.jsonl"
            )
            parent_transcript.parent.mkdir(parents=True)
            resumed_parent_transcript.parent.mkdir(parents=True)
            child_transcript.parent.mkdir(parents=True, exist_ok=True)
            parent_transcript.write_text(
                json.dumps({"payload": {"turn_id": continuation_id}}),
                encoding="utf-8",
            )
            resumed_parent_transcript.write_text(
                json.dumps({"payload": {"turn_id": root_turn_id}}),
                encoding="utf-8",
            )
            child_transcript.write_text(
                json.dumps({"payload": {"root_turn_id": root_turn_id}}),
                encoding="utf-8",
            )

            result = run_hook(
                {
                    "hook_event_name": "SubagentStart",
                    "agent_type": "design_recorder",
                    "session_id": parent_session_id,
                    "turn_id": child_turn_id,
                    "transcript_path": str(child_transcript),
                }
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(resumed_parent_transcript), context)
        self.assertNotIn(str(parent_transcript), context)
        self.assertNotIn(str(child_transcript), context)
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SubagentStart")

    def test_falls_back_to_hook_turn_id_without_root_turn_id(self) -> None:
        parent_session_id = "019fc5ae-95c2-7520-9197-dc22b7177351"
        active_turn_id = "019fc5b0-1234-7520-9197-dc22b7177351"
        with tempfile.TemporaryDirectory() as temporary_directory:
            sessions_root = Path(temporary_directory) / "sessions"
            parent_transcript = (
                sessions_root / f"rollout-parent-{parent_session_id}.jsonl"
            )
            child_transcript = sessions_root / "rollout-child.jsonl"
            sessions_root.mkdir(parents=True)
            parent_transcript.write_text(
                json.dumps({"payload": {"turn_id": active_turn_id}}),
                encoding="utf-8",
            )
            child_transcript.write_text("child", encoding="utf-8")

            result = run_hook(
                {
                    "hook_event_name": "SubagentStart",
                    "agent_type": "design_recorder",
                    "session_id": parent_session_id,
                    "turn_id": active_turn_id,
                    "transcript_path": str(child_transcript),
                }
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(parent_transcript), context)

    def test_ignores_design_advisor(self) -> None:
        result = run_hook(
            {
                "hook_event_name": "SubagentStart",
                "agent_type": "design_advisor",
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
                    "agent_type": "design_recorder",
                    "session_id": "019fc5ae-95c2-7520-9197-dc22b7177351",
                    "turn_id": "019fc5b0-1234-7520-9197-dc22b7177351",
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

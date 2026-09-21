"""design_recorder に親セッションの原文トランスクリプト位置を渡す。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Dict, Optional
from uuid import UUID


JsonObject = Dict[str, object]


def normalize_uuid(value: object) -> Optional[str]:
    """UUID 文字列を正規化し、不正な値を拒否する。"""

    if not isinstance(value, str):
        return None
    try:
        normalized = str(UUID(value))
    except ValueError:
        return None
    return normalized if normalized == value.lower() else None


def transcript_contains_turn(transcript_path: Path, turn_id: str) -> bool:
    """トランスクリプトが現在ターンの直接イベントを含むか確認する。"""

    try:
        with transcript_path.open(encoding="utf-8") as transcript:
            for line in transcript:
                event = json.loads(line)
                if not isinstance(event, dict):
                    continue
                event_payload = event.get("payload")
                if not isinstance(event_payload, dict):
                    continue
                metadata = event_payload.get(
                    "internal_chat_message_metadata_passthrough"
                )
                if event_payload.get("turn_id") == turn_id or (
                    isinstance(metadata, dict) and metadata.get("turn_id") == turn_id
                ):
                    return True
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    return False


def child_root_turn_id(transcript_path: Path) -> Optional[str]:
    """子トランスクリプトから親側の起点ターン ID を取得する。"""

    try:
        with transcript_path.open(encoding="utf-8") as transcript:
            for line in transcript:
                event = json.loads(line)
                if not isinstance(event, dict):
                    continue
                event_payload = event.get("payload")
                if not isinstance(event_payload, dict):
                    continue
                root_turn_id = normalize_uuid(event_payload.get("root_turn_id"))
                if root_turn_id is not None:
                    return root_turn_id
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return None


def find_parent_transcript(payload: JsonObject) -> Optional[Path]:
    """親セッションの現在ターンを含むトランスクリプトを一意に解決する。"""

    parent_session_id = normalize_uuid(payload.get("session_id"))
    child_transcript_path = payload.get("transcript_path")
    if parent_session_id is None or not isinstance(child_transcript_path, str):
        return None

    child_transcript = Path(child_transcript_path)
    turn_id = child_root_turn_id(child_transcript) or normalize_uuid(
        payload.get("turn_id")
    )
    if turn_id is None:
        return None

    sessions_root = next(
        (parent for parent in child_transcript.parents if parent.name == "sessions"),
        None,
    )
    if sessions_root is None:
        return None

    matches = [
        transcript
        for transcript in sessions_root.rglob(f"*{parent_session_id}*.jsonl")
        if transcript_contains_turn(transcript, turn_id)
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def build_output(payload: JsonObject) -> Optional[JsonObject]:
    """対象の SubagentStart だけに追加コンテキストを返す。"""

    if payload.get("hook_event_name") != "SubagentStart":
        return None
    if payload.get("agent_type") != "design_recorder":
        return None

    parent_transcript = find_parent_transcript(payload)
    if parent_transcript is not None:
        context = (
            "親セッションの原文トランスクリプトは次のパスです:\n"
            f"{parent_transcript}\n"
            "RECORD ではこのファイルを自分で読み、対象判断に関係する原文・経緯・検討案を"
            "抽出してください。無関係なセッションを探索せず、解釈だけで原文を補わないでください。"
        )
    else:
        context = (
            "親セッションの原文トランスクリプトは利用できません。"
            "RECORD では推測や代替保存をせず、保存失敗としてメインエージェントへ返してください。"
        )

    return {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": context,
        }
    }


def main() -> int:
    """標準入力のフック JSON を処理して、標準出力へ JSON を返す。"""

    try:
        raw_payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        print(f"invalid hook input: {error}", file=sys.stderr)
        return 1

    if not isinstance(raw_payload, dict):
        print("invalid hook input: expected a JSON object", file=sys.stderr)
        return 1

    output = build_output(raw_payload)
    if output is not None:
        json.dump(output, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

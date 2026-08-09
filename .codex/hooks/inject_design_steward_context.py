"""design_steward に親セッションのトランスクリプト位置を渡す。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Dict, Optional
from uuid import UUID


JsonObject = Dict[str, object]


def find_parent_transcript(payload: JsonObject) -> Optional[Path]:
    """親セッション ID と完全一致するトランスクリプトを一意に解決する。"""

    parent_session_id = payload.get("session_id")
    child_transcript_path = payload.get("transcript_path")
    if not isinstance(parent_session_id, str) or not isinstance(
        child_transcript_path, str
    ):
        return None

    try:
        normalized_parent_id = str(UUID(parent_session_id))
    except ValueError:
        return None
    if normalized_parent_id != parent_session_id.lower():
        return None

    child_transcript = Path(child_transcript_path)
    sessions_root = next(
        (parent for parent in child_transcript.parents if parent.name == "sessions"),
        None,
    )
    if sessions_root is None:
        return None

    matches = list(sessions_root.rglob(f"*{normalized_parent_id}.jsonl"))
    if len(matches) != 1:
        return None
    return matches[0]


def build_output(payload: JsonObject) -> Optional[JsonObject]:
    """対象の SubagentStart だけに追加コンテキストを返す。"""

    if payload.get("hook_event_name") != "SubagentStart":
        return None
    if payload.get("agent_type") != "design_steward":
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

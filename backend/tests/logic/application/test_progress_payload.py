"""進捗イベントの公開 payload 契約を検証する。

分類: logic
"""

from splat_replay.application.services.common.progress import (
    ProgressEvent,
    build_progress_payload,
)


def test_build_progress_payload_includes_visual_progress_fields() -> None:
    clips: list[dict[str, object]] = [
        {
            "group_index": 0,
            "video_assets": [
                {
                    "video_id": "recorded/sample.mkv",
                    "duration_seconds": 120,
                }
            ],
        }
    ]
    event = ProgressEvent(
        task_id="auto_edit",
        kind="start",
        task_name="自動編集",
        total=1,
        completed=0,
        progress_percent=25.0,
        clips=clips,
    )

    payload = build_progress_payload(event)

    assert payload["progress_percent"] == 25.0
    assert payload["clips"] == clips

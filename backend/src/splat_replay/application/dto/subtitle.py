"""字幕関連のDTO定義。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleBlockDTO:
    """字幕ブロックを表すDTO。

    Attributes:
        index: ブロック番号
        start_time: 開始時刻（秒）
        end_time: 終了時刻（秒）
        text: 字幕テキスト
    """

    index: int
    start_time: float
    end_time: float
    text: str


@dataclass(frozen=True)
class SubtitleDataDTO:
    """字幕データを表すDTO。

    Attributes:
        blocks: 字幕ブロックのリスト
        video_duration: 動画の長さ（秒）- オプション
    """

    blocks: list[SubtitleBlockDTO]
    video_duration: float | None = None

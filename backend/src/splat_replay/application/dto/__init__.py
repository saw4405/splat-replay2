"""Application層のDTO定義。

Clean Architecture の原則に従い、Application層は外部層（Interface/Infrastructure）に
依存してはならない。このDTOはユースケースが返すデータ構造を定義する。

責務：
- ユースケースの入出力データ構造を定義
- ドメインモデルとインターフェース層の間の変換層
- 各インターフェース（HTTP/CLI/GUI）から独立
"""

from __future__ import annotations

__all__ = [
    # Assets DTO
    "RecordedVideoDTO",
    "EditedVideoDTO",
    "EditUploadStatusDTO",
    # Metadata DTO
    "SubtitleDTO",
    "RecordingMetadataPatchDTO",
    # Subtitle DTO
    "SubtitleBlockDTO",
    "SubtitleDataDTO",
]

from .assets import EditedVideoDTO, EditUploadStatusDTO, RecordedVideoDTO
from .metadata import RecordingMetadataPatchDTO, SubtitleDTO
from .subtitle import SubtitleBlockDTO, SubtitleDataDTO

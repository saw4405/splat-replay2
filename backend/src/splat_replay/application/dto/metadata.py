"""メタデータ管理関連のDTO定義。"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "SubtitleDTO",
    "RecordingMetadataPatchDTO",
]


@dataclass(frozen=True)
class SubtitleDTO:
    """字幕データを表すDTO。

    Attributes:
        content: 字幕内容（SRT形式のテキスト）
    """

    content: str


@dataclass(frozen=True)
class RecordingMetadataPatchDTO:
    """録画メタデータ更新パッチDTO。"""

    match: str | None = None
    rule: str | None = None
    stage: str | None = None
    rate: str | None = None
    judgement: str | None = None
    kill: int | None = None
    death: int | None = None
    special: int | None = None
    allies: tuple[str, str, str, str] | None = None
    enemies: tuple[str, str, str, str] | None = None

    def to_update_dict(self) -> dict[str, object]:
        """更新対象のみを抽出した辞書を返す。"""
        payload: dict[str, object] = {}
        if self.match is not None:
            payload["match"] = self.match
        if self.rule is not None:
            payload["rule"] = self.rule
        if self.stage is not None:
            payload["stage"] = self.stage
        if self.rate is not None:
            payload["rate"] = self.rate
        if self.judgement is not None:
            payload["judgement"] = self.judgement
        if self.kill is not None:
            payload["kill"] = self.kill
        if self.death is not None:
            payload["death"] = self.death
        if self.special is not None:
            payload["special"] = self.special
        if self.allies is not None:
            payload["allies"] = list(self.allies)
        if self.enemies is not None:
            payload["enemies"] = list(self.enemies)
        return payload

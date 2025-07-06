"""録画時に保存するメタデータクラス。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

from .rate import RateBase
from .match import Match
from .rule import Rule
from .stage import Stage


@dataclass
class RecordingMetadata:
    """録画時点での簡易メタデータ。"""

    started_at: datetime | None = None
    match: Match | None = None
    rule: Rule | None = None
    stage: Stage | None = None
    rate: RateBase | None = None
    judgement: str | None = None
    kill: int | None = None
    death: int | None = None
    special: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書へ変換する。"""
        return {
            "started_at": self.started_at.isoformat()
            if self.started_at
            else None,
            "match": self.match.name if self.match else None,
            "rule": self.rule.name if self.rule else None,
            "stage": self.stage.name if self.stage else None,
            "rate": self.rate.short_str() if self.rate else None,
            "judgement": self.judgement,
            "result": {
                "kill": self.kill,
                "death": self.death,
                "special": self.special,
            }
            if self.kill is not None
            and self.death is not None
            and self.special is not None
            else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordingMetadata":
        """辞書からインスタンスを生成する。"""
        started_at_str = data.get("started_at")
        started_at = (
            datetime.fromisoformat(started_at_str) if started_at_str else None
        )
        match_str = data.get("match")
        match = Match[match_str] if match_str else None
        rule_str = data.get("rule")
        rule = Rule[rule_str] if rule_str else None
        stage_str = data.get("stage")
        stage = Stage[stage_str] if stage_str else None
        rate_str = data.get("rate")
        rate = RateBase.create(rate_str) if rate_str else None
        result = data.get("result") or {}
        kill = result.get("kill")
        death = result.get("death")
        special = result.get("special")
        return cls(
            started_at=started_at,
            match=match,
            rule=rule,
            stage=stage,
            rate=rate,
            judgement=data.get("judgement"),
            kill=kill,
            death=death,
            special=special,
        )

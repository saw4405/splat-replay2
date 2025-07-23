"""録画時に保存するメタデータクラス。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

from .result import Result
from .rate import RateBase


@dataclass
class RecordingMetadata:
    """録画時点での簡易メタデータ。"""

    started_at: datetime
    rate: RateBase | None = None
    judgement: str | None = None
    result: Result | None = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書へ変換する。"""
        return {
            "started_at": self.started_at.isoformat()
            if self.started_at
            else None,
            "rate": str(self.rate) if self.rate else None,
            "judgement": self.judgement,
            "result": self.result.to_dict() if self.result else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordingMetadata":
        """辞書からインスタンスを生成する。"""
        started_at_str = data.get("started_at")
        if started_at_str is None:
            raise ValueError("started_at is required")

        started_at = datetime.fromisoformat(started_at_str)
        rate_str = data.get("rate")
        rate = RateBase.create(rate_str) if rate_str else None
        result_data = data.get("result")
        result = None
        if result_data:
            if result_data.get("type") == "battle":
                from .result import BattleResult

                result = BattleResult.from_dict(result_data)
            elif result_data.get("type") == "salmon":
                from .result import SalmonResult

                result = SalmonResult.from_dict(result_data)
        return cls(
            started_at=started_at,
            rate=rate,
            judgement=data.get("judgement"),
            result=result,
        )

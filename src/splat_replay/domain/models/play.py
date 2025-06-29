"""バトル情報。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .match import Match
from .rule import Rule
from .stage import Stage
from .rate import RateBase


@dataclass
class Play:
    """バトル1件分のメタデータ。"""

    match: Match
    rule: Rule
    stage: Stage
    start_at: datetime
    judgement: str | None = None
    kill: int | None = None
    death: int | None = None
    special: int | None = None
    rate: RateBase | None = None

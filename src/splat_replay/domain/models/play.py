"""バトル情報。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

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
    end_at: datetime | None = None
    result: str | None = None
    """"win" または "lose" を設定する。"""
    kill: int | None = None
    death: int | None = None
    special: int | None = None
    rate: RateBase | None = None
    id: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.id = str(uuid4())

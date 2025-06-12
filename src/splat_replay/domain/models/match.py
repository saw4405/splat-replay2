"""バトル情報。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from .result import Result
from .rule import Rule
from .stage import Stage


@dataclass
class Match:
    """バトル1件分のメタデータ。"""

    rule: Rule
    stage: Stage
    start_at: datetime
    end_at: datetime | None = None
    result: Result | None = None
    id: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.id = str(uuid4())

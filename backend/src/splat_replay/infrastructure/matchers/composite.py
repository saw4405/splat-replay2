from typing import Dict

import numpy as np

from splat_replay.domain.config import MatchExpression

from .base import BaseMatcher


class CompositeMatcher:
    """複数条件を評価するマッチャー。"""

    def __init__(
        self,
        expr: MatchExpression,
        lookup: Dict[str, BaseMatcher],
        *,
        name: str | None = None,
    ) -> None:
        self.name = name
        self.expr = expr
        self.lookup = lookup

    async def match(self, image: np.ndarray) -> bool:
        """設定された式に基づき判定する。"""

        async def _eval(name: str) -> bool:
            matcher = self.lookup.get(name)
            if matcher is None:
                return False
            return await matcher.match(image)

        result = await self.expr.evaluate(_eval)
        return result

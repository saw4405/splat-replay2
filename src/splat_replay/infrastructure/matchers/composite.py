from typing import Dict

import numpy as np

from splat_replay.shared.logger import get_logger
from splat_replay.shared.config import MatchExpression
from .base import BaseMatcher

logger = get_logger()


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

    def match(self, image: np.ndarray) -> bool:
        """設定された式に基づき判定する。"""

        def _eval(name: str) -> bool:
            matcher = self.lookup.get(name)
            if matcher is None:
                logger.debug("マッチャー未登録", matcher=name)
                return False
            result = matcher.match(image)
            if not result:
                logger.debug("サブマッチャー不一致", matcher=name)
            return result

        result = self.expr.evaluate(_eval)
        if not result:
            logger.debug("複合条件不一致")
        return result

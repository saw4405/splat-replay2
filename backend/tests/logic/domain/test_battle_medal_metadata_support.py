from __future__ import annotations

import pytest

from splat_replay.domain.exceptions import (
    ValidationError as DomainValidationError,
)
from splat_replay.domain.models import (
    BattleResult,
    Match,
    Rule,
    Stage,
)


def _build_battle_result(
    *,
    gold_medals: int = 2,
    silver_medals: int = 1,
) -> BattleResult:
    return BattleResult(
        match=Match.X,
        rule=Rule.RAINMAKER,
        stage=Stage.HAMMERHEAD_BRIDGE,
        kill=7,
        death=5,
        special=2,
        gold_medals=gold_medals,
        silver_medals=silver_medals,
    )


def test_battle_result_from_dict_defaults_medals_to_zero() -> None:
    result = BattleResult.from_dict(
        {
            "match": "X",
            "rule": "RAINMAKER",
            "stage": "HAMMERHEAD_BRIDGE",
            "kill": 0,
            "death": 3,
            "special": 0,
        }
    )
    assert result.gold_medals == 0
    assert result.silver_medals == 0


@pytest.mark.parametrize(
    ("gold_medals", "silver_medals"),
    [
        (-1, 0),
        (0, -1),
        (4, 0),
        (0, 4),
        (2, 2),
    ],
)
def test_battle_result_rejects_invalid_medal_counts(
    gold_medals: int, silver_medals: int
) -> None:
    with pytest.raises(DomainValidationError):
        BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=gold_medals,
            silver_medals=silver_medals,
        )

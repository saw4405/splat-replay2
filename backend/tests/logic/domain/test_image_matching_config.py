from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from splat_replay.domain.config import ImageMatchingSettings, MatchExpression


def test_repository_image_matching_config_has_valid_references() -> None:
    config_path = (
        Path(__file__).resolve().parents[3] / "config" / "image_matching.yaml"
    )

    settings = ImageMatchingSettings.load_from_yaml(config_path)

    assert "power_off" in settings.composites
    assert "power_off_template" in settings.matchers


def test_unknown_composite_matcher_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown_matcher"):
        ImageMatchingSettings.parse_obj(
            {
                "matchers": {},
                "composites": {
                    "power_off": {"rule": {"matcher": "unknown_matcher"}}
                },
            }
        )


def test_unknown_matcher_group_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown_matcher"):
        ImageMatchingSettings.parse_obj(
            {
                "matchers": {},
                "matcher_groups": {"group": ["unknown_matcher"]},
            }
        )


@pytest.mark.asyncio
async def test_match_expression_or_short_circuits_after_first_true_in_order() -> (
    None
):
    calls: list[str] = []

    async def matcher(name: str) -> bool:
        calls.append(name)
        if name == "raise_if_evaluated":
            raise RuntimeError("OR should have already matched")
        return name == "match"

    expression = MatchExpression.parse_obj(
        {
            "or": [
                {"matcher": "miss"},
                {"matcher": "match"},
                {"matcher": "raise_if_evaluated"},
            ]
        }
    )

    result = await expression.evaluate(matcher)

    assert result is True
    assert calls == ["miss", "match"]


@pytest.mark.asyncio
async def test_match_expression_and_short_circuits_after_first_false_in_order() -> (
    None
):
    calls: list[str] = []

    async def matcher(name: str) -> bool:
        calls.append(name)
        if name == "raise_if_evaluated":
            raise RuntimeError("AND should have already failed")
        return name == "match"

    expression = MatchExpression.parse_obj(
        {
            "and": [
                {"matcher": "match"},
                {"matcher": "miss"},
                {"matcher": "raise_if_evaluated"},
            ]
        }
    )

    result = await expression.evaluate(matcher)

    assert result is False
    assert calls == ["match", "miss"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expression", "matcher_results", "expected"),
    [
        (
            MatchExpression.parse_obj({"not": {"matcher": "child"}}),
            {"child": False},
            True,
        ),
        (MatchExpression.parse_obj({"or": []}), {}, False),
        (MatchExpression.parse_obj({"and": []}), {}, True),
        (MatchExpression(), {}, False),
    ],
    ids=["not", "empty-or", "empty-and", "unset"],
)
async def test_match_expression_keeps_existing_boolean_results(
    expression: MatchExpression,
    matcher_results: dict[str, bool],
    expected: bool,
) -> None:
    async def matcher(name: str) -> bool:
        return matcher_results[name]

    assert await expression.evaluate(matcher) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception_type", [RuntimeError, asyncio.CancelledError]
)
async def test_match_expression_propagates_evaluated_branch_failure(
    exception_type: type[BaseException],
) -> None:
    calls: list[str] = []

    async def matcher(name: str) -> bool:
        calls.append(name)
        raise exception_type("branch failure")

    expression = MatchExpression.parse_obj(
        {"or": [{"matcher": "failure"}, {"matcher": "not_evaluated"}]}
    )

    with pytest.raises(exception_type, match="branch failure"):
        await expression.evaluate(matcher)

    assert calls == ["failure"]

from __future__ import annotations

import numpy as np
import pytest

from splat_replay.infrastructure.adapters.weapon_detection.outline_models import (
    _find_best_shift,
    _iou_score,
    _shift_mask,
)


@pytest.mark.parametrize(
    ("dx", "dy", "expected"),
    [
        (
            0,
            0,
            [[0, 1, 0, 1], [1, 0, 1, 0], [0, 1, 0, 1]],
        ),
        (
            -1,
            1,
            [[0, 0, 0, 0], [1, 0, 1, 0], [0, 1, 0, 0]],
        ),
        (
            1,
            -1,
            [[0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 0]],
        ),
        (4, 0, [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]),
        (-4, 0, [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]),
        (0, 3, [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]),
        (0, -3, [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]),
    ],
)
def test_shift_mask_translates_non_binary_non_contiguous_input(
    dx: int,
    dy: int,
    expected: list[list[int]],
) -> None:
    backing = np.array(
        [
            [0, 9, 1, 9, 0, 9, 255, 9],
            [2, 9, 0, 9, 4, 9, 0, 9],
            [0, 9, 5, 9, 0, 9, 7, 9],
        ],
        dtype=np.uint8,
    )
    mask = backing[:, ::2]
    assert not mask.flags.c_contiguous

    shifted = _shift_mask(mask, dx, dy)

    assert shifted.dtype == np.uint8
    assert shifted.shape == mask.shape
    np.testing.assert_array_equal(shifted, np.array(expected, dtype=np.uint8))


def test_iou_score_uses_positive_pixel_union() -> None:
    mask_a = np.array([[2, 0, 1, 0], [0, -1, 0, 0]], dtype=np.int16)
    mask_b = np.array([[1, 0, 0, 0], [0, 3, 1, 0]], dtype=np.int16)

    assert _iou_score(mask_a, mask_b) == 0.25


def test_iou_score_returns_zero_when_both_masks_are_empty() -> None:
    empty = np.zeros((2, 3), dtype=np.uint8)

    assert _iou_score(empty, empty) == 0.0


@pytest.mark.parametrize(
    (
        "shape",
        "reference_points",
        "target_points",
        "max_shift",
        "expected_dx",
        "expected_dy",
        "expected_points",
    ),
    [
        (
            (5, 6),
            ((3, 3),),
            ((2, 1),),
            0,
            2,
            1,
            ((3, 3),),
        ),
        (
            (5, 6),
            ((1, 1),),
            ((3, 4),),
            0,
            -3,
            -2,
            ((1, 1),),
        ),
        ((5, 5), (), ((0, 0),), 2, 0, 0, ((0, 0),)),
        ((3, 4), (), (), 4, 0, 0, ()),
        (
            (3, 3),
            ((1, 1),),
            ((1, 1),),
            4,
            0,
            0,
            ((1, 1),),
        ),
    ],
    ids=(
        "positive_shift",
        "negative_shift",
        "shorter_tie",
        "empty",
        "out_of_bounds",
    ),
)
def test_find_best_shift_returns_expected_translation_and_mask(
    shape: tuple[int, int],
    reference_points: tuple[tuple[int, int], ...],
    target_points: tuple[tuple[int, int], ...],
    max_shift: int,
    expected_dx: int,
    expected_dy: int,
    expected_points: tuple[tuple[int, int], ...],
) -> None:
    reference = np.zeros(shape, dtype=np.uint8)
    target = np.zeros(shape, dtype=np.uint8)
    expected_mask = np.zeros(shape, dtype=np.uint8)
    for y, x in reference_points:
        reference[y, x] = 1
    for y, x in target_points:
        target[y, x] = 1
    for y, x in expected_points:
        expected_mask[y, x] = 1

    dx, dy, aligned = _find_best_shift(reference, target, max_shift)

    assert (dx, dy) == (expected_dx, expected_dy)
    np.testing.assert_array_equal(aligned, expected_mask)

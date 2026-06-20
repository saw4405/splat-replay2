from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from splat_replay.infrastructure.matchers.template import TemplateMatcher


def _write_dummy_template(path: Path) -> None:
    template = np.zeros((4, 4, 3), dtype=np.uint8)
    written = cv2.imwrite(str(path), template)
    assert written


def test_template_matcher_score_uses_top1_when_response_top_k_is_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template_path = tmp_path / "template.png"
    _write_dummy_template(template_path)
    matcher = TemplateMatcher(
        template_path=template_path,
        threshold=0.5,
        response_top_k=1,
    )

    response = np.array([[0.10, 0.40], [0.30, 0.20]], dtype=np.float32)

    def _stub_match_template(*args: object, **kwargs: object) -> np.ndarray:
        _ = args
        _ = kwargs
        return response

    monkeypatch.setattr(cv2, "matchTemplate", _stub_match_template)
    image = np.zeros((8, 8, 3), dtype=np.uint8)

    score = matcher._score(image)

    assert score == pytest.approx(0.40)


def test_template_matcher_score_uses_top_k_mean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template_path = tmp_path / "template.png"
    _write_dummy_template(template_path)
    matcher = TemplateMatcher(
        template_path=template_path,
        threshold=0.5,
        response_top_k=2,
    )

    response = np.array([[0.10, 0.40], [0.30, 0.20]], dtype=np.float32)

    def _stub_match_template(*args: object, **kwargs: object) -> np.ndarray:
        _ = args
        _ = kwargs
        return response

    monkeypatch.setattr(cv2, "matchTemplate", _stub_match_template)
    image = np.zeros((8, 8, 3), dtype=np.uint8)

    score = matcher._score(image)

    assert score == pytest.approx((0.40 + 0.30) / 2.0)


def test_template_matcher_rejects_invalid_response_top_k(
    tmp_path: Path,
) -> None:
    template_path = tmp_path / "template.png"
    _write_dummy_template(template_path)

    with pytest.raises(ValueError):
        TemplateMatcher(
            template_path=template_path,
            threshold=0.5,
            response_top_k=0,
        )

from pathlib import Path
from typing import Any

from PIL import ImageFont

from splat_replay.infrastructure.adapters.image import (
    thumbnail_font_resolver,
)


class _Mask:
    def getbbox(self) -> tuple[int, int, int, int]:
        return (0, 0, 10, 10)


class _Font:
    def getmask(self, text: str) -> _Mask:
        assert text == "日本語"
        return _Mask()


def test_resolver_keeps_a_loadable_preferred_font(
    tmp_path: Path, monkeypatch: Any
) -> None:
    preferred = tmp_path / "ikamodoki1.ttf"
    preferred.touch()
    monkeypatch.setattr(
        ImageFont, "truetype", lambda *_args, **_kwargs: _Font()
    )

    assert (
        thumbnail_font_resolver.ThumbnailFontResolver().resolve(preferred)
        == preferred
    )


def test_resolver_uses_typed_windows_japanese_font_candidates(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(thumbnail_font_resolver.sys, "platform", "win32")
    monkeypatch.setenv("WINDIR", "/windows")
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda path: path.name == "meiryo.ttc",
    )
    monkeypatch.setattr(
        ImageFont, "truetype", lambda *_args, **_kwargs: _Font()
    )

    resolved = thumbnail_font_resolver.ThumbnailFontResolver().resolve(
        Path("ikamodoki1.ttf")
    )

    assert resolved == Path("/windows/Fonts/meiryo.ttc")


def test_resolver_returns_none_when_no_candidate_can_be_loaded(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(thumbnail_font_resolver.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "is_file", lambda _path: False)

    assert (
        thumbnail_font_resolver.ThumbnailFontResolver().resolve(
            tmp_path / "ikamodoki1.ttf"
        )
        is None
    )

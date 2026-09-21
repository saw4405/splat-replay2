from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from splat_replay.application.interfaces import (
    FileSystemPort,
    ImageSelector,
    LoggerPort,
    PathsPort,
)
from splat_replay.application.services.editing.thumbnail_generator import (
    ThumbnailGenerator,
)
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
    VideoAsset,
    XP,
)


class _Logger:
    def debug(self, event: str, **kw: object) -> None:
        _ = event, kw

    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def warning(self, event: str, **kw: object) -> None:
        _ = event, kw

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw

    def exception(self, event: str, **kw: object) -> None:
        _ = event, kw


class _Paths:
    def __init__(self, root: Path) -> None:
        self._root = root

    def get_thumbnail_asset(self, filename: str) -> Path:
        return self._root / filename


class _FileSystem:
    def is_file(self, path: Path) -> bool:
        _ = path
        return True


class _Drawer:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.drawn_texts: list[str] = []
        self.drawn_text_calls: list[tuple[str, dict[str, Any]]] = []

    def draw_text_with_outline(
        self, text: str, *args: Any, **kw: Any
    ) -> "_Drawer":
        _ = args, kw
        self.drawn_texts.append(text)
        return self

    def draw_rounded_rectangle(self, *args: Any, **kw: Any) -> "_Drawer":
        _ = args, kw
        return self

    def draw_image(self, *args: Any, **kw: Any) -> "_Drawer":
        _ = args, kw
        return self

    def draw_text(self, text: str, *args: Any, **kw: Any) -> "_Drawer":
        _ = args
        self.drawn_texts.append(text)
        self.drawn_text_calls.append((text, kw))
        return self

    def when(self, condition: bool, callback: Any) -> "_Drawer":
        if condition:
            return cast(_Drawer, callback(self))
        return self

    def for_each(self, items: list[Any], callback: Any) -> "_Drawer":
        drawer: _Drawer = self
        for item in items:
            drawer = cast(_Drawer, callback(item, drawer))
        return drawer

    def draw_rectangle(self, *args: Any, **kw: Any) -> "_Drawer":
        _ = args, kw
        return self

    def overlay_image(self, *args: Any, **kw: Any) -> "_Drawer":
        _ = args, kw
        return self

    def save(self, out: Path) -> "_Drawer":
        self.out = out
        out.write_bytes(b"thumbnail")
        return self


class _ImageSelectorFactory:
    def __init__(self, out: Path) -> None:
        self.drawer = _Drawer(out)

    def __call__(
        self, thumbnails: list[Path], crop: tuple[int, int, int, float]
    ) -> _Drawer:
        _ = thumbnails, crop
        return self.drawer


def _asset(
    *,
    tmp_path: Path,
    name: str,
    match: Match,
    rate: XP,
) -> VideoAsset:
    video = tmp_path / f"{name}.mp4"
    thumbnail = tmp_path / f"{name}.png"
    video.write_bytes(b"video")
    thumbnail.write_bytes(b"png")
    return VideoAsset(
        video=video,
        thumbnail=thumbnail,
        metadata=RecordingMetadata(
            game_mode=GameMode.BATTLE,
            rate=rate,
            judgement=Judgement.WIN,
            result=BattleResult(
                match=match,
                rule=Rule.RAINMAKER,
                stage=Stage.HAMMERHEAD_BRIDGE,
                kill=7,
                death=5,
                special=2,
            ),
        ),
    )


def _generator(
    tmp_path: Path,
) -> tuple[ThumbnailGenerator, _ImageSelectorFactory]:
    selector = _ImageSelectorFactory(tmp_path / "out.png")
    generator = ThumbnailGenerator(
        logger=cast(LoggerPort, _Logger()),
        paths=cast(PathsPort, _Paths(tmp_path)),
        image_selector=cast(ImageSelector, selector),
        file_system=cast(FileSystemPort, _FileSystem()),
    )
    return generator, selector


def test_thumbnail_uses_highest_event_power_only_for_event_match(
    tmp_path: Path,
) -> None:
    generator, selector = _generator(tmp_path)

    out = generator.create(
        [
            _asset(
                tmp_path=tmp_path,
                name="first",
                match=Match.CHALLENGE,
                rate=XP(2105.7),
            ),
            _asset(
                tmp_path=tmp_path,
                name="second",
                match=Match.CHALLENGE,
                rate=XP(2180.0),
            ),
        ]
    )

    assert out is not None
    assert "Best Power: 2180.0" in selector.drawer.drawn_texts
    assert (
        "Best Power: 2180.0",
        {"fill_color": (241, 46, 125)},
    ) in selector.drawer.drawn_text_calls
    assert all(
        "2105.7 ~ 2180.0" not in text for text in selector.drawer.drawn_texts
    )


def test_thumbnail_keeps_x_power_range_for_x_match(tmp_path: Path) -> None:
    generator, selector = _generator(tmp_path)

    out = generator.create(
        [
            _asset(
                tmp_path=tmp_path,
                name="first",
                match=Match.X,
                rate=XP(2105.7),
            ),
            _asset(
                tmp_path=tmp_path,
                name="second",
                match=Match.X,
                rate=XP(2180.0),
            ),
        ]
    )

    assert out is not None
    assert "XP: 2105.7 ~ 2180.0" in selector.drawer.drawn_texts


def test_thumbnail_uses_unique_temporary_path_per_call(
    tmp_path: Path,
) -> None:
    generator, _ = _generator(tmp_path)
    assets = [
        _asset(
            tmp_path=tmp_path,
            name="first",
            match=Match.X,
            rate=XP(2105.7),
        )
    ]

    first = generator.create(assets)
    second = generator.create(assets)

    assert first is not None
    assert second is not None
    assert first != second
    assert first.name.endswith(".thumb.png")
    assert second.name.endswith(".thumb.png")


def test_thumbnail_returns_none_when_no_source_thumbnail_is_available(
    tmp_path: Path,
) -> None:
    source = _asset(
        tmp_path=tmp_path,
        name="missing-thumbnail",
        match=Match.X,
        rate=XP(2105.7),
    )
    asset = VideoAsset(video=source.video, metadata=source.metadata)

    def select_missing_image(
        thumbnails: list[Path], crop: tuple[float, float, float, float]
    ) -> None:
        assert thumbnails == []
        _ = crop
        return None

    generator = ThumbnailGenerator(
        logger=cast(LoggerPort, _Logger()),
        paths=cast(PathsPort, _Paths(tmp_path)),
        image_selector=cast(ImageSelector, select_missing_image),
        file_system=cast(FileSystemPort, _FileSystem()),
    )

    assert generator.create([asset]) is None

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from splat_replay.application.interfaces import (
    FileSystemPort,
    ImageSelector,
    LoggerPort,
    PathsPort,
    ThumbnailFontResolverPort,
)
from splat_replay.application.services.editing.thumbnail_generator import (
    ThumbnailGenerator,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
    SystemCheckService,
)
from splat_replay.application.services.system.software_checker import (
    SoftwareChecker,
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
    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw


class _FontResolver:
    def __init__(self, resolved: Path | None) -> None:
        self.resolved = resolved
        self.preferred_paths: list[Path] = []

    def resolve(self, preferred_path: Path) -> Path | None:
        self.preferred_paths.append(preferred_path)
        return self.resolved


class _Paths:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get_thumbnail_assets_dir(self) -> Path:
        return self.root

    def get_thumbnail_asset(self, filename: str) -> Path:
        return self.root / filename

    def get_config_dir(self) -> Path:
        return self.root


class _FileSystem:
    def is_file(self, path: Path) -> bool:
        _ = path
        return True


class _Checker:
    def check(self) -> SoftwareCheckResult:
        return SoftwareCheckResult(is_installed=False)


class _Environment:
    def get(self, name: str, default: str | None = None) -> str | None:
        _ = name
        return default


class _Drawer:
    def __init__(self) -> None:
        self.font_names: list[str] = []

    def draw_text_with_outline(self, *args: Any, **kwargs: Any) -> _Drawer:
        _ = args, kwargs
        return self

    def draw_rounded_rectangle(self, *args: Any, **kwargs: Any) -> _Drawer:
        _ = args, kwargs
        return self

    def draw_image(self, *args: Any, **kwargs: Any) -> _Drawer:
        _ = args, kwargs
        return self

    def draw_text(self, text: str, *args: Any, **kwargs: Any) -> _Drawer:
        _ = text, kwargs
        self.font_names.append(cast(str, args[1]))
        return self

    def when(self, flag: bool, fn: Any) -> _Drawer:
        if flag:
            fn(self)
        return self

    def for_each(self, items: list[Any], fn: Any) -> _Drawer:
        for item in items:
            fn(item, self)
        return self

    def draw_rectangle(self, *args: Any, **kwargs: Any) -> _Drawer:
        _ = args, kwargs
        return self

    def overlay_image(self, *args: Any, **kwargs: Any) -> _Drawer:
        _ = args, kwargs
        return self

    def save(self, path: Path) -> None:
        path.write_bytes(b"thumbnail")


def _system_check_service(
    root: Path, resolver: _FontResolver
) -> SystemCheckService:
    checker = cast(SoftwareChecker, _Checker())
    return SystemCheckService(
        obs_checker=checker,
        ffmpeg_checker=checker,
        tesseract_checker=checker,
        flac_checker=checker,
        ndi_checker=checker,
        font_resolver=cast(ThumbnailFontResolverPort, resolver),
        paths=cast(PathsPort, _Paths(root)),
        file_system=cast(FileSystemPort, _FileSystem()),
        environment=cast(Any, _Environment()),
        logger=cast(LoggerPort, _Logger()),
    )


def _asset(tmp_path: Path) -> VideoAsset:
    video = tmp_path / "match.mp4"
    thumbnail = tmp_path / "match.png"
    video.write_bytes(b"video")
    thumbnail.write_bytes(b"image")
    return VideoAsset(
        video=video,
        thumbnail=thumbnail,
        metadata=RecordingMetadata(
            game_mode=GameMode.BATTLE,
            rate=XP(2000.0),
            judgement=Judgement.WIN,
            result=BattleResult(
                match=Match.X,
                rule=Rule.RAINMAKER,
                stage=Stage.HAMMERHEAD_BRIDGE,
                kill=2,
                death=0,
                special=1,
            ),
        ),
    )


def test_setup_check_accepts_the_same_resolved_system_font(
    tmp_path: Path,
) -> None:
    fallback = tmp_path / "Hiragino Sans.ttc"
    resolver = _FontResolver(fallback)

    result = _system_check_service(
        tmp_path, resolver
    ).check_font_installation()

    assert result.is_installed
    assert result.installation_path == fallback
    assert resolver.preferred_paths == [tmp_path / "ikamodoki1.ttf"]


def test_setup_check_does_not_report_success_without_a_usable_font(
    tmp_path: Path,
) -> None:
    result = _system_check_service(
        tmp_path, _FontResolver(None)
    ).check_font_installation()

    assert not result.is_installed
    assert "日本語フォント" in (result.error_message or "")


def test_thumbnail_uses_resolved_font_and_fails_when_no_fallback_exists(
    tmp_path: Path,
) -> None:
    fallback = tmp_path / "Hiragino Sans.ttc"
    resolver = _FontResolver(fallback)
    drawer = _Drawer()
    generator = ThumbnailGenerator(
        logger=cast(LoggerPort, _Logger()),
        paths=cast(PathsPort, _Paths(tmp_path)),
        image_selector=cast(ImageSelector, lambda *_args: drawer),
        file_system=cast(FileSystemPort, _FileSystem()),
        font_resolver=cast(ThumbnailFontResolverPort, resolver),
    )

    output = generator.create([_asset(tmp_path)])

    assert output is not None
    assert str(fallback) in drawer.font_names

    unavailable_generator = ThumbnailGenerator(
        logger=cast(LoggerPort, _Logger()),
        paths=cast(PathsPort, _Paths(tmp_path)),
        image_selector=cast(ImageSelector, lambda *_args: _Drawer()),
        file_system=cast(FileSystemPort, _FileSystem()),
        font_resolver=cast(ThumbnailFontResolverPort, _FontResolver(None)),
    )
    with pytest.raises(RuntimeError, match="日本語フォントを利用できません"):
        unavailable_generator.create([_asset(tmp_path)])

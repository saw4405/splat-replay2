from __future__ import annotations

from pathlib import Path

import punq
import pytest

from splat_replay.infrastructure.di import config as di_config
from splat_replay.infrastructure.adapters.system.cross_cutting import (
    FileSystemPathsAdapter,
)
from splat_replay.infrastructure.filesystem import paths


def _prepare_image_matching_config_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, Path]:
    project_root = tmp_path / "bundle"
    bundled_config = project_root / "config" / "image_matching.yaml"
    bundled_config.parent.mkdir(parents=True)
    runtime_config = tmp_path / "Application Support" / "config"
    monkeypatch.setattr(paths, "IS_MACOS_FROZEN", True)
    monkeypatch.setattr(paths, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(
        paths, "IMAGE_MATCHING_FILE", runtime_config / "image_matching.yaml"
    )
    return bundled_config, runtime_config / "image_matching.yaml"


def test_macos_frozen_paths_use_application_support_and_bundle_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_bundle = tmp_path / "SplatReplay.app"
    executable = app_bundle / "Contents" / "MacOS" / "SplatReplay"
    resources = app_bundle / "Contents" / "Resources"
    frameworks = app_bundle / "Contents" / "Frameworks"
    home = tmp_path / "home"
    resources.mkdir(parents=True)
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(frameworks), raising=False)
    monkeypatch.setattr(Path, "home", lambda: home)

    data_root = paths._get_runtime_root()

    assert data_root == (
        home
        / "Library"
        / "Application Support"
        / "io.github.saw4405.splatreplay"
    )
    assert paths._get_project_root() == resources
    assert paths._get_assets_dir() == resources / "assets"
    assert paths._get_thumbnail_assets_dir() == (
        data_root / "assets" / "thumbnail"
    )
    assert not data_root.is_relative_to(app_bundle)


@pytest.mark.parametrize(
    ("platform", "frozen"), [("win32", True), ("darwin", False)]
)
def test_windows_frozen_and_development_paths_keep_existing_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    frozen: bool,
) -> None:
    executable = tmp_path / "SplatReplay.exe"
    monkeypatch.setattr(paths.sys, "platform", platform)
    monkeypatch.setattr(paths.sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    expected_root = tmp_path if frozen else Path(__file__).resolve().parents[3]

    assert paths._get_runtime_root() == expected_root
    assert paths._get_assets_dir() == expected_root / "assets"
    assert paths._get_thumbnail_assets_dir() == (
        expected_root / "assets" / "thumbnail"
    )


def test_macos_frozen_image_matching_config_is_copied_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, runtime_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    bundled_config.write_text("simple_matchers: {}\n", encoding="utf-8")

    di_config.register_image_matching_settings(punq.Container())

    assert runtime_config.read_bytes() == bundled_config.read_bytes()
    assert runtime_config.with_name(
        "image_matching.yaml.baseline"
    ).read_bytes() == (bundled_config.read_bytes())
    assert not list(runtime_config.parent.glob("*.tmp"))


def test_macos_frozen_image_matching_config_does_not_overwrite_user_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, user_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    bundled_config.write_text("simple_matchers: {}\n", encoding="utf-8")
    user_config.parent.mkdir(parents=True)
    user_config.write_text(
        "# user change\nsimple_matchers: {}\n", encoding="utf-8"
    )
    baseline = user_config.with_name("image_matching.yaml.baseline")
    baseline.write_bytes(b"simple_matchers: {}\n")
    original_config = user_config.read_bytes()
    original_baseline = baseline.read_bytes()

    di_config.register_image_matching_settings(punq.Container())

    assert user_config.read_bytes() == original_config
    assert baseline.read_bytes() == original_baseline


def test_macos_frozen_image_matching_config_updates_only_from_previous_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, current_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    baseline = current_config.with_name("image_matching.yaml.baseline")
    previous_default = b"simple_matchers: {}\n# previous default\n"
    current_default = b"simple_matchers: {}\n# current default\n"
    next_default = b"simple_matchers: {}\n# next default\n"
    current_config.parent.mkdir(parents=True)
    current_config.write_bytes(previous_default)
    baseline.write_bytes(previous_default)
    bundled_config.write_bytes(current_default)

    di_config.register_image_matching_settings(punq.Container())

    assert current_config.read_bytes() == current_default
    assert baseline.read_bytes() == current_default

    bundled_config.write_bytes(next_default)
    di_config.register_image_matching_settings(punq.Container())

    assert current_config.read_bytes() == next_default
    assert baseline.read_bytes() == next_default
    assert not list(current_config.parent.glob("*.tmp"))


def test_macos_frozen_image_matching_config_does_not_migrate_unknown_old_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, current_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    unknown_old_config = b"simple_matchers: {}\n# unknown old default\n"
    current_config.parent.mkdir(parents=True)
    current_config.write_bytes(unknown_old_config)
    bundled_config.write_bytes(b"simple_matchers: {}\n# new default\n")
    baseline = current_config.with_name("image_matching.yaml.baseline")

    di_config.register_image_matching_settings(punq.Container())

    assert current_config.read_bytes() == unknown_old_config
    assert not baseline.exists()


def test_macos_frozen_image_matching_config_recovers_baseline_after_write_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, current_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    baseline = current_config.with_name("image_matching.yaml.baseline")
    current_default = b"simple_matchers: {}\n# current default\n"
    current_config.parent.mkdir(parents=True)
    bundled_config.write_bytes(current_default)

    original_replace = Path.replace

    def fail_baseline_replace(source: Path, target: str | Path) -> Path:
        if Path(target) == baseline:
            raise OSError("simulated baseline replacement failure")
        return original_replace(source, target)

    with monkeypatch.context() as failure_patch:
        failure_patch.setattr(Path, "replace", fail_baseline_replace)
        di_config.register_image_matching_settings(punq.Container())

    assert current_config.read_bytes() == current_default
    assert not baseline.exists()
    assert not list(current_config.parent.glob("*.tmp"))

    di_config.register_image_matching_settings(punq.Container())

    assert baseline.read_bytes() == current_default


def test_atomic_config_write_preserves_replace_error_when_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "image_matching.yaml"
    target.write_bytes(b"original")
    original_replace = Path.replace
    original_unlink = Path.unlink

    def fail_replace(source: Path, destination: str | Path) -> Path:
        if Path(destination) == target:
            raise OSError("simulated replace failure")
        return original_replace(source, destination)

    def fail_temp_cleanup(path: Path, *, missing_ok: bool = False) -> None:
        if (
            path.name.startswith("image_matching.yaml.")
            and path.suffix == ".tmp"
        ):
            raise OSError("simulated cleanup failure")
        original_unlink(path, missing_ok=missing_ok)

    with monkeypatch.context() as failure_patch:
        failure_patch.setattr(Path, "replace", fail_replace)
        failure_patch.setattr(Path, "unlink", fail_temp_cleanup)
        with pytest.raises(OSError, match="simulated replace failure"):
            di_config._write_bytes_atomically(target, b"new")

    assert target.read_bytes() == b"original"
    for temporary_path in tmp_path.glob("*.tmp"):
        temporary_path.unlink()


def test_macos_frozen_image_matching_config_keeps_current_if_replace_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, current_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    baseline = current_config.with_name("image_matching.yaml.baseline")
    previous_default = b"simple_matchers: {}\n# previous default\n"
    current_default = b"simple_matchers: {}\n# current default\n"
    current_config.parent.mkdir(parents=True)
    current_config.write_bytes(previous_default)
    baseline.write_bytes(previous_default)
    bundled_config.write_bytes(current_default)
    original_replace = Path.replace

    def fail_current_replace(source: Path, target: str | Path) -> Path:
        if Path(target) == current_config:
            raise OSError("simulated current replacement failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_current_replace)

    di_config.register_image_matching_settings(punq.Container())

    assert current_config.read_bytes() == previous_default
    assert baseline.read_bytes() == previous_default
    assert not list(current_config.parent.glob("*.tmp"))


def test_macos_frozen_image_matching_config_keeps_edit_before_replace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, current_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    baseline = current_config.with_name("image_matching.yaml.baseline")
    previous_default = b"simple_matchers: {}\n# previous default\n"
    current_default = b"simple_matchers: {}\n# current default\n"
    user_edit = b"simple_matchers: {}\n# user edit\n"
    current_config.parent.mkdir(parents=True)
    current_config.write_bytes(previous_default)
    baseline.write_bytes(previous_default)
    bundled_config.write_bytes(current_default)
    original_read_bytes = Path.read_bytes
    current_reads = 0

    def edit_current_before_replace(path: Path) -> bytes:
        nonlocal current_reads
        if path == current_config:
            current_reads += 1
            if current_reads == 2:
                path.write_bytes(user_edit)
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", edit_current_before_replace)

    di_config.register_image_matching_settings(punq.Container())

    assert original_read_bytes(current_config) == user_edit
    assert original_read_bytes(baseline) == previous_default
    assert not list(current_config.parent.glob("*.tmp"))


def test_macos_frozen_image_matching_config_keeps_current_if_baseline_read_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, current_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    baseline = current_config.with_name("image_matching.yaml.baseline")
    previous_default = b"simple_matchers: {}\n# previous default\n"
    current_config.parent.mkdir(parents=True)
    current_config.write_bytes(previous_default)
    baseline.write_bytes(previous_default)
    bundled_config.write_bytes(b"simple_matchers: {}\n# current default\n")
    original_read_bytes = Path.read_bytes

    def fail_baseline_read(path: Path) -> bytes:
        if path == baseline:
            raise OSError("simulated baseline read failure")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_baseline_read)

    di_config.register_image_matching_settings(punq.Container())

    assert original_read_bytes(current_config) == previous_default
    assert original_read_bytes(baseline) == previous_default


def test_macos_frozen_image_matching_config_does_not_replace_invalid_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, current_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    previous_default = b"simple_matchers: {}\n# previous default\n"
    current_config.parent.mkdir(parents=True)
    current_config.write_bytes(previous_default)
    current_config.with_name("image_matching.yaml.baseline").write_bytes(
        previous_default
    )
    bundled_config.write_text("simple_matchers: [invalid]\n", encoding="utf-8")

    di_config.register_image_matching_settings(punq.Container())

    assert current_config.read_bytes() == previous_default


def test_explicit_image_matching_config_path_is_not_migrated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled_config, _ = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    explicit_config = tmp_path / "explicit" / "image_matching.yaml"
    explicit_config.parent.mkdir(parents=True)
    previous_default = b"simple_matchers: {}\n# previous default\n"
    explicit_config.write_bytes(previous_default)
    explicit_config.with_name("image_matching.yaml.baseline").write_bytes(
        previous_default
    )
    bundled_config.write_bytes(b"simple_matchers: {}\n# current default\n")

    di_config.register_image_matching_settings(
        punq.Container(), path=explicit_config
    )

    assert explicit_config.read_bytes() == previous_default
    assert explicit_config.with_name(
        "image_matching.yaml.baseline"
    ).read_bytes() == (previous_default)


@pytest.mark.parametrize(
    ("platform", "frozen"), [("win32", True), ("darwin", False)]
)
def test_non_macos_frozen_image_matching_config_is_not_migrated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    frozen: bool,
) -> None:
    bundled_config, current_config = _prepare_image_matching_config_files(
        monkeypatch, tmp_path
    )
    previous_default = b"simple_matchers: {}\n# previous default\n"
    current_config.parent.mkdir(parents=True)
    current_config.write_bytes(previous_default)
    baseline = current_config.with_name("image_matching.yaml.baseline")
    baseline.write_bytes(previous_default)
    bundled_config.write_bytes(b"simple_matchers: {}\n# current default\n")
    monkeypatch.setattr(paths.sys, "platform", platform)
    monkeypatch.setattr(paths.sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(paths, "IS_MACOS_FROZEN", False)

    di_config.register_image_matching_settings(punq.Container())

    assert current_config.read_bytes() == previous_default
    assert baseline.read_bytes() == previous_default


def test_macos_thumbnail_assets_prefer_user_files_and_fall_back_to_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    user_thumbnail_dir = (
        tmp_path / "Application Support" / "assets" / "thumbnail"
    )
    bundled_assets_dir = tmp_path / "bundle" / "assets"
    bundled_thumbnail_dir = bundled_assets_dir / "thumbnail"
    bundled_thumbnail_dir.mkdir(parents=True)
    (bundled_thumbnail_dir / "stage.png").write_bytes(b"bundle")
    monkeypatch.setattr(paths, "IS_MACOS_FROZEN", True)
    monkeypatch.setattr(paths, "THUMBNAIL_ASSETS_DIR", user_thumbnail_dir)
    monkeypatch.setattr(paths, "ASSETS_DIR", bundled_assets_dir)
    adapter = FileSystemPathsAdapter()

    assert adapter.get_thumbnail_assets_dir() == user_thumbnail_dir
    assert adapter.get_thumbnail_asset("stage.png") == (
        bundled_thumbnail_dir / "stage.png"
    )
    assert adapter.get_thumbnail_asset("ikamodoki1.ttf") == (
        user_thumbnail_dir / "ikamodoki1.ttf"
    )

    user_thumbnail_dir.mkdir(parents=True)
    (user_thumbnail_dir / "stage.png").write_bytes(b"user")
    assert adapter.get_thumbnail_asset("stage.png") == (
        user_thumbnail_dir / "stage.png"
    )


def test_non_macos_thumbnail_assets_keep_the_existing_bundle_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    thumbnail_dir = tmp_path / "assets" / "thumbnail"
    monkeypatch.setattr(paths, "IS_MACOS_FROZEN", False)
    monkeypatch.setattr(paths, "THUMBNAIL_ASSETS_DIR", thumbnail_dir)
    adapter = FileSystemPathsAdapter()

    assert adapter.get_thumbnail_assets_dir() == thumbnail_dir
    assert adapter.get_thumbnail_asset("stage.png") == (
        thumbnail_dir / "stage.png"
    )

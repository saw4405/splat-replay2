from __future__ import annotations

from splat_replay.interface.gui.webview_runtime import (
    configure_webview2_browser_arguments,
    normalize_webview_render_mode,
)


def test_normalize_webview_render_mode_defaults_to_gpu() -> None:
    assert normalize_webview_render_mode(None) == "gpu"
    assert normalize_webview_render_mode("BROKEN") == "gpu"
    assert normalize_webview_render_mode("GPU") == "gpu"


def test_configure_webview2_browser_arguments_adds_disable_gpu_on_windows() -> (
    None
):
    env: dict[str, str] = {}

    configured = configure_webview2_browser_arguments(
        env, platform="win32", render_mode="cpu"
    )

    assert configured == "--disable-gpu"
    assert env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == "--disable-gpu"


def test_configure_webview2_browser_arguments_appends_to_existing_args() -> (
    None
):
    env = {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--foo=bar"}

    configured = configure_webview2_browser_arguments(
        env, platform="win32", render_mode="cpu"
    )

    assert configured == "--foo=bar --disable-gpu"
    assert env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == (
        "--foo=bar --disable-gpu"
    )


def test_configure_webview2_browser_arguments_does_not_duplicate_flag() -> (
    None
):
    env = {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--disable-gpu --foo=bar"}

    configured = configure_webview2_browser_arguments(
        env, platform="win32", render_mode="cpu"
    )

    assert configured == "--disable-gpu --foo=bar"
    assert env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == (
        "--disable-gpu --foo=bar"
    )


def test_gpu_mode_removes_disable_gpu_flag_but_preserves_other_args() -> None:
    env = {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--disable-gpu --foo=bar"}

    configured = configure_webview2_browser_arguments(
        env, platform="win32", render_mode="gpu"
    )

    assert configured == "--foo=bar"
    assert env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == "--foo=bar"


def test_gpu_mode_removes_env_var_when_disable_gpu_was_the_only_flag() -> None:
    env = {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--disable-gpu"}

    configured = configure_webview2_browser_arguments(
        env, platform="win32", render_mode="gpu"
    )

    assert configured == ""
    assert "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS" not in env


def test_configure_webview2_browser_arguments_skips_non_windows() -> None:
    env = {"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--foo=bar"}

    configured = configure_webview2_browser_arguments(
        env, platform="linux", render_mode="cpu"
    )

    assert configured is None
    assert env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == "--foo=bar"

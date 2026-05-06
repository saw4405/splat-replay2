from __future__ import annotations

import os
from unittest.mock import Mock

import uvicorn
from fastapi import FastAPI
from typer import Typer
from typer.testing import CliRunner

from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.interface.cli.main import (
    CliDependencies,
    WebViewApp,
    build_app,
    resolve_web_bind_host,
)


class _Logger:
    def info(self, *args: object, **kwargs: object) -> None:
        pass

    def error(self, *args: object, **kwargs: object) -> None:
        pass


def _unused_auto_use_case() -> AutoUseCase:
    raise AssertionError("This dependency should not be used in this test")


def _unused_upload_use_case() -> UploadUseCase:
    raise AssertionError("This dependency should not be used in this test")


def _unused_webview_app() -> WebViewApp:
    raise AssertionError("This dependency should not be used in this test")


def _unused_dependency() -> None:
    raise AssertionError("This dependency should not be used in this test")


def _build_test_app(
    *,
    remote_access_enabled: bool,
) -> Typer:
    web_app = FastAPI()
    deps = CliDependencies(
        auto_use_case=_unused_auto_use_case,
        upload_use_case=_unused_upload_use_case,
        logger=lambda: _Logger(),
        web_app=lambda: web_app,
        webview_app=_unused_webview_app,
        start_dev_server=_unused_dependency,
        remote_access_enabled=lambda: remote_access_enabled,
    )
    return build_app(deps)


def test_web_command_default_host_uses_lan_bind_when_remote_access_enabled() -> (
    None
):
    assert (
        resolve_web_bind_host(requested_host=None, remote_access_enabled=True)
        == "0.0.0.0"
    )


def test_web_command_default_host_uses_loopback_when_remote_access_disabled() -> (
    None
):
    assert (
        resolve_web_bind_host(requested_host=None, remote_access_enabled=False)
        == "127.0.0.1"
    )


def test_web_command_explicit_host_overrides_remote_access_setting() -> None:
    assert (
        resolve_web_bind_host(
            requested_host="127.0.0.1",
            remote_access_enabled=True,
        )
        == "127.0.0.1"
    )


def test_web_command_binds_to_lan_when_remote_access_is_enabled(
    monkeypatch,
) -> None:
    run_mock = Mock(return_value=None)
    monkeypatch.setattr(uvicorn, "run", run_mock)
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_BIND_HOST", "")
    monkeypatch.setenv("SPLAT_REPLAY_BACKEND_PORT", "")

    cli_app = _build_test_app(
        remote_access_enabled=True,
    )

    result = CliRunner().invoke(cli_app, ["web"])

    assert result.exit_code == 0
    run_mock.assert_called_once()
    assert run_mock.call_args.kwargs["host"] == "0.0.0.0"
    assert os.environ["SPLAT_REPLAY_BACKEND_BIND_HOST"] == "0.0.0.0"


def test_web_command_explicit_host_keeps_loopback_bind(
    monkeypatch,
) -> None:
    run_mock = Mock(return_value=None)
    monkeypatch.setattr(uvicorn, "run", run_mock)

    cli_app = _build_test_app(
        remote_access_enabled=True,
    )

    result = CliRunner().invoke(cli_app, ["web", "--host", "127.0.0.1"])

    assert result.exit_code == 0
    run_mock.assert_called_once()
    assert run_mock.call_args.kwargs["host"] == "127.0.0.1"

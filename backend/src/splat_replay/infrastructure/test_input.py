"""E2E 用の動画リプレイ入力を解決するヘルパー。"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from splat_replay.application.dto import ReplayBootstrapDTO
from splat_replay.application.interfaces import ReplayBootstrapResolverPort
from splat_replay.domain.models import GameMode
from splat_replay.infrastructure.filesystem import paths

WINDOWS_PATH_RE = re.compile(r"^(?P<drive>[a-zA-Z]):[\\/](?P<rest>.*)$")
WSL_PATH_RE = re.compile(r"^/mnt/(?P<drive>[a-zA-Z])/(?P<rest>.*)$")
E2E_REPLAY_INPUT_FILE = "e2e-replay-input.json"


@dataclass(frozen=True)
class ResolvedTestVideo:
    """E2E 実行時に解決したテスト用動画。"""

    configured_path: Path
    selected_path: Path
    replay_bootstrap: ReplayBootstrapDTO | None = None


class ConfiguredReplayBootstrapResolver(ReplayBootstrapResolverPort):
    """現在の replay input から bootstrap を解決する。"""

    def resolve(self) -> ReplayBootstrapDTO | None:
        resolved = resolve_configured_test_video()
        if resolved is None:
            return None
        return resolved.replay_bootstrap


def resolve_replay_input_file_path() -> Path:
    """E2E replay input ファイルの保存先を返す。"""
    settings_file = os.getenv("SPLAT_REPLAY_SETTINGS_FILE")
    if settings_file:
        return Path(settings_file).resolve().parent / E2E_REPLAY_INPUT_FILE
    return paths.SETTINGS_FILE.parent / E2E_REPLAY_INPUT_FILE


def normalize_input_path(raw_path: str | Path) -> Path:
    """Windows/WSL 混在のパス表記を正規化する。"""
    text = str(raw_path).strip()
    if not text:
        return Path()

    match = WINDOWS_PATH_RE.match(text)
    if match:
        if os.name == "nt":
            return Path(text)
        drive = match.group("drive").lower()
        rest = match.group("rest").replace("\\", "/").lstrip("/")
        return Path(f"/mnt/{drive}/{rest}")

    wsl_match = WSL_PATH_RE.match(text)
    if wsl_match and os.name == "nt":
        drive = wsl_match.group("drive").upper()
        rest = wsl_match.group("rest").replace("/", "\\")
        return Path(f"{drive}:\\{rest}")

    return Path(text).expanduser()


def resolve_video_input_path(raw_path: str | Path) -> Path:
    """動画ファイルまたはディレクトリから実際に使う動画を 1 本解決する。"""
    if not str(raw_path).strip():
        raise FileNotFoundError("video_path が空です")

    candidate = normalize_input_path(raw_path)
    resolved = candidate.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"動画入力が見つかりません: {resolved}")

    if resolved.is_file():
        return resolved

    mkv_files = sorted(
        path
        for path in resolved.iterdir()
        if path.is_file() and path.suffix.lower() == ".mkv"
    )
    if not mkv_files:
        raise FileNotFoundError(f".mkv ファイルが見つかりません: {resolved}")
    selected = min(
        mkv_files,
        key=lambda path: (path.stat().st_size, path.name.lower()),
    )
    return selected.resolve()


def _parse_game_mode(raw_value: object) -> GameMode | None:
    if not isinstance(raw_value, str):
        return None

    normalized = raw_value.strip().upper()
    if not normalized:
        return None

    try:
        return GameMode[normalized]
    except KeyError:
        return None


def _parse_replay_bootstrap(raw_value: object) -> ReplayBootstrapDTO | None:
    if not isinstance(raw_value, dict):
        return None

    raw_dict = cast(dict[str, object], raw_value)
    phase = raw_dict.get("phase")
    if not isinstance(phase, str):
        return None

    normalized_phase = phase.strip().lower()
    if not normalized_phase:
        return None

    return ReplayBootstrapDTO(
        phase=normalized_phase,
        game_mode=_parse_game_mode(raw_dict.get("game_mode")),
    )


def resolve_configured_test_video() -> ResolvedTestVideo | None:
    """現在の E2E replay input からテスト用動画を解決する。"""
    input_file = resolve_replay_input_file_path()
    if not input_file.exists():
        return None

    payload = json.loads(input_file.read_text(encoding="utf-8"))
    configured_path = str(payload.get("video_path", "")).strip()
    if not configured_path:
        return None

    normalized_path = normalize_input_path(configured_path).resolve()
    selected_path = resolve_video_input_path(configured_path)
    scenario = payload.get("scenario")
    replay_bootstrap = None
    if isinstance(scenario, dict):
        replay_bootstrap = _parse_replay_bootstrap(
            scenario.get("replay_bootstrap")
        )
    return ResolvedTestVideo(
        configured_path=normalized_path,
        selected_path=selected_path,
        replay_bootstrap=replay_bootstrap,
    )

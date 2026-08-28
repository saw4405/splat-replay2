"""E2E 用の動画リプレイ入力を解決するヘルパー。"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from splat_replay.application.dto import ReplayBootstrapDTO
from splat_replay.application.interfaces import ReplayBootstrapResolverPort
from splat_replay.domain.models import GameMode
from splat_replay.domain.ports import OCRPurpose
from splat_replay.infrastructure.filesystem import paths

WINDOWS_PATH_RE = re.compile(r"^(?P<drive>[a-zA-Z]):[\\/](?P<rest>.*)$")
WSL_PATH_RE = re.compile(r"^/mnt/(?P<drive>[a-zA-Z])/(?P<rest>.*)$")
E2E_REPLAY_INPUT_FILE = "e2e-replay-input.json"
REPLAY_WEAPON_SLOT_NAMES = (
    "ally_1",
    "ally_2",
    "ally_3",
    "ally_4",
    "enemy_1",
    "enemy_2",
    "enemy_3",
    "enemy_4",
)
REPLAY_OCR_PURPOSE_NAMES = frozenset(purpose.value for purpose in OCRPurpose)


@dataclass(frozen=True)
class ResolvedTestVideo:
    """E2E 実行時に解決したテスト用動画。"""

    configured_path: Path
    selected_path: Path
    replay_bootstrap: ReplayBootstrapDTO | None = None


@dataclass(frozen=True)
class ReplayWeaponDisplayObservation:
    """replay 入力から得たブキ表示判定の観測。"""

    is_visible: bool
    should_recognize: bool


@dataclass(frozen=True)
class ReplayWeaponSlotObservation:
    """replay 入力から得た1スロット分のブキ認識観測。"""

    slot: str
    weapon: str
    matched: bool


@dataclass(frozen=True)
class ReplayWeaponRecognitionObservation:
    """replay 入力から得たブキ認識ポートの観測。"""

    display: ReplayWeaponDisplayObservation
    slots: tuple[ReplayWeaponSlotObservation, ...]


@dataclass(frozen=True)
class ReplayBattleMedalObservation:
    """replay 入力から得た表彰認識ポートの観測。"""

    gold: int
    silver: int


class ConfiguredReplayBootstrapResolver(ReplayBootstrapResolverPort):
    """現在の replay input から bootstrap を解決する。"""

    def resolve(self) -> ReplayBootstrapDTO | None:
        resolved = resolve_configured_test_video()
        if resolved is None:
            return None
        return resolved.replay_bootstrap


def resolve_replay_weapon_recognition_observation() -> (
    ReplayWeaponRecognitionObservation
):
    """現在の replay input からブキ認識観測を厳密に解決する。"""
    input_file = resolve_replay_input_file_path()
    if not input_file.exists():
        raise RuntimeError(
            "replay input が見つからないためブキ認識観測を解決できません"
        )

    try:
        payload = json.loads(input_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            "replay input のブキ認識観測を読み込めません"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            "replay input は JSON オブジェクトである必要があります"
        )

    raw_observations = payload.get("observations")
    if not isinstance(raw_observations, dict):
        raise RuntimeError("replay input に observations が必要です")
    raw_weapon_recognition = raw_observations.get("weapon_recognition")
    if not isinstance(raw_weapon_recognition, dict):
        raise RuntimeError("observations.weapon_recognition が必要です")

    raw_display = raw_weapon_recognition.get("display")
    if not isinstance(raw_display, dict):
        raise RuntimeError("weapon_recognition.display が必要です")
    is_visible = raw_display.get("is_visible")
    should_recognize = raw_display.get("should_recognize")
    if not isinstance(is_visible, bool) or not isinstance(
        should_recognize, bool
    ):
        raise RuntimeError(
            "weapon_recognition.display は is_visible と should_recognize の真偽値が必要です"
        )

    raw_slots = raw_weapon_recognition.get("slots")
    if not isinstance(raw_slots, dict):
        raise RuntimeError("weapon_recognition.slots が必要です")
    expected_slot_names = set(REPLAY_WEAPON_SLOT_NAMES)
    actual_slot_names = set(raw_slots)
    if actual_slot_names != expected_slot_names:
        missing = sorted(expected_slot_names - actual_slot_names)
        unexpected = sorted(actual_slot_names - expected_slot_names)
        raise RuntimeError(
            "weapon_recognition.slots のスロット名が不正です"
            f" missing={missing} unexpected={unexpected}"
        )

    slots: list[ReplayWeaponSlotObservation] = []
    for slot_name in REPLAY_WEAPON_SLOT_NAMES:
        raw_slot = raw_slots[slot_name]
        if not isinstance(raw_slot, dict):
            raise RuntimeError(
                f"weapon_recognition.slots.{slot_name} が不正です"
            )
        weapon = raw_slot.get("weapon")
        matched = raw_slot.get("matched")
        if not isinstance(weapon, str) or not weapon.strip():
            raise RuntimeError(
                f"weapon_recognition.slots.{slot_name}.weapon は空でない文字列が必要です"
            )
        if not isinstance(matched, bool):
            raise RuntimeError(
                f"weapon_recognition.slots.{slot_name}.matched は真偽値が必要です"
            )
        slots.append(
            ReplayWeaponSlotObservation(
                slot=slot_name,
                weapon=weapon.strip(),
                matched=matched,
            )
        )

    return ReplayWeaponRecognitionObservation(
        display=ReplayWeaponDisplayObservation(
            is_visible=is_visible,
            should_recognize=should_recognize,
        ),
        slots=tuple(slots),
    )


def resolve_replay_ocr_text(purpose: OCRPurpose) -> str | None:
    """現在の replay input から指定用途の OCR 観測を厳密に解決する。"""
    input_file = resolve_replay_input_file_path()
    if not input_file.exists():
        raise RuntimeError(
            "replay input が見つからないため OCR 観測を解決できません"
        )

    try:
        payload = json.loads(input_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("replay input の OCR 観測を読み込めません") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            "replay input は JSON オブジェクトである必要があります"
        )

    raw_observations = payload.get("observations")
    if not isinstance(raw_observations, dict):
        raise RuntimeError("replay input に observations が必要です")
    raw_ocr = raw_observations.get("ocr")
    if not isinstance(raw_ocr, dict):
        raise RuntimeError("observations.ocr が必要です")
    unknown_purposes = sorted(set(raw_ocr) - REPLAY_OCR_PURPOSE_NAMES)
    if unknown_purposes:
        raise RuntimeError(
            f"observations.ocr に未知の用途があります: {unknown_purposes}"
        )
    key = purpose.value
    if key not in raw_ocr:
        raise RuntimeError(f"observations.ocr.{key} が必要です")
    text = raw_ocr[key]
    if text is not None and not isinstance(text, str):
        raise RuntimeError(
            f"observations.ocr.{key} は文字列または null が必要です"
        )
    return text


def resolve_replay_battle_medal_observation() -> ReplayBattleMedalObservation:
    """現在の replay input から表彰認識観測を厳密に解決する。"""
    input_file = resolve_replay_input_file_path()
    if not input_file.exists():
        raise RuntimeError(
            "replay input が見つからないため表彰認識観測を解決できません"
        )

    try:
        payload = json.loads(input_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            "replay input の表彰認識観測を読み込めません"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            "replay input は JSON オブジェクトである必要があります"
        )

    raw_observations = payload.get("observations")
    if not isinstance(raw_observations, dict):
        raise RuntimeError("replay input に observations が必要です")
    raw_battle_medals = raw_observations.get("battle_medals")
    if not isinstance(raw_battle_medals, dict):
        raise RuntimeError("observations.battle_medals が必要です")
    expected_keys = {"gold", "silver"}
    actual_keys = set(raw_battle_medals)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(actual_keys - expected_keys)
        raise RuntimeError(
            "observations.battle_medals のキーが不正です"
            f" missing={missing} unexpected={unexpected}"
        )

    gold = raw_battle_medals["gold"]
    silver = raw_battle_medals["silver"]
    if (
        isinstance(gold, bool)
        or not isinstance(gold, int)
        or gold < 0
        or isinstance(silver, bool)
        or not isinstance(silver, int)
        or silver < 0
    ):
        raise RuntimeError(
            "observations.battle_medals.gold と silver は 0 以上の整数が必要です"
        )

    return ReplayBattleMedalObservation(gold=gold, silver=silver)


def is_wsl_runtime() -> bool:
    """現在の Linux 実行環境が WSL かを返す。"""
    if sys.platform != "linux":
        return False
    return bool(
        os.getenv("WSL_DISTRO_NAME")
        or os.getenv("WSL_INTEROP")
        or "microsoft" in platform.release().lower()
    )


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
        if is_wsl_runtime():
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


def require_configured_test_video() -> ResolvedTestVideo:
    """replay プロファイルに必須の入力動画を解決する。"""
    try:
        resolved = resolve_configured_test_video()
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("リプレイ入力を解決できません") from exc
    if resolved is None:
        raise RuntimeError(
            "SPLAT_REPLAY_RUNTIME_PROFILE=replay には有効な replay 入力が必要です"
        )
    return resolved

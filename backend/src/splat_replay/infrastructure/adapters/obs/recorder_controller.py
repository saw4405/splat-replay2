"""OBS Studio録画制御。

責務:
- 録画開始・停止・一時停止・再開
- 仮想カメラ制御
- 録画状態イベントの通知
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, AsyncIterator, Iterable, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Concatenate,
    Coroutine,
    Dict,
    Literal,
    ParamSpec,
    TypeVar,
    cast,
)

from obswsc.data import Event
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    AudioInputHealthCheckResult,
    AudioInputHealthStatus,
    OBSSettingsView,
    RecorderStatus,
    VideoRecorderPort,
)
from splat_replay.domain.exceptions import DeviceError
from splat_replay.infrastructure.adapters.obs.process_manager import (
    OBSProcessManager,
)
from splat_replay.infrastructure.adapters.obs.websocket_client import (
    InputVolumeMeterSample,
    OBSWebSocketClient,
)

StatusListener = Callable[[RecorderStatus], Awaitable[None]]
OperationParams = ParamSpec("OperationParams")
OperationResult = TypeVar("OperationResult")
DEFAULT_AUDIO_SAMPLE_SECONDS = 1.0
SILENCE_PEAK_MUL_THRESHOLD = 0.001
SILENCE_PEAK_DB_THRESHOLD = -60.0
_AudioInputResolutionStatus = Literal["input_not_found", "unknown"]


@dataclass(frozen=True)
class _OBSInput:
    name: str
    kind: str


# OBSイベント状態からRecorderStatusへのマッピング
STATE_TO_STATUS: Dict[str, RecorderStatus] = {
    "OBS_WEBSOCKET_OUTPUT_STARTED": "started",
    "OBS_WEBSOCKET_OUTPUT_PAUSED": "paused",
    "OBS_WEBSOCKET_OUTPUT_RESUMED": "resumed",
    "OBS_WEBSOCKET_OUTPUT_STOPPED": "stopped",
}

SHORT_AUDIO_MESSAGES = {
    "input_not_configured": "音声入力未設定",
    "input_not_found": "音声入力未検出",
    "input_inactive": "音声入力非アクティブ",
    "muted": "音声ミュート",
    "no_audio_tracks": "録音トラック未設定",
    "silent": "音量メーター未反応",
    "unknown": "音声確認失敗",
    "ok": "",
    "skipped": "",
}


def _audio_health_result(
    *,
    input_name: str,
    status: str,
    healthy: bool,
    details: str | None = None,
    peak_db: float | None = None,
) -> AudioInputHealthCheckResult:
    short_message = SHORT_AUDIO_MESSAGES.get(status, "音声確認失敗")
    if details is None:
        if healthy:
            details = f"OBS の入力「{input_name}」で音声入力を確認しました。"
        elif status == "silent":
            details = (
                f"OBS の入力「{input_name}」の音量メーターが振れていません。"
                "録画は継続しますが、動画に音声が入らない可能性があります。"
            )
        elif status == "muted":
            details = (
                f"OBS の入力「{input_name}」がミュートされています。"
                "録画は継続しますが、動画に音声が入らない可能性があります。"
            )
        elif status == "input_inactive":
            details = (
                f"OBS の入力「{input_name}」がアクティブではありません。"
                "録画は継続しますが、動画に音声が入らない可能性があります。"
            )
        elif status == "no_audio_tracks":
            details = (
                f"OBS の入力「{input_name}」が録音トラックに割り当てられていません。"
                "録画は継続しますが、動画に音声が入らない可能性があります。"
            )
        elif status == "input_not_configured":
            details = (
                "監視対象の OBS 音声入力名が設定されていません。"
                "録画は継続しますが、動画に音声が入らない可能性があります。"
            )
        else:
            details = (
                f"OBS の入力「{input_name}」の音声状態を確認できませんでした。"
                "録画は継続します。"
            )
    return AudioInputHealthCheckResult(
        input_name=input_name,
        status=cast(AudioInputHealthStatus, status),
        healthy=healthy,
        short_message=short_message,
        details=details,
        peak_db=peak_db,
    )


def _extract_peak_number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return None
    peaks: list[float] = []
    for item in value:
        peak = _extract_peak_number(item)
        if peak is not None:
            peaks.append(peak)
    return max(peaks) if peaks else None


def _contains_device_name(value: object, device_name: str) -> bool:
    if isinstance(value, str):
        return value == device_name or value.startswith(f"{device_name}:")
    if isinstance(value, Mapping):
        return any(
            _contains_device_name(item, device_name) for item in value.values()
        )
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return any(_contains_device_name(item, device_name) for item in value)
    return False


def _guard_obs_operation(
    method: Callable[
        Concatenate[OBSRecorderController, OperationParams],
        Coroutine[Any, Any, OperationResult],
    ],
) -> Callable[
    Concatenate[OBSRecorderController, OperationParams],
    Coroutine[Any, Any, OperationResult],
]:
    @wraps(method)
    async def wrapper(
        self: OBSRecorderController,
        *args: OperationParams.args,
        **kwargs: OperationParams.kwargs,
    ) -> OperationResult:
        async with self._operation_guard():
            return await method(self, *args, **kwargs)

    return wrapper


class OBSRecorderController(VideoRecorderPort):
    """OBS Studio録画制御。

    責務:
    - VideoRecorderPortの実装
    - 録画操作（開始・停止・一時停止・再開）
    - 仮想カメラ制御
    - 録画状態イベントの通知

    プロセス管理とWebSocket通信は委譲。
    """

    def __init__(self, settings: OBSSettingsView, logger: BoundLogger) -> None:
        """初期化。

        Args:
            settings: OBS設定
            logger: ロガー
        """
        self._logger = logger
        self._status_listeners: list[StatusListener] = []
        self._audio_meter_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()
        self._operation_owner: asyncio.Task[Any] | None = None
        self._operation_depth = 0

        # プロセス管理とWebSocket通信を委譲
        self._process_manager = OBSProcessManager(
            settings.executable_path, logger
        )
        self._ws_client = OBSWebSocketClient(
            host=settings.websocket_host,
            port=settings.websocket_port,
            password=settings.websocket_password.get_secret_value(),
            logger=logger,
            on_reconnect=self._handle_ws_reconnect,
        )

        # 録画状態イベントを登録
        self._ws_client.register_event_callback(
            "RecordStateChanged", self._on_record_state_changed
        )

    @asynccontextmanager
    async def _operation_guard(self) -> AsyncIterator[None]:
        task = asyncio.current_task()
        if task is not None and self._operation_owner is task:
            self._operation_depth += 1
            try:
                yield
            finally:
                self._operation_depth -= 1
            return

        async with self._operation_lock:
            self._operation_owner = task
            self._operation_depth = 1
            try:
                yield
            finally:
                self._operation_depth = 0
                self._operation_owner = None

    async def _handle_ws_reconnect(self) -> None:
        """OBS再接続時に初期セットアップを再実行する。"""
        self._logger.info("OBS再接続を検知しました。再セットアップします")
        await self.setup()

    def update_settings(self, settings: OBSSettingsView) -> None:
        """設定を更新。

        Args:
            settings: 新しい設定
        """
        self._process_manager = OBSProcessManager(
            settings.executable_path, self._logger
        )
        self._ws_client.update_settings(
            host=settings.websocket_host,
            port=settings.websocket_port,
            password=settings.websocket_password.get_secret_value(),
        )
        self._logger.info("OBS設定更新完了")

    async def is_running(self) -> bool:
        """OBSが実行中かどうかを確認。

        Returns:
            実行中ならTrue
        """
        return await self._process_manager.is_running()

    @_guard_obs_operation
    async def launch(self) -> None:
        """OBSを起動。

        Raises:
            DeviceError: 起動失敗時
        """
        await self._process_manager.launch()

    @_guard_obs_operation
    async def teardown(self) -> None:
        """OBSを終了。

        アプリが終了させる OBS の録画と仮想カメラを停止してから終了する。
        アプリ起動前から存在する OBS の出力には触れない。
        """
        self._logger.info("OBS 終了要求")

        # 外部起動または終了時に保持する OBS の出力を巻き込まない。
        if self._ws_client.is_connected:
            if self._process_manager.will_close_on_teardown:
                self._logger.info("OBS リソース解放開始")

                active, _ = await self._get_record_status()
                if active:
                    self._logger.info("録画停止中")
                    await self.stop()

                if await self.is_virtual_camera_active():
                    self._logger.info("仮想カメラ停止中")
                    await self.stop_virtual_camera()

            await self._ws_client.disconnect()

        # プロセス終了
        await self._process_manager.teardown()
        await self._ws_client.drain_meter_cleanup_tasks()
        self._logger.info("OBS 終了完了")

    @_guard_obs_operation
    async def check_audio_input_health(
        self,
        input_name: str,
        *,
        sample_duration_seconds: float = DEFAULT_AUDIO_SAMPLE_SECONDS,
    ) -> AudioInputHealthCheckResult:
        """Check whether the named OBS audio input appears usable."""
        target_name = input_name.strip()
        try:
            inspection, resolved_name, _ = await self._inspect_audio_input(
                target_name
            )
            if inspection is not None:
                return inspection
            assert resolved_name is not None

            sample = await self._sample_audio_meter(
                resolved_name,
                sample_duration_seconds=sample_duration_seconds,
            )
            return self._audio_health_from_meter_sample(resolved_name, sample)
        except Exception as exc:
            self._logger.warning(
                "OBS 音声入力ヘルスチェックに失敗しました",
                input_name=target_name,
                error=str(exc),
            )
            return _audio_health_result(
                input_name=target_name,
                status="unknown",
                healthy=False,
                details=(
                    f"OBS の入力「{target_name}」の音声状態を確認できませんでした。"
                    f"エラー: {exc}。録画は継続します。"
                ),
            )

    async def observe_audio_input_health(
        self, input_name: str
    ) -> AsyncGenerator[AudioInputHealthCheckResult, None]:
        """OBS の音声状態を有界な1秒窓で連続観測する。"""
        target_name = input_name.strip()
        while True:
            meter_windows: (
                AsyncGenerator[dict[str, InputVolumeMeterSample], None] | None
            ) = None
            try:
                (
                    inspection,
                    resolved_name,
                    source_key,
                ) = await self._inspect_audio_input(target_name)
                if inspection is not None:
                    yield inspection
                    await asyncio.sleep(DEFAULT_AUDIO_SAMPLE_SECONDS)
                    continue

                meter_windows = (
                    self._ws_client.iter_input_volume_meter_windows(
                        window_seconds=DEFAULT_AUDIO_SAMPLE_SECONDS
                    )
                )
                async for window in meter_windows:
                    (
                        current_inspection,
                        current_name,
                        current_key,
                    ) = await self._inspect_audio_input(target_name)
                    if current_inspection is not None:
                        result = current_inspection
                        source_key = None
                    elif current_key != source_key:
                        result = _audio_health_result(
                            input_name=target_name,
                            status="unknown",
                            healthy=False,
                            details=(
                                f"OBS の入力「{target_name}」の割り当てが変わったため、"
                                "次の音量メーター窓で再確認します。"
                            ),
                        )
                        source_key = current_key
                    else:
                        assert current_name is not None
                        result = self._audio_health_from_meter_sample(
                            current_name, window.get(current_name)
                        )
                        source_key = current_key
                    yield result
            except asyncio.CancelledError:
                raise
            except Exception:
                yield _audio_health_result(
                    input_name=target_name,
                    status="unknown",
                    healthy=False,
                    details=(
                        f"OBS の入力「{target_name}」の音声状態を確認できませんでした。"
                        "録画は継続します。"
                    ),
                )
                await asyncio.sleep(DEFAULT_AUDIO_SAMPLE_SECONDS)
            finally:
                if meter_windows is not None:
                    with suppress(Exception):
                        await meter_windows.aclose()

    async def _inspect_audio_input(
        self, target_name: str
    ) -> tuple[AudioInputHealthCheckResult | None, str | None, str | None]:
        if not target_name:
            return (
                _audio_health_result(
                    input_name=target_name,
                    status="input_not_configured",
                    healthy=False,
                ),
                None,
                None,
            )

        await self._connect_if_running()
        available_inputs = await self._list_inputs()
        (
            resolved_name,
            unresolved_status,
        ) = await self._resolve_audio_input_name(target_name, available_inputs)
        if resolved_name is None:
            status = unresolved_status or "input_not_found"
            if status == "unknown":
                details = (
                    f"OBS の入力「{target_name}」に対応する音声入力を"
                    "一意に確認できませんでした。録画は継続します。"
                )
            else:
                available_names = ", ".join(
                    obs_input.name for obs_input in available_inputs
                )
                details = (
                    f"OBS の入力「{target_name}」が見つかりません。"
                    f"利用可能な入力: {available_names or 'なし'}。"
                    "録画は継続しますが、音声が入らない可能性があります。"
                )
            return (
                _audio_health_result(
                    input_name=target_name,
                    status=status,
                    healthy=False,
                    details=details,
                ),
                None,
                None,
            )

        if await self._is_input_muted(resolved_name):
            return (
                _audio_health_result(
                    input_name=resolved_name, status="muted", healthy=False
                ),
                resolved_name,
                None,
            )
        tracks = await self._get_input_audio_tracks(resolved_name)
        if tracks is not None and not any(tracks):
            return (
                _audio_health_result(
                    input_name=resolved_name,
                    status="no_audio_tracks",
                    healthy=False,
                ),
                resolved_name,
                None,
            )
        if await self._is_source_active(resolved_name) is False:
            return (
                _audio_health_result(
                    input_name=resolved_name,
                    status="input_inactive",
                    healthy=False,
                ),
                resolved_name,
                None,
            )

        settings = await self._get_input_settings(resolved_name)
        return (
            None,
            resolved_name,
            json.dumps(dict(settings), sort_keys=True, default=str),
        )

    async def _connect_if_running(self) -> None:
        """OBS が起動済みならWebSocket接続を行う。"""
        if not await self._process_manager.is_running():
            raise DeviceError("OBS が起動していません", "OBS_NOT_RUNNING")
        if not self._ws_client.is_connected:
            await self._ws_client.connect()

    @staticmethod
    def _audio_health_from_meter_sample(
        input_name: str,
        sample: (InputVolumeMeterSample | tuple[float, float | None] | None),
    ) -> AudioInputHealthCheckResult:
        if sample is None:
            return _audio_health_result(
                input_name=input_name,
                status="unknown",
                healthy=False,
                details=(
                    "OBS WebSocket から音量メーターイベントを取得できなかったため、"
                    f"入力「{input_name}」の入力レベルを確認できませんでした。"
                    "録画は継続しますが、動画に音声が入らない可能性があります。"
                ),
            )
        if isinstance(sample, InputVolumeMeterSample):
            raw_peak_mul = sample.peak_mul
            peak_db = sample.peak_db
        else:
            raw_peak_mul, peak_db = sample
        peak_mul = float(raw_peak_mul) if raw_peak_mul is not None else 0.0
        if peak_mul <= SILENCE_PEAK_MUL_THRESHOLD and (
            peak_db is None or peak_db <= SILENCE_PEAK_DB_THRESHOLD
        ):
            return _audio_health_result(
                input_name=input_name,
                status="silent",
                healthy=False,
                peak_db=peak_db,
            )
        return _audio_health_result(
            input_name=input_name,
            status="ok",
            healthy=True,
            peak_db=peak_db,
        )

    async def _resolve_audio_input_name(
        self, target_name: str, available_inputs: list[_OBSInput]
    ) -> tuple[str | None, _AudioInputResolutionStatus | None]:
        coreaudio_inputs = [
            obs_input
            for obs_input in available_inputs
            if obs_input.kind == "coreaudio_input_capture"
        ]
        if coreaudio_inputs:
            matches: list[str] = []
            for obs_input in coreaudio_inputs:
                settings = await self._get_input_settings(obs_input.name)
                device_id = settings.get("device_id")
                if device_id == "default":
                    continue
                if not isinstance(device_id, str) or not device_id:
                    return None, "unknown"

                response = await self._ws_client.request(
                    "GetInputPropertiesListPropertyItems",
                    idempotent=True,
                    request_data={
                        "inputName": obs_input.name,
                        "propertyName": "device_id",
                    },
                )
                property_items = (response.res_data or {}).get("propertyItems")
                if not isinstance(property_items, list):
                    return None, "unknown"

                named_items: list[dict[str, object]] = []
                for item in property_items:
                    if not isinstance(item, dict):
                        return None, "unknown"
                    if (
                        item.get("itemEnabled") is True
                        and item.get("itemName") == target_name
                    ):
                        named_items.append(item)
                if len(named_items) > 1:
                    return None, "unknown"
                if (
                    len(named_items) == 1
                    and named_items[0].get("itemValue") == device_id
                ):
                    matches.append(obs_input.name)

            if len(matches) == 1:
                return matches[0], None
            return None, "unknown"

        non_macos_inputs = [
            obs_input
            for obs_input in available_inputs
            if obs_input.kind != "macos-avcapture"
        ]
        exact_matches = [
            obs_input.name
            for obs_input in non_macos_inputs
            if obs_input.name == target_name
        ]
        if len(exact_matches) == 1:
            return exact_matches[0], None
        if len(exact_matches) > 1:
            return None, "unknown"

        device_matches: list[str] = []
        for obs_input in non_macos_inputs:
            if await self._input_settings_contain_device_name(
                obs_input.name, target_name
            ):
                device_matches.append(obs_input.name)
        if len(device_matches) == 1:
            return device_matches[0], None
        if len(device_matches) > 1:
            return None, "unknown"

        macos_video_inputs = [
            obs_input
            for obs_input in available_inputs
            if obs_input.kind == "macos-avcapture"
        ]
        if macos_video_inputs:
            return None, "unknown"

        if any(
            obs_input.name == target_name for obs_input in available_inputs
        ):
            return None, "unknown"
        return None, "input_not_found"

    async def _input_settings_contain_device_name(
        self, input_name: str, device_name: str
    ) -> bool:
        settings = await self._get_input_settings(input_name)
        return _contains_device_name(settings, device_name)

    async def _get_input_settings(
        self, input_name: str
    ) -> Mapping[str, object]:
        response = await self._ws_client.request(
            "GetInputSettings",
            idempotent=True,
            request_data={"inputName": input_name},
        )
        input_settings = (response.res_data or {}).get("inputSettings")
        if not isinstance(input_settings, Mapping):
            raise DeviceError(
                f"OBS 入力「{input_name}」の設定を確認できません",
                "OBS_INPUT_SETTINGS_INVALID",
            )
        return cast(Mapping[str, object], input_settings)

    async def _list_inputs(self) -> list[_OBSInput]:
        response = await self._ws_client.request(
            "GetInputList", idempotent=True
        )
        response_data = response.res_data
        if not isinstance(response_data, Mapping):
            raise DeviceError(
                "OBS 入力一覧を確認できません",
                "OBS_INPUT_LIST_INVALID",
            )
        inputs = response_data.get("inputs")
        if not isinstance(inputs, list):
            raise DeviceError(
                "OBS 入力一覧を確認できません",
                "OBS_INPUT_LIST_INVALID",
            )
        result: list[_OBSInput] = []
        for item in inputs:
            if not isinstance(item, dict):
                raise DeviceError(
                    "OBS 入力一覧の項目を確認できません",
                    "OBS_INPUT_LIST_INVALID",
                )
            name = item.get("inputName")
            kind = item.get("inputKind")
            if not isinstance(name, str) or not isinstance(kind, str):
                raise DeviceError(
                    "OBS 入力一覧の種類を確認できません",
                    "OBS_INPUT_LIST_INVALID",
                )
            result.append(_OBSInput(name=name, kind=kind))
        return result

    async def _is_input_muted(self, input_name: str) -> bool:
        response = await self._ws_client.request(
            "GetInputMute",
            idempotent=True,
            request_data={"inputName": input_name},
        )
        return bool((response.res_data or {}).get("inputMuted", False))

    async def _get_input_audio_tracks(
        self, input_name: str
    ) -> list[bool] | None:
        try:
            response = await self._ws_client.request(
                "GetInputAudioTracks",
                idempotent=True,
                request_data={"inputName": input_name},
            )
        except DeviceError as exc:
            self._logger.debug(
                "OBS 録音トラック状態を取得できませんでした",
                input_name=input_name,
                error=str(exc),
            )
            return None
        raw_tracks = (response.res_data or {}).get("inputAudioTracks")
        if not isinstance(raw_tracks, dict):
            return None
        return [bool(value) for value in raw_tracks.values()]

    async def _is_source_active(self, input_name: str) -> bool | None:
        try:
            response = await self._ws_client.request(
                "GetSourceActive",
                idempotent=True,
                request_data={"sourceName": input_name},
            )
        except DeviceError as exc:
            self._logger.debug(
                "OBS ソースのアクティブ状態を取得できませんでした",
                input_name=input_name,
                error=str(exc),
            )
            return None
        raw = (response.res_data or {}).get("videoActive")
        return bool(raw) if raw is not None else None

    async def _sample_audio_meter(
        self, input_name: str, *, sample_duration_seconds: float
    ) -> tuple[float, float | None] | None:
        async with self._audio_meter_lock:
            peaks_mul: list[float] = []
            peaks_db: list[float] = []
            events = await self._ws_client.collect_input_volume_meter_events(
                input_name,
                sample_duration_seconds=sample_duration_seconds,
            )
            event_count = 0
            numeric_mul_samples = 0
            numeric_db_samples = 0
            for item in events:
                peak_mul = _extract_peak_number(item.get("inputLevelsMul"))
                peak_db = _extract_peak_number(item.get("inputLevelsDb"))
                item_event_count = item.get("_eventCount")
                event_count += (
                    item_event_count
                    if isinstance(item_event_count, int)
                    else 1
                )
                if peak_mul is not None:
                    peaks_mul.append(peak_mul)
                item_mul_count = item.get("_numericMulSamples")
                numeric_mul_samples += (
                    item_mul_count
                    if isinstance(item_mul_count, int)
                    else int(peak_mul is not None)
                )
                if peak_db is not None:
                    peaks_db.append(peak_db)
                item_db_count = item.get("_numericDbSamples")
                numeric_db_samples += (
                    item_db_count
                    if isinstance(item_db_count, int)
                    else int(peak_db is not None)
                )

            peak_mul_value = max(peaks_mul) if peaks_mul else None
            peak_db_value = max(peaks_db) if peaks_db else None
            self._logger.info(
                "OBS 音声メーター計測結果",
                input_name=input_name,
                sample_duration_seconds=sample_duration_seconds,
                event_count=event_count,
                numeric_mul_samples=numeric_mul_samples,
                numeric_db_samples=numeric_db_samples,
                peak_mul=peak_mul_value,
                peak_db=peak_db_value,
            )

            if not events:
                return None
            return (
                peak_mul_value if peak_mul_value is not None else 0.0,
                peak_db_value,
            )

    @_guard_obs_operation
    async def connect(self) -> None:
        """WebSocketに接続。

        Raises:
            DeviceError: OBSが起動していない、または接続失敗時
        """
        await self._connect_if_running()

    @_guard_obs_operation
    async def setup(self) -> None:
        """OBSのセットアップ。

        起動・接続・仮想カメラ開始を一括実行。
        """
        self._logger.info("OBS セットアップ開始")

        if not await self._process_manager.is_running():
            await self._process_manager.launch()

        if not self._ws_client.is_connected:
            await self._ws_client.connect()

        await self.start_virtual_camera()
        self._logger.info("OBS セットアップ完了")

    # ------------------------------------------------------------------
    # 仮想カメラ制御
    # ------------------------------------------------------------------
    @_guard_obs_operation
    async def is_virtual_camera_active(self) -> bool:
        """仮想カメラが有効かどうかを確認。

        Returns:
            有効ならTrue
        """
        active = await self._ws_client.get_data(
            "GetVirtualCamStatus", "outputActive"
        )
        return bool(active) if active is not None else False

    @_guard_obs_operation
    async def start_virtual_camera(self) -> None:
        """仮想カメラを開始。"""
        self._logger.info("仮想カメラ開始要求")
        if await self.is_virtual_camera_active():
            self._logger.info("仮想カメラは既に開始済み")
            return
        await self._ws_client.request("StartVirtualCam")
        self._logger.info("仮想カメラ開始完了")

    @_guard_obs_operation
    async def stop_virtual_camera(self) -> None:
        """仮想カメラを停止。"""
        self._logger.info("仮想カメラ停止要求")
        if not await self.is_virtual_camera_active():
            self._logger.info("仮想カメラは既に停止済み")
            return
        await self._ws_client.request("StopVirtualCam")
        # 要求の受理と出力停止は別。停止完了前に閉じると終了確認が出る。
        try:
            async with asyncio.timeout(5):
                while (
                    await self._ws_client.get_data(
                        "GetVirtualCamStatus", "outputActive"
                    )
                    is not False
                ):
                    await asyncio.sleep(0.1)
        except TimeoutError as exc:
            raise DeviceError(
                "仮想カメラの停止を確認できませんでした",
                "OBS_VIRTUAL_CAMERA_STOP_TIMEOUT",
                cause=exc,
            ) from exc
        self._logger.info("仮想カメラ停止完了")

    # ------------------------------------------------------------------
    # 録画制御
    # ------------------------------------------------------------------
    @_guard_obs_operation
    async def _get_record_status(self) -> tuple[bool, bool]:
        """録画状態を取得。

        Returns:
            (active, paused) のタプル
        """
        await self.connect()
        response = await self._ws_client.request(
            "GetRecordStatus", idempotent=True
        )
        if response.res_data is None:
            return False, False
        active = bool(response.res_data.get("outputActive", False))
        paused = bool(response.res_data.get("outputPaused", False))
        return active, paused

    @_guard_obs_operation
    async def start(self) -> None:
        """録画を開始。"""
        self._logger.info("録画開始要求")
        active, _ = await self._get_record_status()
        if active:
            self._logger.warning("録画は既に開始済みです")
            return
        await self._ws_client.request("StartRecord")
        self._logger.info("録画開始完了")

    @_guard_obs_operation
    async def stop(self) -> Path | None:
        """録画を停止。

        Returns:
            録画ファイルのパス（取得失敗時はNone）
        """
        self._logger.info("録画停止要求")
        active, _ = await self._get_record_status()
        if not active:
            self._logger.warning("録画は開始されていません")
            return None

        response = await self._ws_client.request("StopRecord")
        if response.res_data is None:
            self._logger.warning("録画停止レスポンスが空です")
            return None

        output = response.res_data.get("outputPath")
        if not isinstance(output, str) or not output:
            self._logger.warning("録画ファイルの取得に失敗しました")
            return None

        output_path = Path(output)
        self._logger.info("録画停止完了", output_path=str(output_path))
        return output_path

    @_guard_obs_operation
    async def pause(self) -> None:
        """録画を一時停止。"""
        self._logger.info("録画一時停止要求")
        active, paused = await self._get_record_status()
        if not active:
            self._logger.warning("録画は開始されていません")
            return
        if paused:
            self._logger.warning("録画は既に一時停止中です")
            return
        await self._ws_client.request("PauseRecord")
        self._logger.info("録画一時停止完了")

    @_guard_obs_operation
    async def resume(self) -> None:
        """録画を再開。"""
        self._logger.info("録画再開要求")
        _, paused = await self._get_record_status()
        if not paused:
            self._logger.warning("録画は一時停止されていません")
            return
        await self._ws_client.request("ResumeRecord")
        self._logger.info("録画再開完了")

    # ------------------------------------------------------------------
    # 状態通知
    # ------------------------------------------------------------------
    def add_status_listener(self, listener: StatusListener) -> None:
        """状態リスナーを追加。

        Args:
            listener: リスナー関数
        """
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: StatusListener) -> None:
        """状態リスナーを削除。

        Args:
            listener: リスナー関数
        """
        if listener in self._status_listeners:
            self._status_listeners.remove(listener)

    async def _on_record_state_changed(self, event: Event) -> None:
        """録画状態変更イベントを処理。

        Args:
            event: OBSイベント
        """
        if event.event_type != "RecordStateChanged":
            return

        state_obj = event.event_data.get("outputState")
        if not isinstance(state_obj, str):
            self._logger.warning("不明な録画状態", state=state_obj)
            return

        status = STATE_TO_STATUS.get(state_obj)
        if status is None:
            self._logger.debug("未対応の録画状態", state=state_obj)
            return

        self._logger.info("録画状態変更", status=status)
        await self._notify_status(status)

    async def _notify_status(self, status: RecorderStatus) -> None:
        """状態リスナーに通知。

        Args:
            status: 録画状態
        """
        for listener in list(self._status_listeners):
            try:
                await listener(status)
            except Exception as exc:  # pragma: no cover - logging path
                self._logger.error("ステータス通知でエラー", error=str(exc))

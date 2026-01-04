"""OBS Studio録画制御。

責務:
- 録画開始・停止・一時停止・再開
- 仮想カメラ制御
- 録画状態イベントの通知
"""

from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable, Dict

from obswsc.data import Event
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    OBSSettingsView,
    RecorderStatus,
    VideoRecorderPort,
)
from splat_replay.domain.exceptions import DeviceError
from splat_replay.infrastructure.adapters.obs.process_manager import (
    OBSProcessManager,
)
from splat_replay.infrastructure.adapters.obs.websocket_client import (
    OBSWebSocketClient,
)

StatusListener = Callable[[RecorderStatus], Awaitable[None]]

# OBSイベント状態からRecorderStatusへのマッピング
STATE_TO_STATUS: Dict[str, RecorderStatus] = {
    "OBS_WEBSOCKET_OUTPUT_STARTED": "started",
    "OBS_WEBSOCKET_OUTPUT_PAUSED": "paused",
    "OBS_WEBSOCKET_OUTPUT_RESUMED": "resumed",
    "OBS_WEBSOCKET_OUTPUT_STOPPED": "stopped",
}


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

        # プロセス管理とWebSocket通信を委譲
        self._process_manager = OBSProcessManager(
            settings.executable_path, logger
        )
        self._ws_client = OBSWebSocketClient(
            host=settings.websocket_host,
            port=settings.websocket_port,
            password=settings.websocket_password.get_secret_value(),
            logger=logger,
        )

        # 録画状態イベントを登録
        self._ws_client.register_event_callback(
            "RecordStateChanged", self._on_record_state_changed
        )

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

    async def launch(self) -> None:
        """OBSを起動。

        Raises:
            DeviceError: 起動失敗時
        """
        await self._process_manager.launch()

    async def teardown(self) -> None:
        """OBSを終了。

        録画中の場合は停止し、仮想カメラも停止してからプロセスを終了。
        """
        self._logger.info("OBS 終了要求")

        # WebSocket接続がある場合は録画と仮想カメラを停止
        if self._ws_client.is_connected:
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
        self._logger.info("OBS 終了完了")

    async def connect(self) -> None:
        """WebSocketに接続。

        Raises:
            DeviceError: OBSが起動していない、または接続失敗時
        """
        if not await self._process_manager.is_running():
            raise DeviceError("OBS が起動していません", "OBS_NOT_RUNNING")

        await self._ws_client.connect()

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
    async def is_virtual_camera_active(self) -> bool:
        """仮想カメラが有効かどうかを確認。

        Returns:
            有効ならTrue
        """
        active = await self._ws_client.get_data(
            "GetVirtualCamStatus", "outputActive"
        )
        return bool(active) if active is not None else False

    async def start_virtual_camera(self) -> None:
        """仮想カメラを開始。"""
        self._logger.info("仮想カメラ開始要求")
        if await self.is_virtual_camera_active():
            self._logger.info("仮想カメラは既に開始済み")
            return
        await self._ws_client.request("StartVirtualCam")
        self._logger.info("仮想カメラ開始完了")

    async def stop_virtual_camera(self) -> None:
        """仮想カメラを停止。"""
        self._logger.info("仮想カメラ停止要求")
        if not await self.is_virtual_camera_active():
            self._logger.info("仮想カメラは既に停止済み")
            return
        await self._ws_client.request("StopVirtualCam")
        self._logger.info("仮想カメラ停止完了")

    # ------------------------------------------------------------------
    # 録画制御
    # ------------------------------------------------------------------
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

    async def start(self) -> None:
        """録画を開始。"""
        self._logger.info("録画開始要求")
        active, _ = await self._get_record_status()
        if active:
            self._logger.warning("録画は既に開始済みです")
            return
        await self._ws_client.request("StartRecord")
        self._logger.info("録画開始完了")

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

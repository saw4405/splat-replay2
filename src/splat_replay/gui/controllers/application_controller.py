"""Slim GUI controller using new runtime adapter (fully async push model)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Tuple, cast

import ttkbootstrap as ttk

from splat_replay.application.interfaces import (
    VideoAssetRepository,
    VideoEditorPort,
)
from splat_replay.application.services import (
    AutoEditor,
    AutoRecorder,
    AutoUploader,
    DeviceChecker,
    ProgressReporter,
)
from splat_replay.domain.models import Frame, VideoAsset
from splat_replay.domain.services import RecordState, StateMachine
from splat_replay.gui.runtime_adapter import GuiRuntimeAdapter
from splat_replay.infrastructure import GuiRuntimePortAdapter
from splat_replay.infrastructure.runtime.events import Event
from splat_replay.infrastructure.runtime.frames import FramePacket
from splat_replay.infrastructure.runtime.runtime import AppRuntime
from splat_replay.shared.config import BehaviorSettings
from splat_replay.shared.di import configure_container, resolve
from splat_replay.shared.event_types import EventTypes
from splat_replay.shared.logger import get_logger


class GUIApplicationController:
    def __init__(self) -> None:
        self.logger = get_logger()
        self.container = configure_container()
        self.runtime = resolve(self.container, AppRuntime)
        self._gui_ports = resolve(self.container, GuiRuntimePortAdapter)
        self.adapter: GuiRuntimeAdapter | None = None

        # core components
        self.behavior_settings = resolve(self.container, BehaviorSettings)
        self._device_checker = resolve(self.container, DeviceChecker)
        self._auto_recorder = resolve(self.container, AutoRecorder)
        self._auto_editor = resolve(self.container, AutoEditor)
        self._auto_uploader = resolve(self.container, AutoUploader)
        self._progress = resolve(self.container, ProgressReporter)
        self._asset_repo = resolve(self.container, VideoAssetRepository)
        self._video_editor = resolve(self.container, VideoEditorPort)
        self._state_machine = resolve(self.container, StateMachine)
        # listeners
        self._record_state_listeners: List[Callable[[RecordState], None]] = []
        self._operation_msg_listeners: List[Callable[[str], None]] = []
        self._power_off_listeners: List[Callable[[], None]] = []
        self._progress_listeners: List[Callable[[dict], None]] = []
        # video asset change listeners
        self._asset_event_listeners: List[Callable[[str, dict], None]] = []
        self._asset_events = {
            EventTypes.ASSET_RECORDED_SAVED,
            EventTypes.ASSET_RECORDED_METADATA_UPDATED,
            EventTypes.ASSET_RECORDED_DELETED,
            EventTypes.ASSET_EDITED_SAVED,
            EventTypes.ASSET_EDITED_DELETED,
        }

    def attach_gui_root(self, root: ttk.Window) -> None:  # type: ignore[no-untyped-def]
        # adapter now uses abstract ports (dispatcher/subscriber/frame_source)
        self.adapter = GuiRuntimeAdapter(
            dispatcher=self._gui_ports,
            subscriber=self._gui_ports,
            frame_source=self._gui_ports,
            tk_root=root,
        )
        self.adapter.on_event(self._on_event)

    def _on_event(self, ev: Event) -> None:
        if ev.type == EventTypes.RECORDER_STATE:
            state = self._state_machine.state
            for cb in list(self._record_state_listeners):
                try:
                    cb(state)
                except Exception:
                    pass
        elif ev.type == EventTypes.RECORDER_OPERATION:
            msg = ev.payload.get("message", "")
            for cb in list(self._operation_msg_listeners):
                try:
                    cb(msg)
                except Exception:
                    pass
        elif ev.type == EventTypes.POWER_OFF_DETECTED:
            for cb in list(self._power_off_listeners):
                try:
                    cb()
                except Exception:
                    pass
        elif ev.type.startswith(EventTypes.PROGRESS_PREFIX):
            # progress.<kind>
            payload = dict(ev.payload)
            payload["kind"] = ev.type[len(EventTypes.PROGRESS_PREFIX) :]
            for cb in list(self._progress_listeners):
                try:
                    cb(payload)
                except Exception:
                    pass
        elif ev.type in self._asset_events:
            # video asset repository change events -> notify listeners
            for cb in list(self._asset_event_listeners):
                try:
                    cb(ev.type, dict(ev.payload))
                except Exception:
                    pass

    def start_auto_recorder(self) -> None:
        async def run():
            try:
                # キャプチャデバイス接続待機
                try:
                    connected = (
                        await self._device_checker.wait_for_device_connection()
                    )
                except Exception as e:  # 保険で例外を握り潰しログ
                    self.logger.error(
                        "デバイス接続待機処理でエラー", error=str(e)
                    )
                    connected = False
                if not connected:
                    # 接続できない場合は自動録画開始をスキップ（GUI 側で手動リトライ前提）
                    self.logger.error(
                        "キャプチャデバイス未接続のため自動録画を開始しません"
                    )
                    return
                await self._auto_recorder.execute()
            except Exception as e:
                self.logger.error("AutoRecorder 実行エラー", error=str(e))

        if self.runtime.loop:
            self.runtime.loop.create_task(run())

    def _stop_auto_recorder(self) -> None:
        self._auto_recorder.force_stop_loop()

    # Frame delivery (GUI 用ラッパ): Widget からは Adapter を意識せず購読できる
    def on_preview_frame(self, handler: Callable[["Frame"], None]) -> bool:
        """
        プレビュー用のフレームハンドラを登録。

        GUI スレッドで呼び出される。Adapter 未接続時は False を返す。
        """
        adp = self.adapter
        if adp is None:
            return False

        # FramePacket -> Frame に変換して渡す
        def _wrap(pkt: FramePacket) -> None:
            try:
                handler(pkt.frame)
            except Exception:
                pass

        adp.on_frame(_wrap)
        return True

    def start_auto_editor_and_uploader(self) -> None:
        """自動編集→アップロードを順次非同期で実行する。GUI スレッドをブロックしない。"""

        async def run():
            try:
                await self._auto_editor.execute()
            except Exception as e:
                self.logger.error("AutoEditor 実行エラー", error=str(e))
            try:
                await self._auto_uploader.execute()
            except Exception as e:
                self.logger.error("AutoUploader 実行エラー", error=str(e))

        if self.runtime.loop:
            self.runtime.loop.create_task(run())

    def cancel_auto_editor_and_uploader(self) -> None:
        """自動編集/自動アップロード処理のキャンセルを要求する。"""
        try:
            self._auto_editor.request_cancel()
        except Exception:
            pass
        try:
            self._auto_uploader.request_cancel()
        except Exception:
            pass

    # Listener registration
    def add_record_state_changed_listener(
        self, cb: Callable[[RecordState], None]
    ) -> None:
        self._record_state_listeners.append(cb)

    def add_auto_recorder_operation_state_listener(
        self, cb: Callable[[str], None]
    ) -> None:
        self._operation_msg_listeners.append(cb)

    def add_detected_power_off_listener(self, cb: Callable[[], None]) -> None:
        self._power_off_listeners.append(cb)

    # Progress
    def add_progress_listener(self, cb: Callable[[dict], None]) -> None:
        self._progress_listeners.append(cb)

    def remove_progress_listener(self, cb: Callable[[dict], None]) -> None:
        if cb in self._progress_listeners:
            self._progress_listeners.remove(cb)

    # Asset change
    def add_asset_event_listener(
        self, cb: Callable[[str, dict], None]
    ) -> None:
        self._asset_event_listeners.append(cb)

    def remove_asset_event_listener(
        self, cb: Callable[[str, dict], None]
    ) -> None:
        if cb in self._asset_event_listeners:
            self._asset_event_listeners.remove(cb)

    def get_current_record_state(self) -> RecordState:
        return self._state_machine.state

    # Commands
    def start_manual_recording(self, cb: Callable[[bool], None]) -> None:
        fut = self._gui_ports.submit("recorder.start")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(lambda: cb(f.result().ok))
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().ok))

    def stop_manual_recording(self, cb: Callable[[bool], None]) -> None:
        fut = self._gui_ports.submit("recorder.stop")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(lambda: cb(f.result().ok))
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().ok))

    def pause_manual_recording(self, cb: Callable[[bool], None]) -> None:
        fut = self._gui_ports.submit("recorder.pause")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(lambda: cb(f.result().ok))
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().ok))

    def resume_manual_recording(self, cb: Callable[[bool], None]) -> None:
        fut = self._gui_ports.submit("recorder.resume")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(lambda: cb(f.result().ok))
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().ok))

    # Asset / metadata (synchronous simplified)
    def get_video_list(self, cb: Callable[[List[VideoAsset]], None]) -> None:
        fut = self._gui_ports.submit("asset.list")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(
                    lambda: cb((f.result().value or []))
                )
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().value or []))

    def get_video_assets_with_length(
        self, cb: Callable[[List[Tuple[VideoAsset, float | None]]], None]
    ) -> None:
        fut = self._gui_ports.submit("asset.list_with_length")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(
                    lambda: cb((f.result().value or []))
                )
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().value or []))

    def get_edited_assets_with_length(
        self,
        cb: Callable[
            [List[Tuple[Path, float | None, dict[str, str] | None]]], None
        ],
    ) -> None:
        fut = self._gui_ports.submit("asset.list_edited_with_length")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(
                    lambda: cb((f.result().value or []))
                )
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().value or []))

    def get_metadata(
        self, video_path: Path, cb: Callable[[Optional[dict]], None]
    ) -> None:
        fut = self._gui_ports.submit(
            "asset.get_metadata", video_path=video_path
        )
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(lambda: cb(f.result().value))
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().value))

    def save_metadata(
        self, video_path: Path, metadata_dict: dict, cb: Callable[[bool], None]
    ) -> None:
        fut = self._gui_ports.submit(
            "asset.save_metadata",
            video_path=video_path,
            metadata_dict=metadata_dict,
        )
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(
                    lambda: cb(
                        bool(f.result().value) if f.result().ok else False
                    )
                )
            )
        else:
            fut.add_done_callback(
                lambda f: cb(
                    bool(f.result().value) if f.result().ok else False
                )
            )

    def get_current_metadata(
        self, cb: Callable[[Optional[dict]], None]
    ) -> None:
        try:
            cb(self._auto_recorder.metadata.to_dict())
        except Exception:
            cb(None)

    def get_video_length(
        self, video_path: Path, cb: Callable[[float | None], None]
    ) -> None:
        fut = self._gui_ports.submit("asset.get_length", video_path=video_path)
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(lambda: cb(f.result().value))
            )
        else:
            fut.add_done_callback(lambda f: cb(f.result().value))

    def delete_video_assets(
        self, video_path: Path, cb: Callable[[], None]
    ) -> None:
        fut = self._gui_ports.submit("asset.delete", video_path=video_path)
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(lambda _f: adapter.call_soon(cb))
        else:
            fut.add_done_callback(lambda _f: cb())

    def get_recorded_dir(self, cb: Callable[[Path | None], None]) -> None:
        fut = self._gui_ports.submit("asset.get_recorded_dir")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(lambda: cb(f.result().value))
            )
        else:
            fut.add_done_callback(lambda f: cb(cast(Path, f.result().value)))

    def get_edited_dir(self, cb: Callable[[Path | None], None]) -> None:
        fut = self._gui_ports.submit("asset.get_edited_dir")
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(
                lambda f: adapter.call_soon(lambda: cb(f.result().value))
            )
        else:
            fut.add_done_callback(lambda f: cb(cast(Path, f.result().value)))

    def delete_edited_asset(
        self, video_path: Path, cb: Callable[[], None]
    ) -> None:
        fut = self._gui_ports.submit(
            "asset.delete_edited", video_path=video_path
        )
        adapter = self.adapter
        if adapter is not None:
            fut.add_done_callback(lambda _f: adapter.call_soon(cb))
        else:
            fut.add_done_callback(lambda _f: cb())

    def close(self) -> None:
        """GUI 終了時のクリーンアップ。"""
        try:
            # 進捗購読など GUI リスナーコレクションをクリア
            self._stop_auto_recorder()
            # detach GUI runtime adapter
            if self.adapter is not None:
                try:
                    self.adapter.close()
                except Exception:
                    pass
            self._record_state_listeners.clear()
            self._operation_msg_listeners.clear()
            self._power_off_listeners.clear()
            self._progress_listeners.clear()
            # runtime を停止 (他に共有利用が無い前提)
            if self.runtime:
                self.runtime.stop()
            self.logger.info("GUIApplicationController closed")
        except Exception as e:
            self.logger.error(
                "GUIApplicationController close error", error=str(e)
            )


__all__ = ["GUIApplicationController"]

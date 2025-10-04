"""Slim GUI controller using new runtime adapter (fully async push model)."""

from __future__ import annotations

from concurrent.futures import Future as ThreadFuture
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk

from splat_replay.application.events.types import EventTypes
from splat_replay.application.interfaces import (
    VideoAssetRepositoryPort,
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
from splat_replay.gui.utils.runtime_adapter import GuiRuntimeAdapter
from splat_replay.infrastructure import GuiRuntimePortAdapter
from splat_replay.infrastructure.runtime.commands import CommandResult
from splat_replay.infrastructure.runtime.events import Event
from splat_replay.infrastructure.runtime.runtime import AppRuntime
from splat_replay.shared.config import BehaviorSettings
from splat_replay.shared.di import configure_container, resolve
from splat_replay.shared.logger import get_logger


class GUIApplicationController:
    def __init__(self, root: ttk.Window) -> None:
        self.logger = get_logger()

        self.container = configure_container()
        self.runtime: AppRuntime = resolve(self.container, AppRuntime)
        self._gui_ports: GuiRuntimePortAdapter = resolve(
            self.container, GuiRuntimePortAdapter
        )
        self.behavior_settings: BehaviorSettings = resolve(
            self.container, BehaviorSettings
        )
        self._device_checker: DeviceChecker = resolve(
            self.container, DeviceChecker
        )
        self._auto_recorder: AutoRecorder = resolve(
            self.container, AutoRecorder
        )
        self._auto_editor: AutoEditor = resolve(self.container, AutoEditor)
        self._auto_uploader: AutoUploader = resolve(
            self.container, AutoUploader
        )
        self._progress: ProgressReporter = resolve(
            self.container, ProgressReporter
        )
        self._asset_repo: VideoAssetRepositoryPort = resolve(
            self.container, VideoAssetRepositoryPort
        )
        self._video_editor: VideoEditorPort = resolve(
            self.container, VideoEditorPort
        )
        self._state_machine: StateMachine = resolve(
            self.container, StateMachine
        )

        self._record_reset_listeners: List[Callable[[], None]] = []
        self._record_state_listeners: List[Callable[[RecordState], None]] = []
        self._operation_msg_listeners: List[Callable[[str], None]] = []
        self._power_off_listeners: List[Callable[[], None]] = []
        self._progress_listeners: List[Callable[[dict], None]] = []
        self._asset_event_listeners: List[Callable[[str, dict], None]] = []
        self._asset_events = {
            EventTypes.ASSET_RECORDED_SAVED,
            EventTypes.ASSET_RECORDED_METADATA_UPDATED,
            EventTypes.ASSET_RECORDED_SUBTITLE_UPDATED,
            EventTypes.ASSET_RECORDED_DELETED,
            EventTypes.ASSET_EDITED_SAVED,
            EventTypes.ASSET_EDITED_DELETED,
        }
        self._metadata_listeners: List[
            Callable[[Dict[str, str | int | None]], None]
        ] = []
        self.adapter = GuiRuntimeAdapter(
            dispatcher=self._gui_ports,
            subscriber=self._gui_ports,
            frame_source=self._gui_ports,
            tk_root=root,
        )
        self.adapter.add_event_handler(self._on_event)
        self.logger.info("GUIApplicationController initialized")

    def _on_event(self, ev: Event) -> None:
        if ev.type == EventTypes.RECORDER_STATE:
            state = self._state_machine.state
            for cb in list(self._record_state_listeners):
                try:
                    self.adapter.call_soon(cb, state)
                except Exception:
                    pass
        elif ev.type == EventTypes.RECORDER_RESET:
            for cb in list(self._record_reset_listeners):
                try:
                    self.adapter.call_soon(cb)
                except Exception:
                    pass
        elif ev.type == EventTypes.RECORDER_OPERATION:
            msg = ev.payload.get("message", "")
            for cb in list(self._operation_msg_listeners):
                try:
                    self.adapter.call_soon(cb, msg)
                except Exception:
                    pass
        elif ev.type == EventTypes.RECORDER_METADATA_UPDATED:
            md_payload = ev.payload.get("metadata") or {}
            if not isinstance(md_payload, dict):
                return
            for cb in list(self._metadata_listeners):
                try:
                    self.adapter.call_soon(cb, dict(md_payload))
                except Exception:
                    pass
        elif ev.type == EventTypes.POWER_OFF_DETECTED:
            for cb in list(self._power_off_listeners):
                try:
                    self.adapter.call_soon(cb)
                except Exception:
                    pass
        elif ev.type.startswith(EventTypes.PROGRESS_PREFIX):
            payload = dict(ev.payload)
            payload["kind"] = ev.type[len(EventTypes.PROGRESS_PREFIX) :]
            for cb in list(self._progress_listeners):
                try:
                    self.adapter.call_soon(cb, payload)
                except Exception:
                    pass
        elif ev.type in self._asset_events:
            for cb in list(self._asset_event_listeners):
                try:
                    self.adapter.call_soon(cb, ev.type, dict(ev.payload))
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
    def on_preview_frame(self, handler: Callable[[Frame], None]) -> None:
        """
        プレビュー用のフレームハンドラを登録。

        GUI スレッドで呼び出される。
        """
        self.adapter.add_frame_handler(handler)

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
    def add_record_reset_listener(self, cb: Callable[[], None]) -> None:
        self._record_reset_listeners.append(cb)

    def remove_record_reset_listener(self, cb: Callable[[], None]) -> None:
        if cb in self._record_reset_listeners:
            self._record_reset_listeners.remove(cb)

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
    def get_current_metadata(
        self, cb: Callable[[Optional[Dict[str, str | int | None]]], None]
    ) -> None:
        fut = self._gui_ports.submit("recorder.get_metadata")

        def _on_done(fut_inner):
            try:
                result = fut_inner.result()
                metadata = result.value
                metadata = metadata.to_dict() if metadata else None
            except Exception:
                metadata = None
            self.adapter.call_soon(lambda: cb(metadata))

        fut.add_done_callback(_on_done)

    # metadata listeners (push model)
    def add_metadata_listener(
        self, cb: Callable[[Dict[str, str | int | None]], None]
    ) -> None:
        self._metadata_listeners.append(cb)

    def remove_metadata_listener(
        self, cb: Callable[[Dict[str, str | int | None]], None]
    ) -> None:
        if cb in self._metadata_listeners:
            self._metadata_listeners.remove(cb)

    def start_manual_recording(self, cb: Callable[[bool], None]) -> None:
        fut = self._gui_ports.submit("recorder.start")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().ok))
        )

    def stop_manual_recording(self, cb: Callable[[bool], None]) -> None:
        fut = self._gui_ports.submit("recorder.stop")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().ok))
        )

    def pause_manual_recording(self, cb: Callable[[bool], None]) -> None:
        fut = self._gui_ports.submit("recorder.pause")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().ok))
        )

    def resume_manual_recording(self, cb: Callable[[bool], None]) -> None:
        fut = self._gui_ports.submit("recorder.resume")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().ok))
        )

    # Asset / metadata (synchronous simplified)
    def get_video_list(self, cb: Callable[[List[VideoAsset]], None]) -> None:
        fut = self._gui_ports.submit("asset.list")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(
                lambda: cb((f.result().value or []))
            )
        )

    def get_video_assets_with_length(
        self, cb: Callable[[List[Tuple[VideoAsset, float | None]]], None]
    ) -> None:
        fut = self._gui_ports.submit("asset.list_with_length")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(
                lambda: cb((f.result().value or []))
            )
        )

    def get_edited_assets_with_length(
        self,
        cb: Callable[
            [List[Tuple[Path, float | None, dict[str, str] | None]]], None
        ],
    ) -> None:
        fut = self._gui_ports.submit("asset.list_edited_with_length")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(
                lambda: cb((f.result().value or []))
            )
        )

    def get_metadata(
        self,
        video_path: Path,
        cb: Callable[[Optional[Dict[str, str | None]]], None],
    ) -> None:
        fut = self._gui_ports.submit(
            "asset.get_metadata", video_path=video_path
        )
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().value))
        )

    def save_metadata(
        self, video_path: Path, metadata_dict: dict, cb: Callable[[bool], None]
    ) -> None:
        fut = self._gui_ports.submit(
            "asset.save_metadata",
            video_path=video_path,
            metadata_dict=metadata_dict,
        )
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(
                lambda: cb(bool(f.result().value) if f.result().ok else False)
            )
        )

    def get_subtitle(
        self, video_path: Path, cb: Callable[[Optional[str]], None]
    ) -> None:
        fut = self._gui_ports.submit(
            "asset.get_subtitle", video_path=video_path
        )
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().value))
        )

    def save_subtitle(
        self, video_path: Path, content: str, cb: Callable[[bool], None]
    ) -> None:
        fut = self._gui_ports.submit(
            "asset.save_subtitle", video_path=video_path, content=content
        )

        def _notify(result_future: ThreadFuture[CommandResult[bool]]) -> None:
            try:
                res = result_future.result()
                success = bool(res.value) if res.ok else False
            except Exception:
                success = False
            self.adapter.call_soon(lambda: cb(success))

        fut.add_done_callback(_notify)

    def get_video_length(
        self, video_path: Path, cb: Callable[[float | None], None]
    ) -> None:
        fut = self._gui_ports.submit("asset.get_length", video_path=video_path)
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().value))
        )

    def delete_video_assets(
        self, video_path: Path, cb: Callable[[], None]
    ) -> None:
        fut = self._gui_ports.submit("asset.delete", video_path=video_path)
        fut.add_done_callback(lambda _f: self.adapter.call_soon(cb))

    def get_recorded_dir(self, cb: Callable[[Path | None], None]) -> None:
        fut = self._gui_ports.submit("asset.get_recorded_dir")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().value))
        )

    def get_edited_dir(self, cb: Callable[[Path | None], None]) -> None:
        fut = self._gui_ports.submit("asset.get_edited_dir")
        fut.add_done_callback(
            lambda f: self.adapter.call_soon(lambda: cb(f.result().value))
        )

    def delete_edited_asset(
        self, video_path: Path, cb: Callable[[], None]
    ) -> None:
        fut = self._gui_ports.submit(
            "asset.delete_edited", video_path=video_path
        )
        fut.add_done_callback(lambda _f: self.adapter.call_soon(cb))

    def close(self) -> None:
        """GUI 終了時のクリーンアップ。"""
        try:
            # 進捗購読など GUI リスナーコレクションをクリア
            self._stop_auto_recorder()
            # detach GUI runtime adapter
            self.adapter.close()
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

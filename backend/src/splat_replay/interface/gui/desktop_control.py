"""デスクトップ親子プロセス間の制御信号。ネットワークには公開しない。"""

from __future__ import annotations

import multiprocessing
from dataclasses import dataclass, field
from multiprocessing.synchronize import Event
from multiprocessing.sharedctypes import SynchronizedString
from typing import Protocol


@dataclass
class DesktopSignals:
    requested: Event = field(default_factory=multiprocessing.Event)
    quitting: Event = field(default_factory=multiprocessing.Event)
    ready: Event = field(default_factory=multiprocessing.Event)
    activated: Event = field(default_factory=multiprocessing.Event)
    started: Event = field(default_factory=multiprocessing.Event)
    tray_status: SynchronizedString = field(
        default_factory=lambda: multiprocessing.Array("c", 512)
    )


def describe_tray_status(
    recording: str, processing: str, monitoring: str, power: str
) -> tuple[str, str]:
    """実際の処理を優先し、同時に発生している状態も説明に残す。"""
    details: list[str] = []
    if recording == "RECORDING":
        details.append("録画中")
    elif recording == "PAUSED":
        details.append("録画一時停止中")
    if processing == "running":
        details.append("編集・アップロード中")
    elif processing == "cancelling":
        details.append("編集・アップロード停止処理中")
    elif processing == "failed":
        details.append("編集・アップロード失敗（画面を開いて確認）")
    if power == "capture_disconnected":
        details.append("キャプチャ機器未接続")
    elif monitoring == "stopped":
        details.append("自動録画停止中")

    if recording in ("RECORDING", "PAUSED"):
        return "recording", "／".join(details)
    if processing in ("running", "cancelling"):
        return "processing", "／".join(details)
    if details:
        return "attention", "／".join(details)
    if monitoring != "running" or power == "unknown":
        return "starting", "起動・機器確認中"
    return "waiting", "待機中（プレイ開始を待っています）"


class DesktopControl(Protocol):
    def take(self, command: str) -> bool: ...
    def state(self, name: str, value: bool) -> None: ...

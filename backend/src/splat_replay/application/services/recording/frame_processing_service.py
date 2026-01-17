"""Frame processing service - フレーム取得と処理。

Phase 4 Step 2: AutoRecorder からフレーム処理ロジックを抽出。
"""

from __future__ import annotations

import asyncio

from splat_replay.application.interfaces import (
    DomainEventPublisher,
    LoggerPort,
)
from splat_replay.application.services.recording.frame_capture_producer import (
    FrameCaptureProducer,
)
from splat_replay.domain.events import PowerOffDetected
from splat_replay.domain.models import Frame
from splat_replay.domain.services import FrameAnalyzer

# 定数
POWER_OFF_CHECK_INTERVAL = 5.0
POWER_OFF_COUNT_THRESHOLD = 3


class FrameProcessingService:
    """フレーム取得と処理を担当するサービス。

    責務:
    - フレーム取得（FrameCaptureProducer から）
    - 電源OFF検出
    - フレーム解析準備
    """

    def __init__(
        self,
        capture_producer: FrameCaptureProducer,
        analyzer: FrameAnalyzer,
        logger: LoggerPort,
        domain_publisher: DomainEventPublisher | None = None,
    ):
        self._capture_producer = capture_producer
        self.analyzer = analyzer
        self.logger = logger
        self._domain_publisher = domain_publisher

    # ================================================================
    # フレーム取得
    # ================================================================
    async def acquire_frame(self) -> Frame | None:
        """キューからフレームを取得する。

        Returns:
            取得したフレーム（取得失敗時は None）
        """
        try:
            return await asyncio.to_thread(
                self._capture_producer.get_frame, 0.1
            )
        except Exception as e:
            self.logger.warning("フレーム取得エラー", error=str(e))
            return None

    # ================================================================
    # 電源OFF検出
    # ================================================================
    async def check_power_off(
        self, frame: Frame, off_count: int, last_check: float
    ) -> tuple[int, float, bool]:
        """電源OFF検出を行う。

        Args:
            frame: 処理対象のフレーム
            off_count: 電源OFFと判定された回数
            last_check: 最後にチェックした時刻

        Returns:
            (更新後のoff_count, 更新後のlast_check, 電源OFFフラグ)
        """
        import time

        now = time.time()
        if now - last_check < POWER_OFF_CHECK_INTERVAL:
            return off_count, last_check, False

        last_check = now
        power_is_off = await self.analyzer.detect_power_off(frame)

        if power_is_off:
            off_count += 1
            self.logger.info(f"電源OFFの可能性 ({off_count}回目)")
        else:
            off_count = 0

        detected = off_count >= POWER_OFF_COUNT_THRESHOLD
        return off_count, last_check, detected

    # ================================================================
    # イベント通知
    # ================================================================
    def publish_power_off_detected(self, final: bool = False) -> None:
        """電源OFF検出イベントを発行する。

        Args:
            final: 最終通知フラグ
        """
        # ドメインイベント発行
        if self._domain_publisher:
            event = PowerOffDetected(
                consecutive_count=POWER_OFF_COUNT_THRESHOLD,
                threshold=POWER_OFF_COUNT_THRESHOLD,
                final=final,
            )
            self._domain_publisher.publish_domain_event(event)

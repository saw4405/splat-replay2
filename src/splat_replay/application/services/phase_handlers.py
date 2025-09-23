from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from splat_replay.application.services.recording_context import SessionPhase
from splat_replay.domain.models import Frame

if TYPE_CHECKING:  # pragma: no cover - 型チェックのみ
    from .auto_recorder import AutoRecorder


class PhaseHandler:
    """各フェーズ固有処理を担当する Strategy。"""

    async def handle(
        self, r: "AutoRecorder", frame: Frame
    ) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


@dataclass(slots=True)
class StandbyPhaseHandler(PhaseHandler):
    """STANDBY / MATCHING フェーズ。

    - マッチング開始検出 (started_at 設定)
    - ゲームモード / レート抽出
    - スケジュール変更検出 (リセット)
    - バトル開始検出 (録画開始)
    """

    async def handle(self, r: "AutoRecorder", frame: Frame) -> None:  # noqa: C901 (分岐は限定的)
        md = r.metadata
        # まだマッチングに入っていない
        if md.started_at is None:
            if await r._cached_call(r.analyzer.detect_match_select, frame):
                game_mode = await r._cached_call(
                    r.analyzer.extract_game_mode, frame
                )
                if game_mode is not None and game_mode != md.game_mode:
                    md.game_mode = game_mode
                    r.logger.info("ゲームモード取得", mode=str(md.game_mode))

                rate = await r._cached_call(
                    r.analyzer.extract_rate, frame, md.game_mode
                )
                if rate is not None and (
                    not isinstance(rate, type(md.rate)) or rate != md.rate
                ):
                    md.rate = rate
                    r.logger.info("レート取得", rate=str(rate))

            if await r._cached_call(r.analyzer.detect_matching_start, frame):
                r.logger.info("マッチング開始を検出")
                await r._publish_operation_status(
                    "マッチング開始を検出しました。"
                )
                md.started_at = r._now_dt()
                return
        else:  # MATCHING フェーズ
            if await r._cached_call(r.analyzer.detect_schedule_change, frame):
                r.logger.info("スケジュール変更を検出、情報をリセット")
                await r._publish_operation_status(
                    "スケジュール変更を検出しました。"
                )
                await r._reset()
                return
            if await r._cached_call(
                r.analyzer.detect_session_start, frame, md.game_mode
            ):
                r.logger.info("バトル開始を検出")
                await r._publish_operation_status(
                    "バトル開始を検出したため、録画を開始します。"
                )
                await r.start()
                r._publisher_worker.enqueue_event(
                    r.EventTypes.RECORDER_MATCH, {"event": "battle_started"}
                )


@dataclass(slots=True)
class InGamePhaseHandler(PhaseHandler):
    """IN_GAME フェーズ (録画中、finish 未検出)。"""

    async def handle(self, r: "AutoRecorder", frame: Frame) -> None:
        gm = r._game_mode()
        now = r._now_ts()
        # 早期中断
        if (
            now - r._ctx.battle_started_at <= r.EARLY_ABORT_WINDOW_SECONDS
            and await r._cached_call(
                r.analyzer.detect_session_abort, frame, gm
            )
        ):
            r.logger.info("バトル中断を検出したため録画を中止")
            await r._publish_operation_status(
                "バトル中断を検出したため、録画を中止します。"
            )
            await r.cancel()
            return
        # 録画長超過
        if now - r._ctx.battle_started_at >= r.MAX_RECORDING_SECONDS:
            r.logger.info("録画が10分以上続いたため停止")
            await r._publish_operation_status(
                "録画が10分以上続いたため、録画を停止します。"
            )
            await r.stop()
            return
        # バトル終了
        if await r._cached_call(r.analyzer.detect_session_finish, frame, gm):
            r.logger.info("バトル終了を検出、一時停止")
            await r._publish_operation_status(
                "バトル終了を検出したため、録画を一時停止します。"
            )
            r._ctx.finish = True
            r._ctx.resume_trigger = (
                lambda f: r.analyzer.detect_session_judgement(f, gm)
            )
            await r.pause()


@dataclass(slots=True)
class PostFinishPhaseHandler(PhaseHandler):
    """POST_FINISH フェーズ (判定/ローディング/結果待ち)。"""

    async def handle(self, r: "AutoRecorder", frame: Frame) -> None:  # noqa: C901
        gm = r._game_mode()
        # 判定
        if await r._cached_call(
            r.analyzer.detect_session_judgement, frame, gm
        ):
            r.logger.info("バトル判定を検出")
            await r._publish_operation_status("バトル判定を検出しました。")
            judgement = await r._cached_call(
                r.analyzer.extract_session_judgement, frame, gm
            )
            if judgement is not None and r._ctx.metadata.judgement is None:
                r._ctx.metadata.judgement = judgement
                r.logger.info(
                    "バトルジャッジメント取得", judgement=str(judgement)
                )
            return
        # ローディング
        if await r._cached_call(r.analyzer.detect_loading, frame):
            r.logger.info("ローディング画面を検出、一時停止")
            await r._publish_operation_status(
                "ローディング画面を検出したため、録画を一時停止します。"
            )
            r._ctx.resume_trigger = r.analyzer.detect_loading_end
            await r.pause()
            return
        # 結果
        if await r._cached_call(r.analyzer.detect_session_result, frame, gm):
            r.logger.info("結果画面を検出")
            await r._publish_operation_status("結果画面を検出しました。")
            r._ctx.result_frame = frame


@dataclass(slots=True)
class ResultPhaseHandler(PhaseHandler):
    """RESULT フェーズ (結果画面表示中: 画面離脱で停止)。"""

    async def handle(self, r: "AutoRecorder", frame: Frame) -> None:
        gm = r._game_mode()
        # 結果画面から離れたか
        still_result = await r._cached_call(
            r.analyzer.detect_session_result, frame, gm
        )
        if not still_result:
            r.logger.info("結果画面から遷移")
            await r._publish_operation_status(
                "結果画面から遷移したため、録画を停止します。"
            )
            await r.stop()


# 利便: 外部へエクスポート (AutoRecorder から利用)
__all__ = [
    "SessionPhase",
    "PhaseHandler",
    "StandbyPhaseHandler",
    "InGamePhaseHandler",
    "PostFinishPhaseHandler",
    "ResultPhaseHandler",
]

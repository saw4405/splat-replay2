"""インストール状態ドメインモデルのテスト。"""

from datetime import datetime
from typing import List

import pytest

from splat_replay.domain.models import InstallationState, InstallationStep


class TestInstallationStep:
    """InstallationStepのテストクラス。"""

    def test_get_all_steps_returns_correct_order(self) -> None:
        """全ステップが正しい順序で取得できることを確認する。"""
        steps = InstallationStep.get_all_steps()
        expected = [
            InstallationStep.HARDWARE_CHECK,
            InstallationStep.OBS_SETUP,
            InstallationStep.FFMPEG_SETUP,
            InstallationStep.TESSERACT_SETUP,
            InstallationStep.FONT_INSTALLATION,
            InstallationStep.YOUTUBE_SETUP,
        ]
        assert steps == expected

    def test_get_next_step_returns_correct_next_step(self) -> None:
        """次のステップが正しく取得できることを確認する。"""
        assert (
            InstallationStep.HARDWARE_CHECK.get_next_step()
            == InstallationStep.OBS_SETUP
        )
        assert (
            InstallationStep.OBS_SETUP.get_next_step()
            == InstallationStep.FFMPEG_SETUP
        )
        assert (
            InstallationStep.FFMPEG_SETUP.get_next_step()
            == InstallationStep.TESSERACT_SETUP
        )
        assert (
            InstallationStep.TESSERACT_SETUP.get_next_step()
            == InstallationStep.FONT_INSTALLATION
        )
        assert (
            InstallationStep.FONT_INSTALLATION.get_next_step()
            == InstallationStep.YOUTUBE_SETUP
        )

    def test_get_next_step_returns_none_for_last_step(self) -> None:
        """最後のステップの次のステップがNoneであることを確認する。"""
        assert InstallationStep.YOUTUBE_SETUP.get_next_step() is None

    def test_get_previous_step_returns_correct_previous_step(self) -> None:
        """前のステップが正しく取得できることを確認する。"""
        assert (
            InstallationStep.YOUTUBE_SETUP.get_previous_step()
            == InstallationStep.FONT_INSTALLATION
        )
        assert (
            InstallationStep.FONT_INSTALLATION.get_previous_step()
            == InstallationStep.TESSERACT_SETUP
        )
        assert (
            InstallationStep.TESSERACT_SETUP.get_previous_step()
            == InstallationStep.FFMPEG_SETUP
        )
        assert (
            InstallationStep.FFMPEG_SETUP.get_previous_step()
            == InstallationStep.OBS_SETUP
        )
        assert (
            InstallationStep.OBS_SETUP.get_previous_step()
            == InstallationStep.HARDWARE_CHECK
        )

    def test_get_previous_step_returns_none_for_first_step(self) -> None:
        """最初のステップの前のステップがNoneであることを確認する。"""
        assert InstallationStep.HARDWARE_CHECK.get_previous_step() is None

    def test_get_display_name_returns_japanese_names(self) -> None:
        """表示名が日本語で取得できることを確認する。"""
        assert InstallationStep.HARDWARE_CHECK.get_display_name() == "ハードウェア確認"
        assert InstallationStep.OBS_SETUP.get_display_name() == "OBSセットアップ"
        assert InstallationStep.FFMPEG_SETUP.get_display_name() == "FFMPEGセットアップ"
        assert InstallationStep.TESSERACT_SETUP.get_display_name() == "Tesseractセットアップ"
        assert InstallationStep.FONT_INSTALLATION.get_display_name() == "フォントインストール"
        assert InstallationStep.YOUTUBE_SETUP.get_display_name() == "YouTube API設定"


class TestInstallationState:
    """InstallationStateのテストクラス。"""

    def test_default_state_is_not_completed(self) -> None:
        """デフォルト状態では未完了であることを確認する。"""
        state = InstallationState()
        assert not state.is_completed
        assert state.current_step == InstallationStep.HARDWARE_CHECK
        assert state.completed_steps == []
        assert state.skipped_steps == []
        assert state.installation_date is None

    def test_mark_step_completed_adds_to_completed_list(self) -> None:
        """ステップ完了マークが完了リストに追加されることを確認する。"""
        state = InstallationState()
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)

        assert InstallationStep.HARDWARE_CHECK in state.completed_steps
        assert InstallationStep.HARDWARE_CHECK not in state.skipped_steps

    def test_mark_step_completed_removes_from_skipped_list(self) -> None:
        """ステップ完了マークがスキップリストから削除されることを確認する。"""
        state = InstallationState()
        state.mark_step_skipped(InstallationStep.HARDWARE_CHECK)
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)

        assert InstallationStep.HARDWARE_CHECK in state.completed_steps
        assert InstallationStep.HARDWARE_CHECK not in state.skipped_steps

    def test_mark_step_skipped_adds_to_skipped_list(self) -> None:
        """ステップスキップマークがスキップリストに追加されることを確認する。"""
        state = InstallationState()
        state.mark_step_skipped(InstallationStep.HARDWARE_CHECK)

        assert InstallationStep.HARDWARE_CHECK in state.skipped_steps
        assert InstallationStep.HARDWARE_CHECK not in state.completed_steps

    def test_mark_step_skipped_removes_from_completed_list(self) -> None:
        """ステップスキップマークが完了リストから削除されることを確認する。"""
        state = InstallationState()
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        state.mark_step_skipped(InstallationStep.HARDWARE_CHECK)

        assert InstallationStep.HARDWARE_CHECK in state.skipped_steps
        assert InstallationStep.HARDWARE_CHECK not in state.completed_steps

    def test_is_step_completed_returns_correct_status(self) -> None:
        """ステップ完了状態が正しく判定されることを確認する。"""
        state = InstallationState()
        assert not state.is_step_completed(InstallationStep.HARDWARE_CHECK)

        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        assert state.is_step_completed(InstallationStep.HARDWARE_CHECK)

    def test_is_step_skipped_returns_correct_status(self) -> None:
        """ステップスキップ状態が正しく判定されることを確認する。"""
        state = InstallationState()
        assert not state.is_step_skipped(InstallationStep.HARDWARE_CHECK)

        state.mark_step_skipped(InstallationStep.HARDWARE_CHECK)
        assert state.is_step_skipped(InstallationStep.HARDWARE_CHECK)

    def test_can_proceed_to_next_step_when_completed(self) -> None:
        """ステップが完了している場合に次に進めることを確認する。"""
        state = InstallationState()
        assert not state.can_proceed_to_next_step()

        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        assert state.can_proceed_to_next_step()

    def test_can_proceed_to_next_step_when_skipped(self) -> None:
        """ステップがスキップされている場合に次に進めることを確認する。"""
        state = InstallationState()
        assert not state.can_proceed_to_next_step()

        state.mark_step_skipped(InstallationStep.HARDWARE_CHECK)
        assert state.can_proceed_to_next_step()

    def test_proceed_to_next_step_advances_current_step(self) -> None:
        """次のステップに進む処理が正しく動作することを確認する。"""
        state = InstallationState()
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)

        result = state.proceed_to_next_step()
        assert result is True
        assert state.current_step == InstallationStep.OBS_SETUP

    def test_proceed_to_next_step_fails_when_cannot_proceed(self) -> None:
        """進行条件を満たしていない場合に次に進めないことを確認する。"""
        state = InstallationState()

        result = state.proceed_to_next_step()
        assert result is False
        assert state.current_step == InstallationStep.HARDWARE_CHECK

    def test_proceed_to_next_step_completes_installation_at_end(self) -> None:
        """最後のステップで次に進むとインストールが完了することを確認する。"""
        state = InstallationState()
        state.current_step = InstallationStep.YOUTUBE_SETUP
        state.mark_step_completed(InstallationStep.YOUTUBE_SETUP)

        result = state.proceed_to_next_step()
        assert result is True
        assert state.is_completed
        assert state.installation_date is not None

    def test_go_back_to_previous_step_moves_backward(self) -> None:
        """前のステップに戻る処理が正しく動作することを確認する。"""
        state = InstallationState()
        state.current_step = InstallationStep.OBS_SETUP

        result = state.go_back_to_previous_step()
        assert result is True
        assert state.current_step == InstallationStep.HARDWARE_CHECK

    def test_go_back_to_previous_step_fails_at_first_step(self) -> None:
        """最初のステップで前に戻れないことを確認する。"""
        state = InstallationState()

        result = state.go_back_to_previous_step()
        assert result is False
        assert state.current_step == InstallationStep.HARDWARE_CHECK

    def test_complete_installation_sets_completed_state(self) -> None:
        """インストール完了処理が正しく動作することを確認する。"""
        state = InstallationState()
        before_completion = datetime.now()

        state.complete_installation()

        assert state.is_completed
        assert state.installation_date is not None
        assert state.installation_date >= before_completion

    def test_get_progress_percentage_calculates_correctly(self) -> None:
        """進行状況パーセンテージが正しく計算されることを確認する。"""
        state = InstallationState()

        # 初期状態では0%
        assert state.get_progress_percentage() == 0.0

        # 1つ完了で約16.67%（6ステップ中1つ）
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        expected = (1 / 6) * 100
        assert abs(state.get_progress_percentage() - expected) < 0.01

        # 1つ完了、1つスキップで約33.33%（6ステップ中2つ処理済み）
        state.mark_step_skipped(InstallationStep.OBS_SETUP)
        expected = (2 / 6) * 100
        assert abs(state.get_progress_percentage() - expected) < 0.01

    def test_get_remaining_steps_returns_unprocessed_steps(self) -> None:
        """残りステップが正しく取得されることを確認する。"""
        state = InstallationState()

        # 初期状態では全ステップが残り
        remaining = state.get_remaining_steps()
        assert len(remaining) == 6

        # 1つ完了すると5つが残り
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        remaining = state.get_remaining_steps()
        assert len(remaining) == 5
        assert InstallationStep.HARDWARE_CHECK not in remaining

        # 1つスキップするとさらに1つ減る
        state.mark_step_skipped(InstallationStep.OBS_SETUP)
        remaining = state.get_remaining_steps()
        assert len(remaining) == 4
        assert InstallationStep.OBS_SETUP not in remaining

    def test_validate_state_consistency_detects_overlap(self) -> None:
        """状態の整合性検証が重複を検出することを確認する。"""
        state = InstallationState()

        # 正常な状態では整合性がある
        assert state.validate_state_consistency()

        # 同じステップを完了とスキップの両方に追加すると不整合
        state.completed_steps.append(InstallationStep.HARDWARE_CHECK)
        state.skipped_steps.append(InstallationStep.HARDWARE_CHECK)
        assert not state.validate_state_consistency()

    def test_validate_state_consistency_detects_completed_without_date(self) -> None:
        """完了状態なのに完了日時がない不整合を検出することを確認する。"""
        state = InstallationState()
        state.is_completed = True
        # installation_dateはNoneのまま

        assert not state.validate_state_consistency()

    def test_validate_state_consistency_passes_for_valid_state(self) -> None:
        """正常な状態で整合性検証が通ることを確認する。"""
        state = InstallationState()
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)
        state.mark_step_skipped(InstallationStep.OBS_SETUP)

        assert state.validate_state_consistency()

    def test_pydantic_validation_works(self) -> None:
        """Pydanticバリデーションが正しく動作することを確認する。"""
        # 正常なデータでインスタンス作成
        data = {
            "is_completed": False,
            "current_step": InstallationStep.HARDWARE_CHECK,
            "completed_steps": [InstallationStep.HARDWARE_CHECK],
            "skipped_steps": [],
            "installation_date": None,
        }
        state = InstallationState(**data)

        assert not state.is_completed
        assert state.current_step == InstallationStep.HARDWARE_CHECK
        assert state.completed_steps == [InstallationStep.HARDWARE_CHECK]

    def test_enum_serialization_works(self) -> None:
        """Enumの値がシリアライズされることを確認する。"""
        state = InstallationState()
        state.mark_step_completed(InstallationStep.HARDWARE_CHECK)

        data = state.dict()
        assert data["current_step"] == InstallationStep.HARDWARE_CHECK
        assert data["completed_steps"] == [InstallationStep.HARDWARE_CHECK]

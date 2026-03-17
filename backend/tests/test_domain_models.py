"""Domain Models Unit Tests.

責務：
- Domain 層の値オブジェクト（Enum）の動作を検証する
- 等値性・不変性を確認する
- バリデーション動作を確認する

分類: logic
"""

from __future__ import annotations

import pytest

from splat_replay.domain.models import GameMode, Judgement, Match, Rule, Stage


class TestMatch:
    """Matchモデルのテスト。"""

    def test_enum_values_are_unique(self) -> None:
        """各Match値が一意であることを確認。"""
        values = [match.value for match in Match]
        assert len(values) == len(set(values))

    def test_is_anarchy(self) -> None:
        """is_anarchy()メソッドのテスト。"""
        assert Match.ANARCHY.is_anarchy()
        assert Match.ANARCHY_OPEN.is_anarchy()
        assert Match.ANARCHY_SERIES.is_anarchy()
        assert not Match.REGULAR.is_anarchy()
        assert not Match.X.is_anarchy()
        assert not Match.SPLATFEST.is_anarchy()

    def test_is_fest(self) -> None:
        """is_fest()メソッドのテスト。"""
        assert Match.SPLATFEST.is_fest()
        assert Match.SPLATFEST_OPEN.is_fest()
        assert Match.SPLATFEST_PRO.is_fest()
        assert not Match.REGULAR.is_fest()
        assert not Match.ANARCHY.is_fest()
        assert not Match.X.is_fest()

    def test_equal_same_variant(self) -> None:
        """同じバリアントの等値性テスト。"""
        assert Match.REGULAR.equal(Match.REGULAR)
        assert Match.ANARCHY.equal(Match.ANARCHY)

    def test_equal_different_variant_strict(self) -> None:
        """異なるバリアントの等値性テスト（厳密モード）。"""
        assert not Match.ANARCHY_OPEN.equal(Match.ANARCHY_SERIES)
        assert not Match.SPLATFEST_OPEN.equal(Match.SPLATFEST_PRO)
        assert not Match.REGULAR.equal(Match.ANARCHY)

    def test_equal_ignore_open_challenge_anarchy(self) -> None:
        """equal() のignore_open_challengeオプション（バンカラ）。"""
        assert Match.ANARCHY_OPEN.equal(
            Match.ANARCHY_SERIES, ignore_open_challenge=True
        )
        assert Match.ANARCHY.equal(
            Match.ANARCHY_OPEN, ignore_open_challenge=True
        )
        assert Match.ANARCHY.equal(
            Match.ANARCHY_SERIES, ignore_open_challenge=True
        )

    def test_equal_ignore_open_challenge_fest(self) -> None:
        """equal() のignore_open_challengeオプション（フェス）。"""
        assert Match.SPLATFEST_OPEN.equal(
            Match.SPLATFEST_PRO, ignore_open_challenge=True
        )
        assert Match.SPLATFEST.equal(
            Match.SPLATFEST_OPEN, ignore_open_challenge=True
        )
        assert Match.SPLATFEST.equal(
            Match.SPLATFEST_PRO, ignore_open_challenge=True
        )

    def test_equal_cross_category_with_ignore(self) -> None:
        """異なるカテゴリでは ignore_open_challenge でも一致しない。"""
        assert not Match.ANARCHY.equal(
            Match.SPLATFEST, ignore_open_challenge=True
        )
        assert not Match.REGULAR.equal(
            Match.ANARCHY, ignore_open_challenge=True
        )

    def test_match_value_format(self) -> None:
        """Match.value が日本語表記であることを確認。"""
        assert Match.REGULAR.value == "レギュラーマッチ"
        assert Match.ANARCHY.value == "バンカラマッチ"
        assert Match.X.value == "Xマッチ"


class TestRule:
    """Ruleモデルのテスト。"""

    def test_enum_values_are_unique(self) -> None:
        """各Rule値が一意であることを確認。"""
        values = [rule.value for rule in Rule]
        assert len(values) == len(set(values))

    def test_all_rules_present(self) -> None:
        """主要ルールが全て定義されていることを確認。"""
        expected_rules = {
            Rule.TURF_WAR,
            Rule.RAINMAKER,
            Rule.SPLAT_ZONES,
            Rule.TOWER_CONTROL,
            Rule.CLAM_BLITZ,
            Rule.TRICOLOR_TURF_WAR,
        }
        actual_rules = set(Rule)
        assert actual_rules == expected_rules

    def test_rule_value_format(self) -> None:
        """Rule.value が日本語表記であることを確認。"""
        assert Rule.TURF_WAR.value == "ナワバリ"
        assert Rule.RAINMAKER.value == "ガチホコ"
        assert Rule.SPLAT_ZONES.value == "ガチエリア"
        assert Rule.TOWER_CONTROL.value == "ガチヤグラ"
        assert Rule.CLAM_BLITZ.value == "ガチアサリ"


class TestStage:
    """Stageモデルのテスト。"""

    def test_enum_values_are_unique(self) -> None:
        """各Stage値が一意であることを確認。"""
        values = [stage.value for stage in Stage]
        assert len(values) == len(set(values))

    def test_representative_stages_present(self) -> None:
        """代表的なステージが定義されていることを確認。"""
        # 一部のステージのみ確認
        assert Stage.SCORCH_GORGE in Stage
        assert Stage.EELTAIL_ALLEY in Stage
        assert Stage.MAHI_MAHI_RESORT in Stage

    def test_stage_value_format(self) -> None:
        """Stage.value が日本語表記であることを確認。"""
        assert Stage.SCORCH_GORGE.value == "ユノハナ大渓谷"
        assert Stage.EELTAIL_ALLEY.value == "ゴンズイ地区"
        assert Stage.MAHI_MAHI_RESORT.value == "マヒマヒリゾート＆スパ"


class TestJudgement:
    """Judgementモデルのテスト。"""

    def test_enum_values_are_unique(self) -> None:
        """各Judgement値が一意であることを確認。"""
        values = [judgement.value for judgement in Judgement]
        assert len(values) == len(set(values))

    def test_only_win_and_lose(self) -> None:
        """WINとLOSEのみが定義されていることを確認。"""
        assert set(Judgement) == {Judgement.WIN, Judgement.LOSE}

    def test_judgement_value_format(self) -> None:
        """Judgement.value が英語表記であることを確認。"""
        assert Judgement.WIN.value == "WIN"
        assert Judgement.LOSE.value == "LOSE"


# Rateテストは削除：新しい設計ではRateはEnumではなく、RateBase/XP/Udemaeクラスに変更された


class TestGameMode:
    """GameModeモデルのテスト。"""

    def test_enum_values_are_unique(self) -> None:
        """各GameMode値が一意であることを確認。"""
        values = [mode.value for mode in GameMode]
        assert len(values) == len(set(values))

    def test_game_mode_value_format(self) -> None:
        """GameMode.value が正しいことを確認。"""
        # 代表的なモード値を確認
        assert any(mode.value == "バトルモード" for mode in GameMode)
        assert any(mode.value == "バイトモード" for mode in GameMode)


class TestEnumSerialization:
    """Enumのシリアライズ・デシリアライズテスト。"""

    def test_match_from_string(self) -> None:
        """文字列からMatchへの変換。"""
        match = Match("レギュラーマッチ")
        assert match == Match.REGULAR

    def test_rule_from_string(self) -> None:
        """文字列からRuleへの変換。"""
        rule = Rule("ナワバリ")
        assert rule == Rule.TURF_WAR

    def test_stage_from_string(self) -> None:
        """文字列からStageへの変換。"""
        stage = Stage("ユノハナ大渓谷")
        assert stage == Stage.SCORCH_GORGE

    def test_judgement_from_string(self) -> None:
        """文字列からJudgementへの変換。"""
        judgement = Judgement("WIN")
        assert judgement == Judgement.WIN

    def test_invalid_match_value(self) -> None:
        """無効なMatch値でValueErrorが発生することを確認。"""
        with pytest.raises(ValueError, match=r"is not a valid Match"):
            Match("無効なマッチ")

    def test_invalid_rule_value(self) -> None:
        """無効なRule値でValueErrorが発生することを確認。"""
        with pytest.raises(ValueError, match=r"is not a valid Rule"):
            Rule("無効なルール")

    def test_invalid_stage_value(self) -> None:
        """無効なStage値でValueErrorが発生することを確認。"""
        with pytest.raises(ValueError, match=r"is not a valid Stage"):
            Stage("無効なステージ")

    def test_invalid_judgement_value(self) -> None:
        """無効なJudgement値でValueErrorが発生することを確認。"""
        with pytest.raises(ValueError, match=r"is not a valid Judgement"):
            Judgement("INVALID")


class TestEnumEquality:
    """Enum等値性のテスト。"""

    def test_match_equality(self) -> None:
        """同一Match値の等値性。"""
        assert Match.REGULAR == Match.REGULAR
        assert Match.REGULAR is Match.REGULAR  # シングルトン
        assert Match.REGULAR != Match.ANARCHY

    def test_rule_equality(self) -> None:
        """同一Rule値の等値性。"""
        assert Rule.TURF_WAR == Rule.TURF_WAR
        assert Rule.TURF_WAR is Rule.TURF_WAR
        assert Rule.TURF_WAR != Rule.RAINMAKER

    def test_stage_equality(self) -> None:
        """同一Stage値の等値性。"""
        assert Stage.SCORCH_GORGE == Stage.SCORCH_GORGE
        assert Stage.SCORCH_GORGE is Stage.SCORCH_GORGE
        assert Stage.SCORCH_GORGE != Stage.EELTAIL_ALLEY

    def test_judgement_equality(self) -> None:
        """同一Judgement値の等値性。"""
        assert Judgement.WIN == Judgement.WIN
        assert Judgement.WIN is Judgement.WIN
        assert Judgement.WIN != Judgement.LOSE


class TestEnumIterability:
    """Enum反復可能性のテスト。"""

    def test_match_iteration(self) -> None:
        """Match全値の反復。"""
        matches = list(Match)
        assert len(matches) > 0
        assert Match.REGULAR in matches
        assert Match.ANARCHY in matches

    def test_rule_iteration(self) -> None:
        """Rule全値の反復。"""
        rules = list(Rule)
        assert len(rules) == 6
        assert Rule.TURF_WAR in rules

    def test_stage_iteration(self) -> None:
        """Stage全値の反復。"""
        stages = list(Stage)
        assert len(stages) > 0
        assert Stage.SCORCH_GORGE in stages

    def test_judgement_iteration(self) -> None:
        """Judgement全値の反復。"""
        judgements = list(Judgement)
        assert len(judgements) == 2
        assert Judgement.WIN in judgements
        assert Judgement.LOSE in judgements

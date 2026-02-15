"""メタデータマージサービス。

責務：
- 自動更新と手動更新のマージ
- 手動編集フィールドの保護
- 3way マージの実行

このサービスはすべてのマージロジックを集約し、
UseCase から分離することで、テスタビリティと保守性を向上させる。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from splat_replay.domain.models import (
    BattleResult,
    RecordingMetadata,
    SalmonResult,
)
from splat_replay.domain.models.recording_metadata import (
    BATTLE_RESULT_REQUIRED_FIELDS,
    SALMON_RESULT_REQUIRED_FIELDS,
    has_required_fields,
)
from splat_replay.application.services.editing.metadata_parser import (
    MetadataParser,
)


class MetadataMerger:
    """録画メタデータのマージを担当するサービス。

    このサービスは以下の責務を持つ：
    1. 自動更新と手動更新の競合解決（3way マージ）
    2. 手動編集フィールドの保護
    3. メタデータ更新の検証

    設計原則：
    - 不変性：すべてのメソッドは新しい RecordingMetadata を返す
    - 純粋性：副作用なし（イベント発行は UseCase の責務）
    - 明示性：マージの意図を明確に表現
    """

    def apply_manual_updates(
        self,
        current: RecordingMetadata,
        updates: Mapping[str, object],
    ) -> tuple[RecordingMetadata, frozenset[str]]:
        """手動更新を適用する。

        Args:
            current: 現在のメタデータ
            updates: 更新内容

        Returns:
            更新後のメタデータと適用できた手動編集フィールド
        """
        # MetadataParser を使用して基本フィールドを更新
        updated, applied_fields = (
            MetadataParser.parse_metadata_updates_with_applied_fields(
                current, updates
            )
        )

        # Result オブジェクトを生成（必要なら）
        updated, result_fields = self._apply_result_updates(updated, updates)

        return updated, applied_fields.union(result_fields)

    def apply_pending_result_updates(
        self,
        current: RecordingMetadata,
        pending_updates: Mapping[str, object],
        manual_fields: frozenset[str],
    ) -> tuple[RecordingMetadata, frozenset[str]]:
        """結果確定後に保留中の手動更新を適用する。"""
        if current.result is None or not pending_updates:
            return current, frozenset()

        filtered_updates = {
            key: value
            for key, value in pending_updates.items()
            if key not in manual_fields
        }
        if not filtered_updates:
            return current, frozenset()

        updated, applied_fields = (
            MetadataParser.parse_metadata_updates_with_applied_fields(
                current, filtered_updates
            )
        )
        result_fields = applied_fields.intersection(
            RecordingMetadata.BATTLE_FIELDS | RecordingMetadata.SALMON_FIELDS
        )
        return updated, frozenset(result_fields)

    def merge_with_auto_update(
        self,
        base: RecordingMetadata,
        auto_update: RecordingMetadata,
        current: RecordingMetadata,
        manual_fields: frozenset[str],
    ) -> RecordingMetadata:
        """自動更新を現在のメタデータにマージする（3way マージ）。

        3way マージのルール：
        1. base → auto_update で変更があり、base → current で変更がない
           → auto_update の値を採用
        2. base → current で変更がある（手動編集）
           → current の値を保護（auto_update を無視）
        3. それ以外
           → current をそのまま保持

        Args:
            base: マージ開始時点のメタデータ（共通祖先）
            auto_update: 自動更新後のメタデータ
            current: 現在のメタデータ（手動編集を含む可能性）
            manual_fields: 手動編集されたフィールドのセット

        Returns:
            マージ後のメタデータ
        """
        merged = current

        # 基本フィールドのマージ
        merged = self._merge_basic_fields(
            base, auto_update, merged, manual_fields
        )

        # Result オブジェクトのマージ
        merged = self._merge_result(base, auto_update, merged, manual_fields)

        return merged

    def apply_manual_overrides(
        self,
        current: RecordingMetadata,
        updated: RecordingMetadata,
        manual_fields: frozenset[str],
    ) -> RecordingMetadata:
        """手動編集フィールドで上書きする。

        自動更新後のメタデータに対して、手動編集されたフィールドを
        現在の値で上書きする。

        Args:
            current: 現在のメタデータ（手動編集を含む）
            updated: 更新後のメタデータ
            manual_fields: 手動編集されたフィールドのセット

        Returns:
            手動編集を反映したメタデータ
        """
        if not manual_fields:
            return updated

        merged = updated

        # 基本フィールドの上書き
        if "game_mode" in manual_fields:
            merged = replace(merged, game_mode=current.game_mode)
        if "started_at" in manual_fields:
            merged = replace(merged, started_at=current.started_at)
        if "rate" in manual_fields:
            merged = replace(merged, rate=current.rate)
        if "judgement" in manual_fields:
            merged = replace(merged, judgement=current.judgement)
        if "allies" in manual_fields:
            merged = replace(merged, allies=current.allies)
        if "enemies" in manual_fields:
            merged = replace(merged, enemies=current.enemies)

        # Result フィールドの上書き
        result_fields = manual_fields.intersection(
            RecordingMetadata.BATTLE_FIELDS | RecordingMetadata.SALMON_FIELDS
        )
        if result_fields:
            merged_result = self._apply_manual_result_overrides(
                current.result, updated.result, manual_fields
            )
            merged = replace(merged, result=merged_result)

        return merged

    # ----------------------------------------------------------------
    # プライベートメソッド：Result の更新
    # ----------------------------------------------------------------

    def _apply_result_updates(
        self,
        metadata: RecordingMetadata,
        updates: Mapping[str, object],
    ) -> tuple[RecordingMetadata, frozenset[str]]:
        """Result オブジェクトを生成・更新し、適用したフィールドを返す。"""
        # 既存の Result が未設定の場合、必要なフィールドがあれば生成
        if metadata.result is None:
            if has_required_fields(updates, BATTLE_RESULT_REQUIRED_FIELDS):
                try:
                    result = BattleResult.from_dict(updates)
                    return (
                        replace(metadata, result=result),
                        frozenset(BATTLE_RESULT_REQUIRED_FIELDS),
                    )
                except Exception:
                    pass

            if has_required_fields(updates, SALMON_RESULT_REQUIRED_FIELDS):
                try:
                    result = SalmonResult.from_dict(updates)
                    return (
                        replace(metadata, result=result),
                        frozenset(SALMON_RESULT_REQUIRED_FIELDS),
                    )
                except Exception:
                    pass

        return metadata, frozenset()

    # ----------------------------------------------------------------
    # プライベートメソッド：3way マージ
    # ----------------------------------------------------------------

    def _merge_basic_fields(
        self,
        base: RecordingMetadata,
        auto_update: RecordingMetadata,
        current: RecordingMetadata,
        manual_fields: frozenset[str],
    ) -> RecordingMetadata:
        """基本フィールドの 3way マージ。"""
        merged = current

        # 各フィールドを個別にマージ
        if "game_mode" not in manual_fields:
            if (
                auto_update.game_mode != base.game_mode
                and current.game_mode == base.game_mode
            ):
                merged = replace(merged, game_mode=auto_update.game_mode)

        if "started_at" not in manual_fields:
            if (
                auto_update.started_at != base.started_at
                and current.started_at == base.started_at
            ):
                merged = replace(merged, started_at=auto_update.started_at)

        if "rate" not in manual_fields:
            if auto_update.rate != base.rate and current.rate == base.rate:
                merged = replace(merged, rate=auto_update.rate)

        if "judgement" not in manual_fields:
            if (
                auto_update.judgement != base.judgement
                and current.judgement == base.judgement
            ):
                merged = replace(merged, judgement=auto_update.judgement)

        if "allies" not in manual_fields:
            if (
                auto_update.allies != base.allies
                and current.allies == base.allies
            ):
                merged = replace(merged, allies=auto_update.allies)

        if "enemies" not in manual_fields:
            if (
                auto_update.enemies != base.enemies
                and current.enemies == base.enemies
            ):
                merged = replace(merged, enemies=auto_update.enemies)

        return merged

    def _merge_result(
        self,
        base: RecordingMetadata,
        auto_update: RecordingMetadata,
        current: RecordingMetadata,
        manual_fields: frozenset[str],
    ) -> RecordingMetadata:
        """Result オブジェクトの 3way マージ。"""
        # Result が同一なら変更なし
        if auto_update.result == base.result:
            return current

        # base から変更がなければ auto_update を採用
        if current.result == base.result:
            return replace(current, result=auto_update.result)

        # 同じ型の Result をマージ
        if (
            isinstance(base.result, BattleResult)
            and isinstance(auto_update.result, BattleResult)
            and isinstance(current.result, BattleResult)
        ):
            merged_result = self._merge_battle_result(
                base.result,
                auto_update.result,
                current.result,
                manual_fields,
            )
            return replace(current, result=merged_result)

        if (
            isinstance(base.result, SalmonResult)
            and isinstance(auto_update.result, SalmonResult)
            and isinstance(current.result, SalmonResult)
        ):
            merged_result = self._merge_salmon_result(
                base.result,
                auto_update.result,
                current.result,
                manual_fields,
            )
            return replace(current, result=merged_result)

        # 型が異なる場合は current を保持
        return current

    def _merge_battle_result(
        self,
        base: BattleResult,
        auto_update: BattleResult,
        current: BattleResult,
        manual_fields: frozenset[str],
    ) -> BattleResult:
        """BattleResult の 3way マージ。"""
        merged = current

        # 各フィールドを個別にマージ
        if "match" not in manual_fields:
            if auto_update.match != base.match and current.match == base.match:
                merged = replace(merged, match=auto_update.match)

        if "rule" not in manual_fields:
            if auto_update.rule != base.rule and current.rule == base.rule:
                merged = replace(merged, rule=auto_update.rule)

        if "stage" not in manual_fields:
            if auto_update.stage != base.stage and current.stage == base.stage:
                merged = replace(merged, stage=auto_update.stage)

        if "kill" not in manual_fields:
            if auto_update.kill != base.kill and current.kill == base.kill:
                merged = replace(merged, kill=auto_update.kill)

        if "death" not in manual_fields:
            if auto_update.death != base.death and current.death == base.death:
                merged = replace(merged, death=auto_update.death)

        if "special" not in manual_fields:
            if (
                auto_update.special != base.special
                and current.special == base.special
            ):
                merged = replace(merged, special=auto_update.special)

        return merged

    def _merge_salmon_result(
        self,
        base: SalmonResult,
        auto_update: SalmonResult,
        current: SalmonResult,
        manual_fields: frozenset[str],
    ) -> SalmonResult:
        """SalmonResult の 3way マージ。"""
        merged = current

        # 各フィールドを個別にマージ
        if "hazard" not in manual_fields:
            if (
                auto_update.hazard != base.hazard
                and current.hazard == base.hazard
            ):
                merged = replace(merged, hazard=auto_update.hazard)

        if "stage" not in manual_fields:
            if auto_update.stage != base.stage and current.stage == base.stage:
                merged = replace(merged, stage=auto_update.stage)

        if "golden_egg" not in manual_fields:
            if (
                auto_update.golden_egg != base.golden_egg
                and current.golden_egg == base.golden_egg
            ):
                merged = replace(merged, golden_egg=auto_update.golden_egg)

        if "power_egg" not in manual_fields:
            if (
                auto_update.power_egg != base.power_egg
                and current.power_egg == base.power_egg
            ):
                merged = replace(merged, power_egg=auto_update.power_egg)

        if "rescue" not in manual_fields:
            if (
                auto_update.rescue != base.rescue
                and current.rescue == base.rescue
            ):
                merged = replace(merged, rescue=auto_update.rescue)

        if "rescued" not in manual_fields:
            if (
                auto_update.rescued != base.rescued
                and current.rescued == base.rescued
            ):
                merged = replace(merged, rescued=auto_update.rescued)

        return merged

    # ----------------------------------------------------------------
    # プライベートメソッド：手動編集の上書き
    # ----------------------------------------------------------------

    def _apply_manual_result_overrides(
        self,
        current: BattleResult | SalmonResult | None,
        updated: BattleResult | SalmonResult | None,
        manual_fields: frozenset[str],
    ) -> BattleResult | SalmonResult | None:
        """Result フィールドの手動編集を上書きする。"""
        if current is None:
            return updated
        if updated is None:
            # Result 関連のフィールドが手動編集されていれば保持
            if manual_fields.intersection(
                RecordingMetadata.BATTLE_FIELDS
                | RecordingMetadata.SALMON_FIELDS
            ):
                return current
            return updated

        # 型が異なる場合は更新を優先
        if not isinstance(updated, type(current)):
            return updated

        # 同じ型の Result を上書き
        if isinstance(current, BattleResult) and isinstance(
            updated, BattleResult
        ):
            return self._apply_manual_battle_overrides(
                current, updated, manual_fields
            )

        if isinstance(current, SalmonResult) and isinstance(
            updated, SalmonResult
        ):
            return self._apply_manual_salmon_overrides(
                current, updated, manual_fields
            )

        return updated

    def _apply_manual_battle_overrides(
        self,
        current: BattleResult,
        updated: BattleResult,
        manual_fields: frozenset[str],
    ) -> BattleResult:
        """BattleResult の手動編集を上書きする。"""
        merged = updated

        if "match" in manual_fields:
            merged = replace(merged, match=current.match)
        if "rule" in manual_fields:
            merged = replace(merged, rule=current.rule)
        if "stage" in manual_fields:
            merged = replace(merged, stage=current.stage)
        if "kill" in manual_fields:
            merged = replace(merged, kill=current.kill)
        if "death" in manual_fields:
            merged = replace(merged, death=current.death)
        if "special" in manual_fields:
            merged = replace(merged, special=current.special)

        return merged

    def _apply_manual_salmon_overrides(
        self,
        current: SalmonResult,
        updated: SalmonResult,
        manual_fields: frozenset[str],
    ) -> SalmonResult:
        """SalmonResult の手動編集を上書きする。"""
        merged = updated

        if "hazard" in manual_fields:
            merged = replace(merged, hazard=current.hazard)
        if "stage" in manual_fields:
            merged = replace(merged, stage=current.stage)
        if "golden_egg" in manual_fields:
            merged = replace(merged, golden_egg=current.golden_egg)
        if "power_egg" in manual_fields:
            merged = replace(merged, power_egg=current.power_egg)
        if "rescue" in manual_fields:
            merged = replace(merged, rescue=current.rescue)
        if "rescued" in manual_fields:
            merged = replace(merged, rescued=current.rescued)

        return merged

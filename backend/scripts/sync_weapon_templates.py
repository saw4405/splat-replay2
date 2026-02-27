#!/usr/bin/env python3
"""ブキテンプレート定義を assets 差分から同期する。"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

WEAPON_GROUP_ITEM_PATTERN = re.compile(
    r"^\s{4}-\s*(weapon_template_(\d{3}))\s*$"
)
WEAPON_DEF_KEY_PATTERN = re.compile(r"^\s{2}(weapon_template_(\d{3})):\s*$")
TEMPLATE_PATH_PATTERN = re.compile(
    r'^\s{4}template_path:\s*"assets/matching/weapon/(.+)\.png"\s*$'
)
TOP_LEVEL_KEY_PATTERN = re.compile(r"^[^\s#][^:]*:\s*(?:#.*)?$")
WEAPON_CSV_NAME_FIELD = "武器名"


class SyncError(RuntimeError):
    """同期処理で期待外の状態を検出した場合の例外。"""


@dataclass(frozen=True)
class SectionRange:
    start: int
    end: int


@dataclass(frozen=True)
class ExistingDefinition:
    key: str
    weapon_name: str


@dataclass(frozen=True)
class PlannedAddition:
    key: str
    weapon_name: str


@dataclass(frozen=True)
class CsvWeaponRow:
    weapon_name: str


def _read_text_preserve_newline(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    return text, newline


def _find_top_level_section(
    lines: list[str], section_name: str
) -> SectionRange:
    needle = f"{section_name}:"
    section_start: int | None = None
    for idx, line in enumerate(lines):
        if line.rstrip("\r\n") == needle:
            section_start = idx
            break

    if section_start is None:
        raise SyncError(f"必須セクションが見つかりません: {section_name}")

    section_end = len(lines)
    for idx in range(section_start + 1, len(lines)):
        raw = lines[idx].rstrip("\r\n")
        if TOP_LEVEL_KEY_PATTERN.match(raw):
            section_end = idx
            break

    return SectionRange(start=section_start, end=section_end)


def _find_weapon_templates_group_block(
    lines: list[str], matcher_groups_section: SectionRange
) -> tuple[int, int, list[str]]:
    group_header_index: int | None = None
    for idx in range(
        matcher_groups_section.start + 1, matcher_groups_section.end
    ):
        if lines[idx].rstrip("\r\n") == "  weapon_templates:":
            group_header_index = idx
            break

    if group_header_index is None:
        raise SyncError("matcher_groups.weapon_templates が見つかりません。")

    block_end = group_header_index + 1
    while block_end < matcher_groups_section.end and lines[
        block_end
    ].startswith("    "):
        block_end += 1

    keys: list[str] = []
    for idx in range(group_header_index + 1, block_end):
        match = WEAPON_GROUP_ITEM_PATTERN.match(lines[idx].rstrip("\r\n"))
        if match is None:
            if lines[idx].strip() == "" or lines[idx].lstrip().startswith("#"):
                continue
            raise SyncError(
                "matcher_groups.weapon_templates の書式が不正です。"
                f" line={idx + 1}"
            )
        keys.append(match.group(1))

    if not keys:
        raise SyncError("matcher_groups.weapon_templates が空です。")

    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise SyncError(
            "matcher_groups.weapon_templates に重複があります: "
            + ", ".join(duplicates)
        )

    return group_header_index, block_end, keys


def _extract_definition_block_end(
    lines: list[str], block_start: int, simple_matchers_end: int
) -> int:
    idx = block_start + 1
    while idx < simple_matchers_end:
        raw = lines[idx].rstrip("\r\n")
        if re.match(r"^\s{2}\S[^:]*:\s*$", raw):
            return idx
        idx += 1
    return simple_matchers_end


def _find_existing_weapon_definitions(
    lines: list[str], simple_matchers_section: SectionRange
) -> list[ExistingDefinition]:
    definitions: list[ExistingDefinition] = []
    seen_keys: set[str] = set()

    for idx in range(
        simple_matchers_section.start + 1, simple_matchers_section.end
    ):
        key_match = WEAPON_DEF_KEY_PATTERN.match(lines[idx].rstrip("\r\n"))
        if key_match is None:
            continue

        key = key_match.group(1)
        if key in seen_keys:
            raise SyncError(f"simple_matchers に重複キーがあります: {key}")
        seen_keys.add(key)

        block_end = _extract_definition_block_end(
            lines,
            block_start=idx,
            simple_matchers_end=simple_matchers_section.end,
        )
        weapon_name: str | None = None
        for inner_idx in range(idx + 1, block_end):
            template_match = TEMPLATE_PATH_PATTERN.match(
                lines[inner_idx].rstrip("\r\n")
            )
            if template_match is not None:
                weapon_name = template_match.group(1)
                break

        if weapon_name is None:
            raise SyncError(
                f"{key} から template_path を抽出できません。"
                " expected=assets/matching/weapon/<name>.png"
            )

        definitions.append(
            ExistingDefinition(key=key, weapon_name=weapon_name)
        )

    if not definitions:
        raise SyncError(
            "simple_matchers 内に weapon_template_xxx 定義がありません。"
        )

    return definitions


def _collect_assets(assets_dir: Path) -> list[str]:
    if not assets_dir.is_dir():
        raise SyncError(f"assets ディレクトリが見つかりません: {assets_dir}")

    weapon_names: list[str] = []
    for png_path in sorted(assets_dir.glob("*.png")):
        stem = png_path.stem
        if stem.endswith("_mask"):
            continue
        weapon_names.append(stem)

    if not weapon_names:
        raise SyncError(f"ブキ画像が見つかりません: {assets_dir}")

    missing_masks = [
        name
        for name in weapon_names
        if not (assets_dir / f"{name}_mask.png").exists()
    ]
    if missing_masks:
        raise SyncError(
            "mask が不足しています: "
            + ", ".join(sorted(missing_masks))
            + " (expected: <name>_mask.png)"
        )

    return weapon_names


def _load_csv_weapons(csv_path: Path) -> list[CsvWeaponRow]:
    if not csv_path.is_file():
        raise SyncError(f"CSV ファイルが見つかりません: {csv_path}")

    with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise SyncError(f"CSV ヘッダーが見つかりません: {csv_path}")
        if WEAPON_CSV_NAME_FIELD not in reader.fieldnames:
            raise SyncError(
                f"CSV に必須列がありません: {WEAPON_CSV_NAME_FIELD}"
            )

        rows: list[CsvWeaponRow] = []
        seen_weapon_names: set[str] = set()
        for row in reader:
            raw_weapon_name = row.get(WEAPON_CSV_NAME_FIELD, "")
            weapon_name = raw_weapon_name.strip()
            if not weapon_name or weapon_name in seen_weapon_names:
                continue
            seen_weapon_names.add(weapon_name)
            rows.append(CsvWeaponRow(weapon_name=weapon_name))

    if not rows:
        raise SyncError(
            "CSV からブキ名を抽出できませんでした。"
            f" file={csv_path}, column={WEAPON_CSV_NAME_FIELD}"
        )
    return rows


def _normalize_weapon_name_for_compare(weapon_name: str) -> str:
    return weapon_name.replace("/", "")


def _find_uncovered_csv_weapons(
    csv_rows: list[CsvWeaponRow],
    reflected_weapon_names: list[str],
) -> list[str]:
    reflected_normalized = {
        _normalize_weapon_name_for_compare(name)
        for name in reflected_weapon_names
    }
    uncovered_weapon_names: list[str] = []
    for row in csv_rows:
        normalized_name = _normalize_weapon_name_for_compare(row.weapon_name)
        if normalized_name not in reflected_normalized:
            uncovered_weapon_names.append(row.weapon_name)
    return uncovered_weapon_names


def _print_uncovered_csv_weapons(
    csv_path: Path, uncovered_weapon_names: list[str]
) -> None:
    print(
        "未反映ブキ件数: "
        f"{len(uncovered_weapon_names)} (source={csv_path.name})"
    )
    if not uncovered_weapon_names:
        print("未反映ブキ一覧: なし")
        return

    print("未反映ブキ一覧:")
    for weapon_name in uncovered_weapon_names:
        print(f"- {weapon_name}")


def _validate_key_sets(
    group_keys: list[str], definitions: list[ExistingDefinition]
) -> None:
    group_set = set(group_keys)
    definition_set = {item.key for item in definitions}
    if group_set != definition_set:
        missing_in_group = sorted(definition_set - group_set)
        missing_in_def = sorted(group_set - definition_set)
        raise SyncError(
            "weapon_templates のキー集合が一致しません。"
            f" missing_in_group={missing_in_group}, missing_in_def={missing_in_def}"
        )


def _extract_config_weapon_names(
    config_text: str,
) -> tuple[list[ExistingDefinition], int]:
    lines = config_text.splitlines(keepends=True)
    matcher_groups_section = _find_top_level_section(lines, "matcher_groups")
    simple_matchers_section = _find_top_level_section(lines, "simple_matchers")
    _group_header_index, _group_insert_index, group_keys = (
        _find_weapon_templates_group_block(lines, matcher_groups_section)
    )
    definitions = _find_existing_weapon_definitions(
        lines, simple_matchers_section
    )
    _validate_key_sets(group_keys, definitions)
    return definitions, simple_matchers_section.end


def _validate_name_consistency(
    *, asset_weapons: list[str], config_weapon_names: list[str]
) -> list[str]:
    asset_set = set(asset_weapons)
    config_set = set(config_weapon_names)

    if len(asset_set) != len(asset_weapons):
        raise SyncError("assets 側でブキ名が重複しています。")

    if len(config_set) != len(config_weapon_names):
        counts: dict[str, int] = {}
        for name in config_weapon_names:
            counts[name] = counts.get(name, 0) + 1
        duplicates = sorted(
            name for name, count in counts.items() if count > 1
        )
        raise SyncError(
            "設定側で同一ブキ名が重複しています: " + ", ".join(duplicates)
        )

    missing_in_config = sorted(asset_set - config_set)
    missing_in_assets = sorted(config_set - asset_set)
    if missing_in_assets:
        raise SyncError(
            "設定に存在するが画像がないブキがあります: "
            + ", ".join(missing_in_assets)
        )

    return missing_in_config


def _build_plan(
    *,
    weapon_assets: list[str],
    definitions: list[ExistingDefinition],
) -> list[PlannedAddition]:
    config_names = [definition.weapon_name for definition in definitions]
    missing_names = _validate_name_consistency(
        asset_weapons=weapon_assets,
        config_weapon_names=config_names,
    )
    if not missing_names:
        return []

    max_id = max(
        int(definition.key.rsplit("_", 1)[1]) for definition in definitions
    )
    planned: list[PlannedAddition] = []
    next_id = max_id + 1
    for weapon_name in missing_names:
        planned.append(
            PlannedAddition(
                key=f"weapon_template_{next_id:03d}",
                weapon_name=weapon_name,
            )
        )
        next_id += 1
    return planned


def _build_definition_block_lines(
    additions: list[PlannedAddition], threshold: float, newline: str
) -> list[str]:
    lines: list[str] = []
    for item in additions:
        lines.extend(
            [
                f"  {item.key}:{newline}",
                f'    name: "{item.weapon_name}"{newline}',
                f'    type: "template"{newline}',
                f'    template_path: "assets/matching/weapon/{item.weapon_name}.png"{newline}',
                f'    mask_path: "assets/matching/weapon/{item.weapon_name}_mask.png"{newline}',
                f"    threshold: {threshold:g}{newline}",
                f'    description: "ブキ照合テンプレート"{newline}',
                newline,
            ]
        )
    return lines


def _apply_additions(
    *,
    original_text: str,
    newline: str,
    group_insert_index: int,
    simple_insert_index: int,
    additions: list[PlannedAddition],
    threshold: float,
) -> str:
    lines = original_text.splitlines(keepends=True)

    group_lines = [f"    - {item.key}{newline}" for item in additions]
    lines[group_insert_index:group_insert_index] = group_lines

    if simple_insert_index >= group_insert_index:
        simple_insert_index += len(group_lines)

    definition_lines = _build_definition_block_lines(
        additions, threshold, newline
    )
    if (
        simple_insert_index > 0
        and lines[simple_insert_index - 1].strip() != ""
    ):
        definition_lines.insert(0, newline)
    lines[simple_insert_index:simple_insert_index] = definition_lines

    return "".join(lines)


def _validate_yaml_load(config_path: Path, repo_root: Path) -> None:
    backend_src = repo_root / "backend" / "src"
    if not backend_src.is_dir():
        raise SyncError(f"backend/src が見つかりません: {backend_src}")

    sys.path.insert(0, str(backend_src))
    try:
        from splat_replay.domain.config import ImageMatchingSettings  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise SyncError(
            "YAML ロード検証に必要な依存を import できませんでした。"
            f" dependency_error={exc}"
        ) from exc

    try:
        ImageMatchingSettings.load_from_yaml(config_path)
    except ModuleNotFoundError as exc:
        raise SyncError(
            f"PyYAML などの依存不足の可能性があります。 dependency_error={exc}"
        ) from exc
    except Exception as exc:  # pragma: no cover - 具体エラーは実行時に報告
        raise SyncError(f"YAML ロード検証に失敗しました: {exc}") from exc


def run_sync(
    config_path: Path,
    assets_dir: Path,
    csv_path: Path,
    threshold: float,
    dry_run: bool,
) -> int:
    if threshold <= 0:
        raise SyncError(f"threshold は正の値を指定してください: {threshold}")

    original_text, newline = _read_text_preserve_newline(config_path)
    lines = original_text.splitlines(keepends=True)
    matcher_groups_section = _find_top_level_section(lines, "matcher_groups")
    _group_header_index, group_insert_index, _group_keys = (
        _find_weapon_templates_group_block(lines, matcher_groups_section)
    )
    definitions, simple_insert_index = _extract_config_weapon_names(
        original_text
    )

    asset_weapons = _collect_assets(assets_dir)
    additions = _build_plan(
        weapon_assets=asset_weapons, definitions=definitions
    )
    csv_rows = _load_csv_weapons(csv_path)
    reflected_weapon_names = [
        definition.weapon_name for definition in definitions
    ] + [addition.weapon_name for addition in additions]
    uncovered_csv_weapons = _find_uncovered_csv_weapons(
        csv_rows=csv_rows,
        reflected_weapon_names=reflected_weapon_names,
    )
    config_count = len(definitions)
    asset_count = len(asset_weapons)
    print(
        "件数: "
        f"csv={len(csv_rows)}, assets={asset_count}, config={config_count}"
    )

    if not additions:
        print("件数一致: assets と config のブキ数は一致しています。")
        print("変更なし: 追加すべきブキ定義はありません。")
        _print_uncovered_csv_weapons(
            csv_path=csv_path,
            uncovered_weapon_names=uncovered_csv_weapons,
        )
        return 0

    print("追加予定ブキ:")
    for item in additions:
        print(f"- {item.key}: {item.weapon_name}")
    print(
        f"同期後想定件数: assets={asset_count}, config={config_count + len(additions)}"
    )

    if dry_run:
        print("dry-run: image_matching.yaml は更新しません。")
        _print_uncovered_csv_weapons(
            csv_path=csv_path,
            uncovered_weapon_names=uncovered_csv_weapons,
        )
        return 0

    updated_text = _apply_additions(
        original_text=original_text,
        newline=newline,
        group_insert_index=group_insert_index,
        simple_insert_index=simple_insert_index,
        additions=additions,
        threshold=threshold,
    )

    config_path.write_text(updated_text, encoding="utf-8", newline="")
    try:
        updated_definitions, _updated_simple_insert_index = (
            _extract_config_weapon_names(updated_text)
        )
        _validate_name_consistency(
            asset_weapons=asset_weapons,
            config_weapon_names=[
                definition.weapon_name for definition in updated_definitions
            ],
        )
        _validate_yaml_load(config_path=config_path, repo_root=Path.cwd())
    except Exception:
        config_path.write_text(original_text, encoding="utf-8", newline="")
        raise

    print("件数一致: assets と config のブキ数は一致しています。")
    print(f"更新完了: {config_path}")
    _print_uncovered_csv_weapons(
        csv_path=csv_path,
        uncovered_weapon_names=uncovered_csv_weapons,
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "backend/assets/matching/weapon と "
            "backend/config/image_matching.yaml のブキテンプレート定義を同期する。"
        )
    )
    parser.add_argument(
        "--config",
        default="backend/config/image_matching.yaml",
        help="image_matching.yaml のパス",
    )
    parser.add_argument(
        "--assets-dir",
        default="backend/assets/matching/weapon",
        help="ブキテンプレート assets ディレクトリのパス",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="追加する weapon_template_xxx の threshold",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="差分のみ表示してファイル更新しない",
    )
    parser.add_argument(
        "--weapon-csv",
        default="splatoon3_weapons_gamewith.csv",
        help="未反映ブキ確認に利用する CSV のパス",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    assets_dir = Path(args.assets_dir)
    csv_path = Path(args.weapon_csv)

    if not config_path.is_file():
        raise SyncError(f"config ファイルが見つかりません: {config_path}")

    return run_sync(
        config_path=config_path,
        assets_dir=assets_dir,
        csv_path=csv_path,
        threshold=args.threshold,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SyncError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)

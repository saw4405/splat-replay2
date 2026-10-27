"""素材の保存・検証・生成中の参照保護。アップロード素材はuploads配下に分離する。"""

from collections import Counter
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import threading
import tempfile
from typing import Iterator
from uuid import uuid4

from PIL import Image, ImageFont, ImageOps
import structlog

from splat_replay.application.interfaces.thumbnail_design import (
    ThumbnailAssetInfo,
)
from splat_replay.domain.config.video_edit import ThumbnailDesign
from splat_replay.domain.models import (
    BattleResult,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
    VideoAsset,
    XP,
)
from splat_replay.infrastructure.config import load_settings_from_toml
from splat_replay.infrastructure.filesystem import paths


class ThumbnailAssets:
    def __init__(
        self, root: Path | None = None, settings_path: Path | None = None
    ) -> None:
        self.root = root or paths.THUMBNAIL_ASSETS_DIR
        self.settings_path = settings_path or paths.SETTINGS_FILE
        self._lock = threading.RLock()
        self._using: Counter[str] = Counter()
        self._logger = structlog.get_logger(__name__)
        candidates = {
            "system-font/japanese": Path(
                "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
            ),
            "system-font/sans": Path("/System/Library/Fonts/Helvetica.ttc"),
            "system-font/windows-japanese": Path(
                "C:/Windows/Fonts/meiryo.ttc"
            ),
            "system-font/linux-japanese": Path(
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
            ),
        }
        self._fonts = {
            key: path for key, path in candidates.items() if path.is_file()
        }

    @contextmanager
    def guard(self) -> Iterator[None]:
        with self._lock:
            yield

    def default_design(self) -> ThumbnailDesign:
        # 同梱側を正本とし、利用者領域の古いコピーより優先する。
        bundled = paths.ASSETS_DIR / "thumbnail" / "design.default.json"
        return ThumbnailDesign.parse_raw(bundled.read_bytes())

    def current_design(self) -> ThumbnailDesign:
        if not self.settings_path.exists():
            return self.default_design()
        return (
            load_settings_from_toml(
                self.settings_path
            ).video_edit.thumbnail_design
            or self.default_design()
        )

    @contextmanager
    def lease(
        self, design: ThumbnailDesign | None = None
    ) -> Iterator[ThumbnailDesign]:
        with self._lock:
            snapshot = (design or self.current_design()).copy(deep=True)
            self.validate_references(snapshot)
            refs = snapshot.asset_ids()
            self._using.update(refs)
        try:
            yield snapshot
        finally:
            with self._lock:
                self._using.subtract(refs)

    def path(self, asset_id: str) -> Path:
        # デザインから参照するIDと直接取得APIの両方をここで検証する。
        if asset_id in self._fonts:
            return self._fonts[asset_id]
        if (
            not asset_id
            or "\\" in asset_id
            or ":" in asset_id
            or any(p in ("", ".", "..") for p in asset_id.split("/"))
        ):
            raise ValueError("素材IDが不正です")
        target = (self.root / asset_id).resolve()
        if not target.is_relative_to(self.root.resolve()):
            raise ValueError("素材IDが不正です")
        if not target.exists() and not asset_id.startswith("uploads/"):
            bundled = paths.ASSETS_DIR / "thumbnail" / asset_id
            if bundled.is_file():
                return bundled
        return target

    def validate_references(self, design: ThumbnailDesign) -> None:
        for asset_id in design.asset_ids():
            target = self.path(asset_id)
            if asset_id == "thumbnail_overlay.png" and not target.exists():
                continue
            if not target.is_file():
                raise ValueError(f"素材が見つかりません: {asset_id}")
            if asset_id in self._fonts or asset_id.lower().endswith(
                (".ttf", ".otf")
            ):
                continue
            with Image.open(target) as image:
                image.verify()
        if design.background.source == "image" and not design.background.asset:
            raise ValueError("背景画像を選択してください")
        for e in design.elements:
            if e.source == "image" and not e.asset:
                raise ValueError(f"画像を選択してください: {e.name}")
            if e.source in ("text", "win_lose", "rate"):
                if e.font not in self._fonts and not e.font.lower().endswith(
                    (".ttf", ".otf")
                ):
                    raise ValueError("フォント素材を選択してください")
                ImageFont.truetype(str(self.path(e.font)), e.font_size)
            if (
                e.source in ("image", "overlay")
                and e.asset
                and not e.asset.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".webp")
                )
            ):
                raise ValueError("画像素材を選択してください")
        if (
            design.background.asset
            and not design.background.asset.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp")
            )
        ):
            raise ValueError("背景には画像素材を選択してください")

    def catalog(self) -> list[ThumbnailAssetInfo]:
        entries: dict[str, ThumbnailAssetInfo] = {}
        for root in (paths.ASSETS_DIR / "thumbnail", self.root):
            for p in sorted(root.rglob("*")):
                if not p.is_file() or p.suffix.lower() not in (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                    ".otf",
                    ".ttf",
                ):
                    continue
                key = p.relative_to(root).as_posix()
                if key.startswith("samples/"):
                    continue
                entries[key] = ThumbnailAssetInfo(
                    id=key,
                    name=p.stem,
                    kind="font"
                    if p.suffix.lower() in (".otf", ".ttf")
                    else "image",
                    protected=not key.startswith("uploads/"),
                )
        for key, p in self._fonts.items():
            entries[key] = ThumbnailAssetInfo(
                id=key, name=p.stem, kind="font", protected=True
            )
        return list(entries.values())

    def upload(self, content: bytes) -> str:
        if len(content) > 20 * 1024 * 1024:
            raise ValueError("画像は20MB以下にしてください")
        try:
            image = Image.open(BytesIO(content))
        except Image.DecompressionBombError as exc:
            raise ValueError("画像は2000万画素以下にしてください") from exc
        with image:
            if image.width * image.height > 20_000_000 or image.format not in (
                "PNG",
                "JPEG",
                "WEBP",
            ):
                raise ValueError(
                    "PNG・JPEG・WebPの2000万画素以下の画像を選択してください"
                )
            image.load()
            asset_id = f"uploads/{uuid4().hex}.png"
            target = self.path(asset_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".tmp")
            try:
                oriented = ImageOps.exif_transpose(image, in_place=False)
                if oriented is None:
                    raise ValueError("画像の向きを読み取れませんでした")
                oriented.convert("RGBA").save(temporary, format="PNG")
                temporary.replace(target)
            finally:
                # カタログに未完了の画像を出さず、失敗時も一時ファイルを残さない。
                temporary.unlink(missing_ok=True)
        self._logger.info("サムネイル素材を追加しました", asset_id=asset_id)
        return asset_id

    def delete(self, asset_id: str, draft: ThumbnailDesign) -> None:
        with self._lock:
            target = self.path(asset_id)
            if not asset_id.startswith("uploads/"):
                raise ValueError("同梱素材は削除できません")
            if (
                asset_id in self.current_design().asset_ids()
                or asset_id in draft.asset_ids()
                or self._using[asset_id] > 0
            ):
                raise ValueError(
                    "使用中の画像です。デザインから外して保存してから削除してください"
                )
            target.unlink()
            self._logger.info(
                "サムネイル素材を削除しました", asset_id=asset_id
            )

    def read(self, path: Path) -> bytes:
        return path.read_bytes()

    @contextmanager
    def sample(self, scenario: str) -> Iterator[list[VideoAsset]]:
        """名前を伏せた実リザルトと確認用の集計値。生成結果は終了時に撤去する。"""
        if scenario not in ("x", "event", "regular", "anarchy", "single"):
            raise ValueError("サンプル種別が不正です")
        with tempfile.TemporaryDirectory(prefix="splat-thumbnail-") as temp:
            root = Path(temp)
            match = {
                "event": Match.CHALLENGE,
                "regular": Match.REGULAR,
                "anarchy": Match.ANARCHY,
            }.get(scenario, Match.X)
            sources = (
                ("result-1.png", 17, 7, Stage.FLOUNDER_HEIGHTS),
                ("result-2.png", 16, 7, Stage.BARNACLE_AND_DIME),
                ("result-3.png", 17, 9, None),
            )
            assets: list[VideoAsset] = []
            for i in range(1 if scenario == "single" else 7):
                filename, kill, death, stage = sources[i % len(sources)]
                assets.append(
                    VideoAsset(
                        video=root / f"sample-{i}.mp4",
                        thumbnail=paths.ASSETS_DIR
                        / "thumbnail"
                        / "samples"
                        / filename,
                        metadata=RecordingMetadata(
                            judgement=Judgement.WIN
                            if i < 4
                            else Judgement.LOSE,
                            rate=None
                            if scenario == "regular"
                            else XP(2000.0 + i * 10.1),
                            result=BattleResult(
                                match=match,
                                rule=Rule.RAINMAKER,
                                stage=stage,
                                kill=kill,
                                death=death,
                                special=4,
                            ),
                        ),
                    )
                )
            yield assets

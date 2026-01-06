"""アセット管理関連のDTO定義。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


EditUploadState = Literal["idle", "running", "succeeded", "failed"]


@dataclass(frozen=True)
class RecordedVideoDTO:
    """録画済みビデオの情報を表すDTO。

    Attributes:
        video_id: ビデオID（base_dirからの相対パス、例: recorded/xxx.mp4）
        path: 動画ファイルの絶対パス（文字列）
        filename: ファイル名
        started_at: 録画開始時刻（ISO形式）
        game_mode: ゲームモード
        match: マッチ種別
        rule: ルール
        stage: ステージ
        rate: レート
        judgement: 勝敗
        kill: キル数
        death: デス数
        special: スペシャル数
        hazard: 危険度（サーモンラン）
        golden_egg: 金イクラ数
        power_egg: イクラ数
        rescue: 救助数
        rescued: 救助された数
        has_subtitle: 字幕の有無
        has_thumbnail: サムネイルの有無
        duration_seconds: 動画の長さ（秒）
        size_bytes: ファイルサイズ（バイト）
    """

    video_id: str
    path: str
    filename: str
    started_at: str | None
    game_mode: str | None
    match: str | None
    rule: str | None
    stage: str | None
    rate: str | None
    judgement: str | None
    kill: int | None
    death: int | None
    special: int | None
    hazard: int | None
    golden_egg: int | None
    power_egg: int | None
    rescue: int | None
    rescued: int | None
    has_subtitle: bool
    has_thumbnail: bool
    duration_seconds: float | None
    size_bytes: int | None


@dataclass(frozen=True)
class EditedVideoDTO:
    """編集済みビデオの情報を表すDTO。

    Attributes:
        video_id: ビデオID（base_dirからの相対パス、例: edited/xxx.mkv）
        path: 動画ファイルの絶対パス（文字列）
        filename: ファイル名
        duration_seconds: 動画の長さ（秒）
        has_subtitle: 字幕の有無
        has_thumbnail: サムネイルの有無
        metadata: メタデータ辞書
        updated_at: 更新日時（ISO形式）
        size_bytes: ファイルサイズ（バイト）
        title: タイトル
        description: 説明
    """

    video_id: str
    path: str
    filename: str
    duration_seconds: float | None
    has_subtitle: bool
    has_thumbnail: bool
    metadata: dict[str, str | None] | None
    updated_at: str | None
    size_bytes: int | None
    title: str | None
    description: str | None


@dataclass(frozen=True)
class EditUploadStatusDTO:
    """編集・アップロード処理の状態を表すDTO。

    Attributes:
        state: 状態（idle/running/succeeded/failed）
        message: 状態メッセージ
        progress: 進捗率（0-100）
    """

    state: EditUploadState
    message: str
    progress: int

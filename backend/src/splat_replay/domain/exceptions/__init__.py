"""ドメイン例外の定義。

このモジュールは、アプリケーション全体で使用されるドメイン例外を提供します。
各例外は error_code を持ち、ログやエラーハンドリングで統一的に扱えます。

Usage:
    from splat_replay.domain.exceptions import ValidationError, ResourceNotFoundError

    # バリデーションエラー
    raise ValidationError(
        "無効なウデマエ形式です",
        error_code="INVALID_UDEMAE_FORMAT",
    )

    # リソース未検出
    raise ResourceNotFoundError(
        "動画ファイルが見つかりません",
        error_code="VIDEO_FILE_NOT_FOUND",
    )
"""

from __future__ import annotations

__all__ = [
    "DomainError",
    "ValidationError",
    "RuleViolationError",
    "ResourceNotFoundError",
    "ResourceConflictError",
    "RecordingError",
    "PhaseTransitionError",
    "DeviceError",
    "AuthenticationError",
    "ConfigurationError",
]


class DomainError(Exception):
    """ドメインエラー基底クラス。

    すべてのドメイン例外はこのクラスを継承します。
    error_code により、エラーの種類を一意に識別できます。

    Attributes:
        error_code: エラーコード（例: "INVALID_UDEMAE_FORMAT"）
        cause: 原因となった例外（オプション）
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        """ドメインエラーを初期化する。

        Args:
            message: エラーメッセージ
            error_code: エラーコード（大文字スネークケース推奨）
            cause: 原因となった例外（オプション）
        """
        super().__init__(message)
        self.error_code = error_code
        self.cause = cause


# ================================================================
# バリデーション系
# ================================================================


class ValidationError(DomainError):
    """バリデーションエラー。

    入力値の形式が不正、必須項目が不足、制約条件を満たさないなど、
    バリデーションに失敗した場合に使用します。

    Examples:
        >>> raise ValidationError(
        ...     "無効なウデマエ形式です: ABC",
        ...     error_code="INVALID_UDEMAE_FORMAT",
        ... )
    """


class RuleViolationError(DomainError):
    """ビジネスルール違反。

    ドメイン固有のビジネスルールに違反した場合に使用します。
    単純なバリデーションではなく、より複雑な制約条件の違反を表現します。

    Examples:
        >>> raise RuleViolationError(
        ...     "録画中は設定を変更できません",
        ...     error_code="RECORDING_IN_PROGRESS",
        ... )
    """


# ================================================================
# リソース系
# ================================================================


class ResourceNotFoundError(DomainError):
    """リソースが見つからない。

    ファイル、データベースレコード、外部APIのリソースなどが
    見つからない場合に使用します。

    Examples:
        >>> raise ResourceNotFoundError(
        ...     "動画ファイルが見つかりません: /path/to/video.mp4",
        ...     error_code="VIDEO_FILE_NOT_FOUND",
        ... )
    """


class ResourceConflictError(DomainError):
    """リソース競合。

    リソースが既に使用中、ロック中、または競合状態にある場合に使用します。

    Examples:
        >>> raise ResourceConflictError(
        ...     "録画デバイスは既に使用中です",
        ...     error_code="DEVICE_IN_USE",
        ... )
    """


# ================================================================
# 録画ドメイン固有
# ================================================================


class RecordingError(DomainError):
    """録画関連エラー。

    録画プロセスに関連する汎用的なエラー。
    より具体的なエラー（PhaseTransitionError など）の基底クラスとしても使用します。

    Examples:
        >>> raise RecordingError(
        ...     "録画開始に失敗しました",
        ...     error_code="RECORDING_START_FAILED",
        ... )
    """


class PhaseTransitionError(RecordingError):
    """フェーズ遷移エラー。

    録画フェーズの遷移が不正な場合に使用します。
    例: Standby → InGame への直接遷移（Matching を経由していない）

    Examples:
        >>> raise PhaseTransitionError(
        ...     "無効なフェーズ遷移: Standby → InGame",
        ...     error_code="INVALID_PHASE_TRANSITION",
        ... )
    """


class DeviceError(DomainError):
    """デバイスエラー。

    キャプチャデバイス、録画デバイスなどのハードウェア関連エラー。

    Examples:
        >>> raise DeviceError(
        ...     "キャプチャデバイスが接続されていません",
        ...     error_code="CAPTURE_DEVICE_NOT_FOUND",
        ... )
    """


# ================================================================
# 認証・設定系
# ================================================================


class AuthenticationError(DomainError):
    """認証エラー。

    ユーザー認証、API認証、トークンの有効期限切れなど、
    認証に失敗した場合に使用します。

    Examples:
        >>> raise AuthenticationError(
        ...     "YouTube 認証に失敗しました",
        ...     error_code="AUTH_YOUTUBE_REFRESH",
        ... )
    """


class ConfigurationError(DomainError):
    """設定エラー。

    設定ファイルの不備、必須設定の欠如、設定値の矛盾など、
    設定に関するエラー。

    Examples:
        >>> raise ConfigurationError(
        ...     "client_secrets.json が見つかりません",
        ...     error_code="CLIENT_SECRETS_NOT_FOUND",
        ... )
    """

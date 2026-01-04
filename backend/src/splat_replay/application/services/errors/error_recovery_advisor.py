"""エラー回復アクション提案サービス。"""

from __future__ import annotations

from splat_replay.application.services.setup.setup_errors import (
    FileOperationError,
    NetworkError,
    SetupError,
    SetupStateError,
    SystemCheckError,
    UserCancelledError,
)
from splat_replay.domain.exceptions import (
    AuthenticationError,
    ConfigurationError,
    DeviceError,
    DomainError,
    RecordingError,
    ResourceConflictError,
    ResourceNotFoundError,
    RuleViolationError,
    ValidationError,
)


class ErrorRecoveryAdvisor:
    """エラーに対する回復アクションを提案するサービス。

    責務:
    - エラータイプ別の回復アクション提案
    - ユーザーフレンドリーなメッセージ生成
    - 回復可能性の判定
    """

    def suggest_recovery_action(self, error: SetupError) -> list[str]:
        """エラーに対する回復アクションを提案する。

        Args:
            error: セットアップエラー

        Returns:
            回復アクションのリスト
        """
        actions: list[str] = []

        # エラー固有の回復アクション
        if error.recovery_action:
            actions.append(error.recovery_action)

        # エラータイプ別の推奨アクション
        if isinstance(error, SystemCheckError):
            actions.extend(self._get_system_check_recovery_actions(error))
        elif isinstance(error, FileOperationError):
            actions.extend(self._get_file_operation_recovery_actions(error))
        elif isinstance(error, NetworkError):
            actions.extend(self._get_network_recovery_actions(error))
        elif isinstance(error, SetupStateError):
            actions.extend(
                self._get_installation_state_recovery_actions(error)
            )
        elif isinstance(error, UserCancelledError):
            actions.extend(["インストーラーを再起動してください"])

        # 共通の回復アクション
        if not actions:
            actions.append(
                "問題が解決しない場合は、サポートにお問い合わせください"
            )

        return actions

    def suggest_domain_error_recovery_action(
        self, error: DomainError
    ) -> list[str]:
        """ドメイン例外の回復アクションを取得する。

        Args:
            error: ドメイン例外

        Returns:
            回復アクションのリスト
        """
        if isinstance(error, ValidationError):
            return [
                "入力内容を確認してください",
                "必須フィールドが入力されているか確認してください",
            ]
        elif isinstance(error, ResourceNotFoundError):
            return [
                "指定されたリソースが存在するか確認してください",
                "パスやファイル名が正しいか確認してください",
            ]
        elif isinstance(error, AuthenticationError):
            return [
                "認証情報を確認してください",
                "アカウント設定を見直してください",
                "必要に応じて再認証を行ってください",
            ]
        elif isinstance(error, ConfigurationError):
            return [
                "設定ファイルを確認してください",
                "設定値が正しいか確認してください",
                "設定をデフォルトに戻すことを検討してください",
            ]
        elif isinstance(error, DeviceError):
            return [
                "デバイスが正しく接続されているか確認してください",
                "デバイスドライバーが正しくインストールされているか確認してください",
                "デバイスを再接続してみてください",
            ]
        elif isinstance(error, RecordingError):
            return [
                "録画設定を確認してください",
                "ディスク空き容量を確認してください",
                "録画ソフトウェアが正しく動作しているか確認してください",
            ]
        elif isinstance(error, (RuleViolationError, ResourceConflictError)):
            return [
                "操作が許可されているか確認してください",
                "別の操作が実行中でないか確認してください",
            ]
        else:
            return [
                "操作を再試行してください",
                "問題が解決しない場合は、サポートにお問い合わせください",
            ]

    def get_setup_error_user_message(self, error: SetupError) -> str:
        """ユーザーフレンドリーなエラーメッセージを取得する。

        Args:
            error: セットアップエラー

        Returns:
            ユーザー向けメッセージ
        """
        if isinstance(error, SystemCheckError):
            return f"{error.software_name} の確認中にエラーが発生しました"
        elif isinstance(error, FileOperationError):
            return "ファイル操作中にエラーが発生しました"
        elif isinstance(error, NetworkError):
            return "ネットワーク接続中にエラーが発生しました"
        elif isinstance(error, SetupStateError):
            return "インストール状態の管理中にエラーが発生しました"
        elif isinstance(error, UserCancelledError):
            return error.message
        else:
            return error.message

    def get_domain_error_user_message(self, error: DomainError) -> str:
        """ドメイン例外のユーザーフレンドリーメッセージを取得する。

        Args:
            error: ドメイン例外

        Returns:
            ユーザー向けメッセージ
        """
        if isinstance(error, ValidationError):
            return f"入力エラー: {error}"
        elif isinstance(error, ResourceNotFoundError):
            return f"リソースが見つかりません: {error}"
        elif isinstance(error, AuthenticationError):
            return f"認証エラー: {error}"
        elif isinstance(error, ConfigurationError):
            return f"設定エラー: {error}"
        elif isinstance(error, DeviceError):
            return f"デバイスエラー: {error}"
        elif isinstance(error, RecordingError):
            return f"録画エラー: {error}"
        elif isinstance(error, RuleViolationError):
            return f"操作エラー: {error}"
        elif isinstance(error, ResourceConflictError):
            return f"競合エラー: {error}"
        else:
            return f"エラーが発生しました: {error}"

    def is_domain_error_recoverable(self, error: DomainError) -> bool:
        """ドメイン例外が回復可能かどうかを判定する。

        Args:
            error: ドメイン例外

        Returns:
            回復可能な場合はTrue
        """
        # ほとんどのドメインエラーは回復可能（ユーザー操作で対処可能）
        # ValidationError、ResourceNotFound等は入力修正で回復可能
        return True

    def _get_system_check_recovery_actions(
        self,
        error: SystemCheckError,
    ) -> list[str]:
        """システムチェックエラーの回復アクションを取得する。

        Args:
            error: システムチェックエラー

        Returns:
            回復アクションのリスト
        """
        return [
            f"{error.software_name} がインストールされているか確認してください",
            "環境変数PATHが正しく設定されているか確認してください",
            "アプリケーションを管理者権限で実行してみてください",
        ]

    def _get_file_operation_recovery_actions(
        self,
        error: FileOperationError,
    ) -> list[str]:
        """ファイル操作エラーの回復アクションを取得する。

        Args:
            error: ファイル操作エラー

        Returns:
            回復アクションのリスト
        """
        return [
            f"ファイル '{error.file_path}' へのアクセス権限を確認してください",
            "ディスクの空き容量を確認してください",
            "ファイルが他のプログラムで使用されていないか確認してください",
        ]

    def _get_network_recovery_actions(
        self,
        error: NetworkError,
    ) -> list[str]:
        """ネットワークエラーの回復アクションを取得する。

        Args:
            error: ネットワークエラー

        Returns:
            回復アクションのリスト
        """
        actions = [
            "インターネット接続を確認してください",
            "ファイアウォール設定を確認してください",
        ]

        if error.url:
            actions.append(
                f"URL '{error.url}' にアクセスできるか確認してください"
            )

        return actions

    def _get_installation_state_recovery_actions(
        self,
        error: SetupStateError,
    ) -> list[str]:
        """インストール状態エラーの回復アクションを取得する。

        Args:
            error: インストール状態エラー

        Returns:
            回復アクションのリスト
        """
        return [
            "インストーラーを再起動してください",
            "設定ファイルが破損している可能性があります",
            "必要に応じてインストール状態をリセットしてください",
        ]

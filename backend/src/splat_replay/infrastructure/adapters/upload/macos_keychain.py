"""macOS Keychain に YouTube OAuth token を保存する。"""

from __future__ import annotations

from typing import Any

_SERVICE = "io.github.saw4405.splatreplay"
_ACCOUNT = "youtube-oauth"


class KeychainError(RuntimeError):
    """Keychain への保存または読み込みに失敗した。"""


def _security() -> Any:
    import Security

    return Security


def _query(security: Any) -> dict[str, Any]:
    return {
        security.kSecClass: security.kSecClassGenericPassword,
        security.kSecAttrService: _SERVICE,
        security.kSecAttrAccount: _ACCOUNT,
    }


def get_youtube_oauth_token() -> str | None:
    """保存済み token を返す。未登録なら None を返す。"""
    security = _security()
    query = _query(security)
    query.update(
        {
            security.kSecReturnData: True,
            security.kSecMatchLimit: security.kSecMatchLimitOne,
        }
    )
    try:
        status, data = security.SecItemCopyMatching(query, None)
    except Exception:
        raise KeychainError(
            "macOS Keychain から token を読み込めません"
        ) from None

    if status == security.errSecItemNotFound:
        return None
    if status != security.errSecSuccess:
        if status == security.errSecUserCanceled:
            raise KeychainError(
                "macOS Keychain の許可操作を完了できませんでした。"
                "録画中の場合は録画終了後にこのエラーを閉じてください。"
                "録画済みまたは編集済み動画が残っていることを確認して"
                "「処理開始」を再実行してください。macOS の許可画面が表示された場合は、"
                f"内容を確認して許可してください。(OSStatus {status})"
            )
        raise KeychainError(
            f"macOS Keychain の読み込みに失敗しました (OSStatus {status})"
        )
    try:
        return bytes(data).decode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise KeychainError(
            "macOS Keychain の token データを読み取れません"
        ) from None


def set_youtube_oauth_token(token: str) -> None:
    """token を Keychain に追加または更新する。"""
    security = _security()
    query = _query(security)
    attributes = {security.kSecValueData: token.encode("utf-8")}
    try:
        status = security.SecItemUpdate(query, attributes)
        if status == security.errSecItemNotFound:
            status, _ = security.SecItemAdd(query | attributes, None)
    except Exception:
        raise KeychainError(
            "macOS Keychain に token を保存できません"
        ) from None

    if status != security.errSecSuccess:
        raise KeychainError(
            f"macOS Keychain の保存に失敗しました (OSStatus {status})"
        )

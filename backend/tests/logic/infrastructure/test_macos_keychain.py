"""macOS Keychain adapter の logic テスト。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from splat_replay.infrastructure.adapters.upload import macos_keychain
from splat_replay.infrastructure.adapters.upload.macos_keychain import (
    KeychainError,
)


@pytest.fixture
def security_api():
    return SimpleNamespace(
        kSecClass="class",
        kSecClassGenericPassword="generic-password",
        kSecAttrService="service",
        kSecAttrAccount="account",
        kSecReturnData="return-data",
        kSecMatchLimit="match-limit",
        kSecMatchLimitOne="one",
        kSecValueData="value-data",
        errSecSuccess=0,
        errSecItemNotFound=-25300,
        errSecUserCanceled=-128,
        SecItemCopyMatching=Mock(),
        SecItemUpdate=Mock(),
        SecItemAdd=Mock(),
    )


def test_get_token_returns_keychain_data(monkeypatch, security_api):
    security_api.SecItemCopyMatching.return_value = (0, b"serialized-token")
    monkeypatch.setattr(macos_keychain, "_security", lambda: security_api)

    assert macos_keychain.get_youtube_oauth_token() == "serialized-token"


def test_get_missing_token_returns_none(monkeypatch, security_api):
    security_api.SecItemCopyMatching.return_value = (-25300, None)
    monkeypatch.setattr(macos_keychain, "_security", lambda: security_api)

    assert macos_keychain.get_youtube_oauth_token() is None


def test_get_keychain_error_is_not_missing(monkeypatch, security_api):
    security_api.SecItemCopyMatching.return_value = (-25293, None)
    monkeypatch.setattr(macos_keychain, "_security", lambda: security_api)

    with pytest.raises(KeychainError, match="-25293"):
        macos_keychain.get_youtube_oauth_token()


def test_get_user_canceled_error_includes_recovery_without_mutating_item(
    monkeypatch: pytest.MonkeyPatch, security_api: SimpleNamespace
) -> None:
    security_api.SecItemCopyMatching.return_value = (-128, None)
    monkeypatch.setattr(macos_keychain, "_security", lambda: security_api)

    with pytest.raises(KeychainError) as exc_info:
        macos_keychain.get_youtube_oauth_token()

    message = str(exc_info.value)
    assert "録画終了後" in message
    assert "録画済みまたは編集済み動画が残っていること" in message
    assert "「処理開始」を再実行" in message
    assert "許可画面が表示された場合" in message
    assert "OSStatus -128" in message
    security_api.SecItemUpdate.assert_not_called()
    security_api.SecItemAdd.assert_not_called()


def test_get_invalid_token_data_raises_generic_error(
    monkeypatch, security_api
):
    security_api.SecItemCopyMatching.return_value = (0, b"\xff")
    monkeypatch.setattr(macos_keychain, "_security", lambda: security_api)

    with pytest.raises(KeychainError, match="token データ"):
        macos_keychain.get_youtube_oauth_token()


def test_set_token_updates_existing_item(monkeypatch, security_api):
    security_api.SecItemUpdate.return_value = 0
    monkeypatch.setattr(macos_keychain, "_security", lambda: security_api)

    macos_keychain.set_youtube_oauth_token("serialized-token")

    security_api.SecItemUpdate.assert_called_once()
    attributes = security_api.SecItemUpdate.call_args.args[1]
    assert attributes["value-data"] == b"serialized-token"
    security_api.SecItemAdd.assert_not_called()


def test_set_token_adds_unregistered_item(monkeypatch, security_api):
    security_api.SecItemUpdate.return_value = -25300
    security_api.SecItemAdd.return_value = (0, None)
    monkeypatch.setattr(macos_keychain, "_security", lambda: security_api)

    macos_keychain.set_youtube_oauth_token("serialized-token")

    security_api.SecItemAdd.assert_called_once()
    attributes = security_api.SecItemAdd.call_args.args[0]
    assert attributes["value-data"] == b"serialized-token"


def test_set_keychain_error_does_not_expose_token(monkeypatch, security_api):
    security_api.SecItemUpdate.return_value = -25300
    security_api.SecItemAdd.return_value = (-25293, None)
    monkeypatch.setattr(macos_keychain, "_security", lambda: security_api)

    with pytest.raises(KeychainError) as exc_info:
        macos_keychain.set_youtube_oauth_token("serialized-token")

    assert "serialized-token" not in str(exc_info.value)

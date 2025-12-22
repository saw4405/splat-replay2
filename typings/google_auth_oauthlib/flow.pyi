"""google_auth_oauthlib.flow の型スタブ"""

from typing import Any

class InstalledAppFlow:
    """インストール済みアプリケーション用のOAuth2フロー"""

    @classmethod
    def from_client_secrets_file(
        cls,
        client_secrets_file: str,
        scopes: list[str],
        **kwargs: Any,
    ) -> InstalledAppFlow: ...
    def run_local_server(
        self,
        port: int = 8080,
        **kwargs: Any,
    ) -> Any: ...

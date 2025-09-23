from __future__ import annotations

from typing import Any, Sequence

class InstalledAppFlow:
    @classmethod
    def from_client_secrets_file(
        cls,
        client_secrets_file: str | bytes | bytearray,
        scopes: Sequence[str],
    ) -> "InstalledAppFlow": ...
    def run_local_server(self, *, port: int = ...) -> Any: ...

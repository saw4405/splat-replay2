from __future__ import annotations

class MediaFileUpload:
    def __init__(
        self,
        filename: str | bytes | bytearray | object,
        mimetype: str | None = ...,
        resumable: bool = ...,
    ) -> None: ...

from typing import IO, Any, Mapping, Sequence

def safe_load(
    stream: IO[bytes] | IO[str] | bytes | str,
) -> Mapping[str, Any] | Sequence[Any] | None: ...

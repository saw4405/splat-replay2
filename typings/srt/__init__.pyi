from __future__ import annotations

from datetime import timedelta
from typing import Iterable, Iterator

class Subtitle:
    index: int
    start: timedelta
    end: timedelta
    content: str

    def __init__(
        self,
        index: int,
        start: timedelta,
        end: timedelta,
        content: str,
        **kwargs: object,
    ) -> None: ...

def parse(data: str) -> Iterator[Subtitle]: ...
def compose(subtitles: Iterable[Subtitle]) -> str: ...

from __future__ import annotations

from typing import Any, Dict, List

class Request:
    def __init__(self, request_type: str, **payload: Any) -> None: ...

class Event:
    event_type: str
    event_data: Dict[str, Any]

    def __init__(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> None: ...

class Response1:
    res_data: Dict[str, Any]

    def __init__(self, res_data: Dict[str, Any]) -> None: ...

class Response2:
    results: List[Response1]

    def __init__(self, results: List[Response1]) -> None: ...

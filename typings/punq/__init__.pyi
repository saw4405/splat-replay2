from __future__ import annotations

from typing import Any, Callable, TypeVar

T = TypeVar("T")

class Container:
    def register(
        self,
        abstract: Any,
        concrete: Any | None = None,
        *,
        instance: Any | None = None,
        factory: Callable[..., Any] | None = None,
    ) -> None: ...
    def resolve(self, abstract: Any) -> Any: ...

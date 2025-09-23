from __future__ import annotations

from typing import Iterable

class _Device:
    Name: object

class _WMI:
    def InstancesOf(self, name: str) -> Iterable[_Device]: ...

def GetObject(moniker: str) -> _WMI: ...

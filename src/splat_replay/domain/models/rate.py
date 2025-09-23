"""Rate models and helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import ClassVar, Literal, cast


class RateBase(ABC):
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "RateBase":
        """Rehydrate a rate from a serialized dictionary."""
        type_ = data.get("type")
        value = data.get("value")
        if value is None:
            raise ValueError("valueがNoneではいけません")
        if not isinstance(type_, str):
            raise ValueError(f"未知のtype: {type_}")
        if type_ == "XP":
            if isinstance(value, (int, float, str)):
                return XP(float(value))
            raise ValueError("XP のvalueは数値として解釈できません")
        if type_ == "Udemae":
            if isinstance(value, str):
                return Udemae(value)
            raise ValueError("Udemae のvalueは文字列で指定してください")
        raise ValueError(f"未知のtype: {type_}")

    @property
    @abstractmethod
    def label(self) -> str:
        """Return label text for UI/logging."""
        raise NotImplementedError

    @abstractmethod
    def compare_rate(self, other: "RateBase") -> int:
        """Compare two rate objects."""
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RateBase):
            return NotImplemented
        return self.compare_rate(other) == 0

    def __lt__(self, other: "RateBase") -> bool:
        if not isinstance(other, RateBase):
            return NotImplemented
        return self.compare_rate(other) == -1

    @abstractmethod
    def __str__(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def short_str(self) -> str:
        raise NotImplementedError

    @classmethod
    def create(cls, value: float | int | str) -> "RateBase":
        """Create a rate from mixed representation."""
        if isinstance(value, (int, float)):
            return XP(float(value))
        if isinstance(value, str):
            try:
                xp = float(value)
            except ValueError:
                return Udemae(value)
            return XP(xp)
        raise ValueError("XP か Udemae の形式で指定してください")

    @abstractmethod
    def to_dict(self) -> dict[str, object]:
        """Serialize into a JSON-friendly dictionary."""
        raise NotImplementedError


class XP(RateBase):
    MIN_XP: ClassVar[float] = 500.0
    MAX_XP: ClassVar[float] = 5500.0

    def __init__(self, xp: float) -> None:
        if not (self.MIN_XP <= xp <= self.MAX_XP):
            raise ValueError(
                f"XP は {self.MIN_XP} 以上 {self.MAX_XP} 以下で指定してください"
            )
        self.xp = xp

    @property
    def label(self) -> str:
        return "XP"

    @property
    def value(self) -> float:
        return self.xp

    def compare_rate(self, other: RateBase) -> int:
        if not isinstance(other, XP):
            raise TypeError("XP 同士で比較してください")
        if self.xp < other.xp:
            return -1
        if self.xp > other.xp:
            return 1
        return 0

    def __str__(self) -> str:
        return str(self.xp)

    def short_str(self) -> str:
        return str(int(self.xp) // 100)

    def to_dict(self) -> dict[str, object]:
        return {"type": "XP", "value": self.xp}


class Udemae(RateBase):
    Rank = Literal[
        "C-",
        "C",
        "C+",
        "B-",
        "B",
        "B+",
        "A-",
        "A",
        "A+",
        "S",
        "S+",
    ]

    RANK_ORDER: ClassVar[dict[Rank, int]] = {
        "C-": 0,
        "C": 1,
        "C+": 2,
        "B-": 3,
        "B": 4,
        "B+": 5,
        "A-": 6,
        "A": 7,
        "A+": 8,
        "S": 9,
        "S+": 10,
    }

    def __init__(self, udemae: str) -> None:
        if udemae not in self.RANK_ORDER:
            raise ValueError("有効なウデマエを指定してください")
        self.udemae: Udemae.Rank = cast(Udemae.Rank, udemae)

    @property
    def label(self) -> str:
        return "ウデマエ"

    @property
    def value(self) -> Udemae.Rank:
        return self.udemae

    def compare_rate(self, other: RateBase) -> int:
        if not isinstance(other, Udemae):
            raise TypeError("Udemae 同士で比較してください")
        self_rank = self.RANK_ORDER.get(self.udemae)
        other_rank = self.RANK_ORDER.get(other.udemae)
        if self_rank is None or other_rank is None:
            raise ValueError("有効なウデマエを指定してください")
        if self_rank < other_rank:
            return -1
        if self_rank > other_rank:
            return 1
        return 0

    def __str__(self) -> str:
        return self.udemae

    def short_str(self) -> str:
        return self.udemae

    def to_dict(self) -> dict[str, object]:
        return {"type": "Udemae", "value": self.udemae}

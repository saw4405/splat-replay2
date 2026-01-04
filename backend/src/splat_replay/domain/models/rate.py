"""Rate models and helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Literal

from splat_replay.domain.exceptions import ValidationError


class RateBase(ABC):
    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "RateBase":
        """Rehydrate a rate from a serialized dictionary."""
        type_ = data.get("type")
        value = data.get("value")
        if value is None:
            raise ValidationError(
                "valueがNoneではいけません",
                error_code="RATE_VALUE_NONE",
            )
        if not isinstance(type_, str):
            raise ValidationError(
                f"未知のtype: {type_}",
                error_code="RATE_UNKNOWN_TYPE",
            )
        if type_ == "XP":
            if isinstance(value, (int, float, str)):
                return XP(float(value))
            raise ValidationError(
                "XP のvalueは数値として解釈できません",
                error_code="XP_VALUE_NOT_NUMERIC",
            )
        if type_ == "Udemae":
            if isinstance(value, str):
                return Udemae(Udemae.validate_rank(value))
            raise ValidationError(
                "Udemae のvalueは文字列で指定してください",
                error_code="UDEMAE_VALUE_NOT_STRING",
            )
        raise ValidationError(
            f"未知のtype: {type_}",
            error_code="RATE_UNKNOWN_TYPE",
        )

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
                return Udemae(Udemae.validate_rank(value))
            return XP(xp)
        raise ValidationError(
            "XP か Udemae の形式で指定してください",
            error_code="RATE_INVALID_FORMAT",
        )

    @abstractmethod
    def to_dict(self) -> dict[str, object]:
        """Serialize into a JSON-friendly dictionary."""
        raise NotImplementedError


@dataclass(frozen=True)
class XP(RateBase):
    """XP rate Value Object.

    Immutable Value Object representing XP-based rate.
    """

    MIN_XP: ClassVar[float] = 500.0
    MAX_XP: ClassVar[float] = 5500.0
    xp: float

    def __post_init__(self) -> None:
        if not (self.MIN_XP <= self.xp <= self.MAX_XP):
            raise ValidationError(
                f"XP は {self.MIN_XP} 以上 {self.MAX_XP} 以下で指定してください",
                error_code="XP_OUT_OF_RANGE",
            )

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


@dataclass(frozen=True)
class Udemae(RateBase):
    """Udemae rate Value Object.

    Immutable Value Object representing rank-based rate.
    """

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

    udemae: Rank

    @classmethod
    def validate_rank(cls, value: str) -> Rank:
        """Validate and convert string to Rank type."""
        if value not in cls.RANK_ORDER:
            raise ValidationError(
                "有効なウデマエを指定してください",
                error_code="UDEMAE_INVALID_RANK",
            )
        return value  # type: ignore[return-value]

    def __post_init__(self) -> None:
        if self.udemae not in self.RANK_ORDER:
            raise ValidationError(
                "有効なウデマエを指定してください",
                error_code="UDEMAE_INVALID_RANK",
            )

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
            raise ValidationError(
                "有効なウデマエを指定してください",
                error_code="UDEMAE_INVALID_RANK",
            )
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

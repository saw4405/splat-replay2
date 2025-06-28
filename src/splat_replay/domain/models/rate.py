"""レート関連クラス。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Union


class RateBase(ABC):
    """レートの基底クラス。"""

    @property
    @abstractmethod
    def label(self) -> str:
        """表示用ラベルを返す。"""
        raise NotImplementedError

    @abstractmethod
    def compare_rate(self, other: "RateBase") -> int:
        """レートを比較する。"""
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
    def __str__(self) -> str:  # pragma: no cover - 具象で実装
        raise NotImplementedError

    @abstractmethod
    def short_str(self) -> str:  # pragma: no cover - 具象で実装
        raise NotImplementedError

    @classmethod
    def create(cls, value: Union[float, int, str]) -> "RateBase":
        """値から適切なレートオブジェクトを生成する。"""
        if isinstance(value, (int, float)):
            return XP(float(value))
        if isinstance(value, str):
            try:
                xp = float(value)
                return XP(xp)
            except ValueError:
                return Udemae(value)
        raise ValueError("XP または Udemae のインスタンスを生成できません")


class XP(RateBase):
    """数値レートを表す。"""

    def __init__(self, xp: float) -> None:
        self.xp = xp

    @property
    def label(self) -> str:
        return "XP"

    @property
    def value(self) -> float:
        return self.xp

    def compare_rate(self, other: RateBase) -> int:
        if not isinstance(other, XP):
            raise TypeError("XP 同士でのみ比較可能です")
        if self.xp < other.xp:
            return -1
        if self.xp > other.xp:
            return 1
        return 0

    def __str__(self) -> str:
        return str(self.xp)

    def short_str(self) -> str:
        return str(int(self.xp) // 100)


class Udemae(RateBase):
    """ウデマエ表記のレート。"""

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

    RANK_ORDER = {
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

    def __init__(self, udemae: Union[Rank, str]) -> None:
        if udemae not in self.RANK_ORDER:
            raise ValueError("無効な評価ランクが指定されています")
        self.udemae = udemae

    @property
    def label(self) -> str:
        return "ウデマエ"

    @property
    def value(self) -> str:
        return self.udemae

    def compare_rate(self, other: RateBase) -> int:
        if not isinstance(other, Udemae):
            raise TypeError("Udemae 同士でのみ比較可能です")
        self_rank = self.RANK_ORDER.get(self.udemae)
        other_rank = self.RANK_ORDER.get(other.udemae)
        if self_rank is None or other_rank is None:
            raise ValueError("無効な評価ランクが指定されています")
        if self_rank < other_rank:
            return -1
        if self_rank > other_rank:
            return 1
        return 0

    def __str__(self) -> str:
        return self.udemae

    def short_str(self) -> str:
        return self.udemae

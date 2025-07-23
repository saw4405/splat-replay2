"""レート関連クラス。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Union


class RateBase(ABC):
    @classmethod
    def from_dict(cls, data: dict) -> "RateBase":
        """to_dictで出力した辞書からRateBaseインスタンスを復元する。"""
        type_ = data.get("type")
        value = data.get("value")
        if value is None:
            raise ValueError("valueがNoneです")
        if type_ == "XP":
            return XP(float(value))
        if type_ == "Udemae":
            return Udemae(value)
        raise ValueError(f"未知のtype: {type_}")

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

    @abstractmethod
    def to_dict(self) -> dict:
        """JSONシリアライズ可能な辞書を返す。"""
        raise NotImplementedError


class XP(RateBase):
    MIN_XP = 500.0
    MAX_XP = 5500.0

    def __init__(self, xp: float) -> None:
        if not (self.MIN_XP <= xp <= self.MAX_XP):
            raise ValueError(
                f"XP は {self.MIN_XP} から {self.MAX_XP} の範囲でなければなりません"
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

    def to_dict(self) -> dict:
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

    def to_dict(self) -> dict:
        return {"type": "Udemae", "value": self.udemae}

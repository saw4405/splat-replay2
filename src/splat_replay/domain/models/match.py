"""マッチ(バトル種別)を表す列挙型。"""

from __future__ import annotations

from enum import Enum


class Match(Enum):
    """マッチ(バトル種別)を表す列挙型。"""

    REGULAR = "レギュラーマッチ"
    ANARCHY = "バンカラマッチ"
    ANARCHY_OPEN = "バンカラマッチ(オープン)"
    ANARCHY_SERIES = "バンカラマッチ(チャレンジ)"
    X = "Xマッチ"
    CHALLENGE = "イベントマッチ"
    SPLATFEST = "フェスマッチ"
    SPLATFEST_OPEN = "フェスマッチ(オープン)"
    SPLATFEST_PRO = "フェスマッチ(チャレンジ)"
    TRICOLOR = "トリカラマッチ"

    def is_anarchy(self) -> bool:
        """バンカラマッチかどうかを返す。"""
        return self in {self.ANARCHY, self.ANARCHY_OPEN, self.ANARCHY_SERIES}

    def is_fest(self) -> bool:
        """フェスマッチかどうかを返す。"""
        return self in {
            self.SPLATFEST,
            self.SPLATFEST_OPEN,
            self.SPLATFEST_PRO,
        }

    def equal(self, other: Match, ignore_open_challenge: bool = False) -> bool:
        """種別が一致するか判定する。"""
        if self is other:
            return True
        if not ignore_open_challenge:
            return False
        if self.is_anarchy() and other.is_anarchy():
            return True
        if self.is_fest() and other.is_fest():
            return True
        return False

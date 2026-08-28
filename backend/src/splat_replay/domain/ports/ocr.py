from __future__ import annotations

from enum import StrEnum
from typing import Optional, Protocol

from splat_replay.domain.models import Frame


class OCRPurpose(StrEnum):
    """OCR 入力の意味的な用途。"""

    BATTLE_XP = "battle_xp"
    BATTLE_EVENT_POWER = "battle_event_power"
    BATTLE_KILL = "battle_kill"
    BATTLE_DEATH = "battle_death"
    BATTLE_SPECIAL = "battle_special"
    BATTLE_KILL_RECORD = "battle_kill_record"


class OCRPort(Protocol):
    """OCR処理を提供するポート。"""

    async def recognize_text(
        self,
        image: Frame,
        ps_mode: Optional[str] = None,
        whitelist: Optional[str] = None,
        purpose: OCRPurpose | None = None,
    ) -> Optional[str]: ...

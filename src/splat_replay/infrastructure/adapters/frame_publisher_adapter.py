"""Infrastructure adapter for FramePublisher using FrameHub."""

from __future__ import annotations

from splat_replay.application.interfaces import FramePublisher
from splat_replay.domain.models import Frame
from splat_replay.infrastructure.runtime.frames import FrameHub


class FramePublisherAdapter(FramePublisher):
    def __init__(self, hub: FrameHub) -> None:
        self._hub = hub

    def publish_frame(self, frame: Frame) -> None:
        try:
            self._hub.publish(frame)
        except Exception:
            pass


__all__ = ["FramePublisherAdapter"]

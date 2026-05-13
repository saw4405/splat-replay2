from __future__ import annotations

from splat_replay.infrastructure.adapters.capture.ndi_capture import NDICapture


class _FinderStub:
    def __init__(self) -> None:
        self.closed = False

    def get_source_names(self) -> list[str]:
        return ["OBS"]

    def get_source(self, name: str) -> str:
        return f"source:{name}"

    def close(self) -> None:
        self.closed = True


class _ReceiverStub:
    def __init__(self, *, connected: bool) -> None:
        self.connected = connected
        self.disconnected = False
        self.sources: list[str] = []

    def is_connected(self) -> bool:
        return self.connected

    def set_source(self, source: str) -> None:
        self.sources.append(source)

    def disconnect(self) -> None:
        self.disconnected = True
        self.connected = False


def test_on_finder_change_rebinds_source_when_receiver_disconnected() -> None:
    capture = object.__new__(NDICapture)
    capture.finder = _FinderStub()
    capture.receiver = _ReceiverStub(connected=False)
    capture.source = "stale-source"

    capture.on_finder_change()

    assert capture.source == "source:OBS"
    assert capture.receiver.sources == ["source:OBS"]


def test_capture_retries_finder_when_receiver_disconnected() -> None:
    capture = object.__new__(NDICapture)
    capture.finder = _FinderStub()
    capture.receiver = _ReceiverStub(connected=False)
    capture.source = None

    frame = capture.capture()

    assert frame is None
    assert capture.source == "source:OBS"
    assert capture.receiver.sources == ["source:OBS"]


def test_teardown_clears_source() -> None:
    capture = object.__new__(NDICapture)
    capture.finder = _FinderStub()
    capture.receiver = _ReceiverStub(connected=True)
    capture.source = "source:OBS"

    capture.teardown()

    assert capture.source is None
    assert capture.receiver.disconnected is True
    assert capture.finder.closed is True

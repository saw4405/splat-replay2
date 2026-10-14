from __future__ import annotations

from collections.abc import Callable
import sys
import threading
from queue import Queue
from types import SimpleNamespace
from typing import cast

import pytest

from splat_replay.interface.gui.macos_desktop_tray import MacOSDesktopTray


@pytest.mark.parametrize(
    "application_icon_mode",
    ["available", "missing", "raises", "compose_raises"],
)
def test_macos_status_item_keeps_brand_icon_and_updates_state_on_main_thread(
    monkeypatch: pytest.MonkeyPatch,
    application_icon_mode: str,
) -> None:
    class FakeButton:
        def __init__(self) -> None:
            self.image: object | None = None
            self.font: FakeFont | None = None
            self.title = ""
            self.tooltip = ""
            self.threads: list[str] = []
            self.image_positions: list[int] = []
            self.image_updates: list[object | None] = []

        def setImage_(self, image: object | None) -> None:
            self.threads.append(threading.current_thread().name)
            self.image_updates.append(image)
            self.image = image

        def setImagePosition_(self, position: int) -> None:
            self.threads.append(threading.current_thread().name)
            self.image_positions.append(position)

        def setFont_(self, font: object) -> None:
            self.threads.append(threading.current_thread().name)
            self.font = cast(FakeFont, font)

        def setTitle_(self, title: str) -> None:
            self.threads.append(threading.current_thread().name)
            self.title = title

        def setToolTip_(self, title: str) -> None:
            self.threads.append(threading.current_thread().name)
            self.tooltip = title

    class FakeMenuItem:
        def __init__(self) -> None:
            self.title = ""
            self.action: str | None = None
            self.target: object | None = None

        @classmethod
        def alloc(cls) -> FakeMenuItem:
            return cls()

        @classmethod
        def separatorItem(cls) -> FakeMenuItem:
            return cls()

        def initWithTitle_action_keyEquivalent_(
            self, title: str, action: str | None, _key: str
        ) -> FakeMenuItem:
            self.title = title
            self.action = action
            return self

        def setTarget_(self, target: object) -> None:
            self.target = target

        def setEnabled_(self, _enabled: bool) -> None:
            pass

        def setTitle_(self, title: str) -> None:
            self.title = title

    class FakeMenu:
        def __init__(self) -> None:
            self.items: list[FakeMenuItem] = []

        @classmethod
        def alloc(cls) -> FakeMenu:
            return cls()

        def initWithTitle_(self, _title: str) -> FakeMenu:
            return self

        def addItem_(self, item: FakeMenuItem) -> None:
            self.items.append(item)

    class FakeStatusItem:
        def __init__(self, button: FakeButton) -> None:
            self._button = button
            self.menu: FakeMenu | None = None

        def button(self) -> FakeButton:
            return self._button

        def setMenu_(self, menu: FakeMenu) -> None:
            self.menu = menu

    button = FakeButton()
    status_item = FakeStatusItem(button)
    status_bar = SimpleNamespace(
        statusItemWithLength_=lambda _length: status_item,
        removeStatusItem_=lambda item: removed.append(item),
    )
    removed: list[FakeStatusItem] = []
    focused_image: object | None = None
    drawing_threads: list[str] = []

    class FakeImage:
        def __init__(self, size: tuple[float, float], template: bool) -> None:
            self.size = size
            self.template = template
            self.lock_count = 0
            self.unlock_count = 0
            self.size_at_lock: tuple[float, float] | None = None
            self.badge_size: tuple[float, float] | None = None
            self.badge_color: str | None = None
            self.badge_glyph: str | None = None
            self.glyph_color: str | None = None
            self.glyph_font_size: float | None = None
            self.current_color: str | None = None

        def copy(self) -> FakeImage:
            image = FakeImage(self.size, self.template)
            image_copies.append(image)
            return image

        def setSize_(self, size: tuple[float, float]) -> None:
            self.size = size

        def setTemplate_(self, template: bool) -> None:
            self.template = template

        def lockFocus(self) -> None:
            nonlocal focused_image
            assert focused_image is None
            focused_image = self
            self.lock_count += 1
            self.size_at_lock = self.size
            drawing_threads.append(threading.current_thread().name)

        def unlockFocus(self) -> None:
            nonlocal focused_image
            assert focused_image is self
            focused_image = None
            self.unlock_count += 1
            drawing_threads.append(threading.current_thread().name)

    image_copies: list[FakeImage] = []

    class FakeFont:
        def __init__(self, size: float) -> None:
            self.size = size

    class FakeFontClass:
        @staticmethod
        def systemFontOfSize_(size: float) -> FakeFont:
            return FakeFont(size)

    class FakeColor:
        def __init__(self, name: str) -> None:
            self.name = name

        def set(self) -> None:
            assert focused_image is not None
            cast(FakeImage, focused_image).current_color = self.name
            drawing_threads.append(threading.current_thread().name)

    class FakeColorClass:
        @staticmethod
        def blackColor() -> FakeColor:
            return FakeColor("black")

        @staticmethod
        def whiteColor() -> FakeColor:
            return FakeColor("white")

    class FakeBezierPath:
        def __init__(
            self, rect: tuple[tuple[float, float], tuple[float, float]]
        ) -> None:
            self.rect = rect

        def fill(self) -> None:
            if application_icon_mode == "compose_raises":
                raise RuntimeError("simulated status image drawing failure")
            assert focused_image is not None
            image = cast(FakeImage, focused_image)
            image.badge_size = self.rect[1]
            image.badge_color = image.current_color
            drawing_threads.append(threading.current_thread().name)

    class FakeBezierPathClass:
        @staticmethod
        def bezierPathWithOvalInRect_(
            rect: tuple[tuple[float, float], tuple[float, float]],
        ) -> FakeBezierPath:
            return FakeBezierPath(rect)

    class FakeAttributedString:
        def __init__(self) -> None:
            self.text = ""
            self.attributes: dict[str, object] = {}

        def initWithString_attributes_(
            self, text: str, attributes: dict[str, object]
        ) -> FakeAttributedString:
            self.text = text
            self.attributes = attributes
            return self

        def size(self) -> tuple[float, float]:
            font = cast(FakeFont, self.attributes["NSFontAttributeName"])
            return (font.size - 2.0, font.size)

        def drawAtPoint_(self, _point: tuple[float, float]) -> None:
            assert focused_image is not None
            image = cast(FakeImage, focused_image)
            color = cast(
                FakeColor,
                self.attributes["NSForegroundColorAttributeName"],
            )
            font = cast(FakeFont, self.attributes["NSFontAttributeName"])
            image.badge_glyph = self.text
            image.glyph_color = color.name
            image.glyph_font_size = font.size
            drawing_threads.append(threading.current_thread().name)

    class FakeAttributedStringClass:
        @staticmethod
        def alloc() -> FakeAttributedString:
            return FakeAttributedString()

    dock_icon = FakeImage((512.0, 512.0), True)

    class FakeApplication:
        @staticmethod
        def sharedApplication() -> FakeApplication:
            return FakeApplication()

        def applicationIconImage(self) -> FakeImage | None:
            if application_icon_mode == "raises":
                raise RuntimeError("simulated application icon failure")
            return None if application_icon_mode == "missing" else dock_icon

    class FakeStatusBar:
        @staticmethod
        def systemStatusBar() -> object:
            return status_bar

    class FakeNSObject:
        @classmethod
        def alloc(cls) -> FakeNSObject:
            return cls()

        def init(self) -> FakeNSObject:
            return self

    def selector(function: object, **_kwargs: object) -> object:
        return function

    monkeypatch.setitem(
        sys.modules,
        "AppKit",
        SimpleNamespace(
            NSVariableStatusItemLength=-1.0,
            NSMenu=FakeMenu,
            NSMenuItem=FakeMenuItem,
            NSStatusBar=FakeStatusBar,
            NSApplication=FakeApplication,
            NSFont=FakeFontClass,
            NSBezierPath=FakeBezierPathClass,
            NSColor=FakeColorClass,
            NSAttributedString=FakeAttributedStringClass,
            NSFontAttributeName="NSFontAttributeName",
            NSForegroundColorAttributeName="NSForegroundColorAttributeName",
            NSImageLeft=2,
        ),
    )
    monkeypatch.setitem(
        sys.modules, "Foundation", SimpleNamespace(NSObject=FakeNSObject)
    )
    monkeypatch.setitem(
        sys.modules, "objc", SimpleNamespace(selector=selector)
    )

    callbacks: Queue[Callable[[], None]] = Queue()
    commands: list[str] = []
    tray = MacOSDesktopTray(commands.append, callbacks.put)
    tray.start()
    has_brand_icon = application_icon_mode in {"available", "compose_raises"}
    brand_icon = image_copies[0] if has_brand_icon else None
    if has_brand_icon:
        assert brand_icon is not None
        assert brand_icon is not dock_icon
        assert brand_icon.size == (24.0, 24.0)
        assert brand_icon.template is False
        assert brand_icon.badge_glyph is None
        assert dock_icon.size == (512.0, 512.0)
        assert dock_icon.template is True
        if application_icon_mode == "available":
            assert isinstance(button.image, FakeImage)
            assert button.image is image_copies[1]
            assert button.image.size == (24.0, 24.0)
            assert button.image.size_at_lock == (48.0, 48.0)
            assert button.image.badge_size == (20.0, 20.0)
            assert button.image.badge_color == "white"
            assert button.image.badge_glyph == "…"
            assert button.image.glyph_color == "black"
            assert button.image.glyph_font_size == 18.0
            assert button.title == ""
        else:
            assert button.image is None
            assert button.title == "SR …"
    else:
        assert button.image is None
        assert button.title == "SR …"
    assert button.image_positions == [2]
    assert button.image_updates == [
        image_copies[1] if application_icon_mode == "available" else None
    ]
    assert button.font is not None
    assert button.font.size == 9.0
    assert button.tooltip == "Splat Replay — 起動中"
    assert status_item.menu is not None
    menu_items = status_item.menu.items
    assert menu_items[0].title == "起動中"
    show_action = cast(
        Callable[[object], None], getattr(menu_items[2].target, "show_")
    )
    quit_action = cast(
        Callable[[object], None], getattr(menu_items[4].target, "quit_")
    )
    show_action(menu_items[2])
    quit_action(menu_items[4])
    assert commands == ["show", "quit"]

    states = (
        ("waiting", "待機中", "○"),
        ("recording", "録画中", "●"),
        ("processing", "編集・アップロード中", "⚙"),
        ("attention", "機器未接続", "!"),
    )
    tray.set_status("starting", "起動中")
    assert callbacks.empty()
    for state, description, symbol in states:
        if state == "waiting":
            worker = threading.Thread(
                target=tray.set_status,
                args=(state, description),
                name="tray-status-worker",
            )
            worker.start()
            worker.join(timeout=2)
            assert not worker.is_alive()
            if application_icon_mode == "available":
                assert isinstance(button.image, FakeImage)
                assert button.image.badge_glyph == "…"
                assert button.title == ""
            else:
                assert button.title == "SR …"
        else:
            tray.set_status(state, description)
        callbacks.get_nowait()()
        if application_icon_mode == "available":
            assert isinstance(button.image, FakeImage)
            assert button.image is image_copies[-1]
            assert button.image is not brand_icon
            assert button.image.size == (24.0, 24.0)
            assert button.image.size_at_lock == (48.0, 48.0)
            assert button.image.badge_glyph == symbol
            assert button.image.badge_size == (20.0, 20.0)
            assert button.image.badge_color == "white"
            assert button.image.glyph_color == "black"
            assert button.image.glyph_font_size == 18.0
            assert button.title == ""
        else:
            assert button.image is None
            assert button.title == f"SR {symbol}"
        assert menu_items[0].title == description
        assert button.tooltip == f"Splat Replay — {description}"

    if application_icon_mode == "available":
        assert button.image_updates == image_copies[1:]
    else:
        assert button.image_updates == [None] * 5
    assert all(
        image.lock_count == image.unlock_count for image in image_copies
    )
    assert all(image.size == (24.0, 24.0) for image in image_copies)
    assert all(
        image.size_at_lock == (48.0, 48.0) for image in image_copies[1:]
    )
    assert all(
        thread == threading.main_thread().name for thread in drawing_threads
    )
    if application_icon_mode == "available":
        assert brand_icon is not None
        assert brand_icon.badge_glyph is None
        assert brand_icon.size == (24.0, 24.0)
        assert dock_icon.size == (512.0, 512.0)
        assert dock_icon.template is True

    assert set(button.threads) == {threading.main_thread().name}
    tray.close()
    assert removed == [status_item]


def test_macos_status_item_start_failure_removes_partial_native_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenStatusItem:
        def button(self) -> object:
            raise RuntimeError("simulated native button failure")

    class StatusBar:
        def __init__(self) -> None:
            self.removed: list[object] = []
            self.item = BrokenStatusItem()

        def statusItemWithLength_(self, _length: float) -> object:
            return self.item

        def removeStatusItem_(self, item: object) -> None:
            self.removed.append(item)

    status_bar = StatusBar()

    class NativeStatusBar:
        @staticmethod
        def systemStatusBar() -> StatusBar:
            return status_bar

    monkeypatch.setitem(
        sys.modules,
        "AppKit",
        SimpleNamespace(
            NSVariableStatusItemLength=-1.0,
            NSStatusBar=NativeStatusBar,
            NSMenu=object,
            NSMenuItem=object,
        ),
    )
    monkeypatch.setitem(
        sys.modules, "Foundation", SimpleNamespace(NSObject=object)
    )
    monkeypatch.setitem(sys.modules, "objc", SimpleNamespace())

    tray = MacOSDesktopTray(lambda _command: None, lambda _callback: None)
    with pytest.raises(RuntimeError, match="simulated native button failure"):
        tray.start()
    assert status_bar.removed == [status_bar.item]

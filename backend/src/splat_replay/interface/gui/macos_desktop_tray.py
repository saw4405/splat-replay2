"""macOS のメニューバー状態表示。"""

from __future__ import annotations

import importlib
import threading
from contextlib import suppress
from collections.abc import Callable
from types import new_class
from typing import Protocol, cast

_Point = tuple[float, float]
_Rect = tuple[_Point, _Point]


class _Button(Protocol):
    def setImage_(self, image: object | None) -> None: ...

    def setImagePosition_(self, position: int) -> None: ...

    def setFont_(self, font: object) -> None: ...

    def setTitle_(self, title: str) -> None: ...

    def setToolTip_(self, title: str) -> None: ...


class _MenuItem(Protocol):
    def setTarget_(self, target: object) -> None: ...

    def setEnabled_(self, enabled: bool) -> None: ...

    def setTitle_(self, title: str) -> None: ...


class _Menu(Protocol):
    def addItem_(self, item: object) -> None: ...


class _MenuAllocation(Protocol):
    def initWithTitle_(self, title: str) -> _Menu: ...


class _MenuClass(Protocol):
    def alloc(self) -> _MenuAllocation: ...


class _MenuItemAllocation(Protocol):
    def initWithTitle_action_keyEquivalent_(
        self, title: str, action: str | None, key: str
    ) -> _MenuItem: ...


class _MenuItemClass(Protocol):
    def alloc(self) -> _MenuItemAllocation: ...

    def separatorItem(self) -> _MenuItem: ...


class _StatusItem(Protocol):
    def button(self) -> _Button: ...

    def setMenu_(self, menu: object) -> None: ...


class _StatusBar(Protocol):
    def statusItemWithLength_(self, length: float) -> _StatusItem: ...

    def removeStatusItem_(self, item: _StatusItem) -> None: ...


class _StatusBarClass(Protocol):
    def systemStatusBar(self) -> _StatusBar: ...


class _Image(Protocol):
    def copy(self) -> _Image: ...

    def lockFocus(self) -> None: ...

    def setSize_(self, size: tuple[float, float]) -> None: ...

    def setTemplate_(self, template: bool) -> None: ...

    def unlockFocus(self) -> None: ...


class _BezierPath(Protocol):
    def fill(self) -> None: ...


class _BezierPathClass(Protocol):
    def bezierPathWithOvalInRect_(self, rect: _Rect) -> _BezierPath: ...


class _Color(Protocol):
    def set(self) -> None: ...


class _ColorClass(Protocol):
    def blackColor(self) -> _Color: ...

    def whiteColor(self) -> _Color: ...


class _AttributedString(Protocol):
    def drawAtPoint_(self, point: _Point) -> None: ...

    def size(self) -> _Point: ...


class _AttributedStringAllocation(Protocol):
    def initWithString_attributes_(
        self, text: str, attributes: dict[str, object]
    ) -> _AttributedString: ...


class _AttributedStringClass(Protocol):
    def alloc(self) -> _AttributedStringAllocation: ...


class _Application(Protocol):
    def applicationIconImage(self) -> _Image | None: ...


class _ApplicationClass(Protocol):
    def sharedApplication(self) -> _Application: ...


class _FontClass(Protocol):
    def systemFontOfSize_(self, size: float) -> object: ...


class _AppKit(Protocol):
    NSVariableStatusItemLength: float
    NSMenu: _MenuClass
    NSMenuItem: _MenuItemClass
    NSStatusBar: _StatusBarClass
    NSApplication: _ApplicationClass
    NSFont: _FontClass
    NSBezierPath: _BezierPathClass
    NSColor: _ColorClass
    NSAttributedString: _AttributedStringClass
    NSFontAttributeName: str
    NSForegroundColorAttributeName: str
    NSImageLeft: int


class _NSObjectAllocation(Protocol):
    def init(self) -> object: ...


class _NSObjectClass(Protocol):
    def alloc(self) -> _NSObjectAllocation: ...


class _ObjectiveC(Protocol):
    def selector(
        self,
        function: Callable[..., object],
        *,
        selector: bytes,
        signature: bytes,
    ) -> object: ...


class MacOSDesktopTray:
    """AppKit の status item を所有し、更新をメインスレッドへ送る。"""

    _STATUS_GLYPHS = {
        "starting": "…",
        "waiting": "○",
        "recording": "●",
        "processing": "⚙",
        "attention": "!",
    }

    def __init__(
        self,
        command: Callable[[str], None],
        call_after: Callable[[Callable[[], None]], None],
    ) -> None:
        self._command = command
        self._call_after = call_after
        self._status = ("starting", "起動中")
        self._applied_status: tuple[str, str] | None = None
        self._status_lock = threading.Lock()
        self._appkit: _AppKit | None = None
        self._status_bar: _StatusBar | None = None
        self._status_item: _StatusItem | None = None
        self._button: _Button | None = None
        self._brand_icon: _Image | None = None
        self._description_item: _MenuItem | None = None
        self._target: object | None = None

    def start(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError(
                "メニューバー項目はメインスレッドで作成してください"
            )

        try:
            appkit = cast(_AppKit, importlib.import_module("AppKit"))
            foundation = importlib.import_module("Foundation")
            objc = cast(_ObjectiveC, importlib.import_module("objc"))
            self._appkit = appkit
            self._status_bar = appkit.NSStatusBar.systemStatusBar()
            self._status_item = self._status_bar.statusItemWithLength_(
                appkit.NSVariableStatusItemLength
            )
            self._button = self._status_item.button()
            brand_icon: _Image | None = None
            try:
                app_icon = appkit.NSApplication.sharedApplication().applicationIconImage()
                if app_icon is not None:
                    brand_icon = app_icon.copy()
                    brand_icon.setSize_((24.0, 24.0))
                    brand_icon.setTemplate_(False)
            except Exception:
                brand_icon = None
            self._brand_icon = brand_icon
            self._button.setImagePosition_(appkit.NSImageLeft)
            self._button.setFont_(appkit.NSFont.systemFontOfSize_(9.0))
            self._target = self._create_target(
                cast(type[object], getattr(foundation, "NSObject")), objc
            )
            self._create_menu(appkit)
            self._apply_status()
        except Exception:
            self.close()
            raise

    def set_status(self, state: str, description: str) -> None:
        status = (state, description)
        with self._status_lock:
            if status == self._status:
                return
            self._status = status
        self._call_after(self._apply_status)

    def close(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError(
                "メニューバー項目はメインスレッドで破棄してください"
            )
        if self._status_item is not None and self._status_bar is not None:
            with suppress(Exception):
                self._status_bar.removeStatusItem_(self._status_item)
        self._status_item = None
        self._status_bar = None
        self._button = None
        self._brand_icon = None
        self._description_item = None
        self._target = None
        self._appkit = None

    def _create_target(
        self, ns_object: type[object], objc: _ObjectiveC
    ) -> object:
        def show(_self: object, _sender: object) -> None:
            self._command("show")

        def quit(_self: object, _sender: object) -> None:
            self._command("quit")

        target_type = new_class(
            "SplatReplayStatusItemTarget",
            (ns_object,),
            {},
            lambda namespace: namespace.update(
                {
                    "show_": objc.selector(
                        show, selector=b"show:", signature=b"v@:@"
                    ),
                    "quit_": objc.selector(
                        quit, selector=b"quit:", signature=b"v@:@"
                    ),
                }
            ),
        )
        return cast(_NSObjectClass, target_type).alloc().init()

    def _create_menu(self, appkit: _AppKit) -> None:
        assert self._status_item is not None and self._target is not None
        menu = appkit.NSMenu.alloc().initWithTitle_("Splat Replay")
        self._description_item = self._menu_item(
            appkit, self._status[1], None, self._target
        )
        self._description_item.setEnabled_(False)
        menu.addItem_(self._description_item)
        menu.addItem_(appkit.NSMenuItem.separatorItem())
        menu.addItem_(
            self._menu_item(appkit, "画面を開く", "show:", self._target)
        )
        menu.addItem_(appkit.NSMenuItem.separatorItem())
        menu.addItem_(
            self._menu_item(
                appkit,
                "完全終了（処理完了を待つ）",
                "quit:",
                self._target,
            )
        )
        self._status_item.setMenu_(menu)

    @staticmethod
    def _menu_item(
        appkit: _AppKit,
        title: str,
        action: str | None,
        target: object,
    ) -> _MenuItem:
        item = appkit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            title, action, ""
        )
        item.setTarget_(target)
        return item

    @staticmethod
    def _compose_status_image(
        appkit: _AppKit, brand_icon: _Image, glyph: str
    ) -> _Image:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("状態画像はメインスレッドで描画してください")

        image = brand_icon.copy()
        image.setSize_((48.0, 48.0))
        # lockFocusはdeprecatedだが、状態更新中にmain threadで同期描画する。
        image.lockFocus()
        try:
            badge = appkit.NSBezierPath.bezierPathWithOvalInRect_(
                ((0.0, 0.0), (20.0, 20.0))
            )
            appkit.NSColor.whiteColor().set()
            badge.fill()
            label = appkit.NSAttributedString.alloc().initWithString_attributes_(
                glyph,
                {
                    appkit.NSFontAttributeName: appkit.NSFont.systemFontOfSize_(
                        18.0
                    ),
                    appkit.NSForegroundColorAttributeName: appkit.NSColor.blackColor(),
                },
            )
            glyph_width, glyph_height = label.size()
            label.drawAtPoint_(
                ((20.0 - glyph_width) / 2, (20.0 - glyph_height) / 2)
            )
        finally:
            try:
                image.unlockFocus()
            finally:
                image.setSize_((24.0, 24.0))
        return image

    def _apply_status(self) -> None:
        if (
            self._appkit is None
            or self._button is None
            or self._description_item is None
        ):
            return
        with self._status_lock:
            status = self._status
        if status == self._applied_status:
            return
        state, description = status
        glyph = self._STATUS_GLYPHS.get(state, self._STATUS_GLYPHS["starting"])
        status_image = None
        if self._brand_icon is not None:
            try:
                status_image = self._compose_status_image(
                    self._appkit, self._brand_icon, glyph
                )
            except Exception:
                status_image = None
        self._button.setImage_(status_image)
        self._button.setTitle_(
            "" if status_image is not None else f"SR {glyph}"
        )
        self._button.setToolTip_(f"Splat Replay — {description}")
        self._description_item.setTitle_(description)
        self._applied_status = status

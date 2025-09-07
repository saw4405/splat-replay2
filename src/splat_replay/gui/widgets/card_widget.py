from __future__ import annotations

import ttkbootstrap as ttk

from splat_replay.shared.logger import get_logger


class CardWidget:
    def __init__(
        self,
        parent: ttk.Frame,
        title: str,
    ):
        self.logger = get_logger()
        self.parent = parent

        self._container = ttk.LabelFrame(
            self.parent, text=title, style="Card.TLabelframe"
        )
        self._container.configure(padding=15)
        self._container.pack(fill="both", expand=True)

        self.header = ttk.Frame(self._container)
        self.header.pack(side="top", fill="x", expand=True)

        self.content = ttk.Frame(self._container)
        self.content.pack(fill="both", expand=True, pady=10)

        self.footer = ttk.Frame(self._container)
        self.footer.pack(side="bottom", fill="x", expand=True, pady=10)

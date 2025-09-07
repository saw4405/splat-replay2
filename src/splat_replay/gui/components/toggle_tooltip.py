from ttkbootstrap.tooltip import ToolTip


class ToggleToolTip(ToolTip):
    def __init__(self, *args, enabled: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.enabled = enabled

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False
        self.hide_tip()

    def enter(self, event=None):
        if not self.enabled:
            return
        super().enter(event)

    def move_tip(self, *a):
        if not self.enabled:
            return
        super().move_tip(*a)

    def show_tip(self, *a):
        if not self.enabled:
            return
        super().show_tip(*a)

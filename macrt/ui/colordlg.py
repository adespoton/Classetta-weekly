"""
macrt.ui.colordlg - The Color Picker's dialog (GetColor): the host's
colour dialog, with the program's prompt as its title.

As with the Standard File dialogs, the application's thread opens it and
waits on a Future for the answer:

    ("ok", (red, green, blue))      each 0 to $FFFF
    ("cancel",)
"""

from __future__ import annotations

from concurrent.futures import Future
from typing import TYPE_CHECKING

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog

if TYPE_CHECKING:
    from .display import Display


class ColorDialog(QColorDialog):
    def __init__(self, display: Display | None, prompt: str, rgb: tuple[int, int, int]):
        super().__init__(QColor.fromRgba64(*rgb),
                         display.host_window if display is not None else None)
        self.display = display
        self._start = rgb
        self._future: Future = Future()
        self.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
        self.setWindowTitle(prompt or "Choose a Color")
        self.setModal(False)
        self.colorSelected.connect(self._chosen)
        self.rejected.connect(lambda: self._answer("cancel"))

    def _chosen(self, color: QColor) -> None:
        """The colour chosen; the one it started with as it was, if that's
        it (the dialog keeps 8 bits of each component)."""
        if color.rgb() == QColor.fromRgba64(*self._start).rgb():
            self._answer("ok", self._start)
            return
        c = color.rgba64()
        self._answer("ok", (c.red(), c.green(), c.blue()))

    def _answer(self, *action) -> None:
        if not self._future.done():
            self._future.set_result(action)

    def finish(self) -> None:
        """The application has its answer."""
        if self.display is not None and self in self.display.color_dialogs:
            self.display.color_dialogs.remove(self)
        self.hide()
        self.deleteLater()


def open_color(display: Display, prompt: str, rgb: tuple[int, int, int]
               ) -> tuple[ColorDialog, tuple[Future]]:
    """On the GUI thread.  (The Future in a tuple, so the bridge doesn't
    wait for it.)"""
    dlg = ColorDialog(display, prompt, rgb)
    display.color_dialogs.append(dlg)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg, (dlg._future,)

"""
macrt.ui.editiondlg - The Edition Manager's publisher and subscriber
options dialogs (SectionOptionsDialog): macrt's own, in Qt, with what
Inside Macintosh: Interapplication Communication says they show: the
edition, its latest date, the update mode, and buttons to send or get an
edition now, to cancel the section and, for a subscriber, to open its
publisher.

As with the Standard File dialogs, the application's thread opens one and
waits on a Future for each step the user takes:

    ("mode", manual)        an update mode chosen
    ("button", what)        "cancel section", "goto", "now", "ok" or "cancel"

and then finishes it, or resumes it showing the update mode it's to show.
"""

from __future__ import annotations

from concurrent.futures import Future
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (QButtonGroup, QDialog, QGridLayout, QHBoxLayout, QLabel,
                             QPushButton, QRadioButton, QVBoxLayout)

from . import theme

if TYPE_CHECKING:
    from .display import Display


class SectionOptionsDialog(QDialog):
    def __init__(self, display: Display | None, publisher: bool, edition: str, latest: str,
                 manual: bool, title: str = ""):
        super().__init__(display.host_window if display is not None else None)
        self.display = display
        self.publisher = publisher
        self._future: Future | None = None
        self.setWindowTitle(title or ("Publisher Options" if publisher else "Subscriber Options"))
        self.setModal(False)
        self.setFont(theme.menu_item_font())

        kind = "Publisher" if publisher else "Subscriber"
        self.edition = QLabel(f"{kind} to: “{edition}”")
        self.latest = QLabel(f"Latest Edition: {latest}")
        modes = (("On Save", "Manually") if publisher else ("Automatically", "Manually"))
        self.automatic = QRadioButton(modes[0])
        self.manual = QRadioButton(modes[1])
        self.modes = QButtonGroup(self)
        self.modes.addButton(self.automatic, 0)
        self.modes.addButton(self.manual, 1)
        self.modes.idClicked.connect(lambda n: self._step("mode", bool(n)))
        self.now = QPushButton("Send Edition Now" if publisher else "Get Edition Now")
        self.cancel_section = QPushButton(f"Cancel {kind}")
        self.open_publisher = QPushButton("Open Publisher")
        self.cancel_button = QPushButton("Cancel")
        self.ok = QPushButton("OK")
        self.ok.setDefault(True)
        for b, what in ((self.now, "now"), (self.cancel_section, "cancel section"),
                        (self.open_publisher, "goto"), (self.cancel_button, "cancel"),
                        (self.ok, "ok")):
            if b is not self.ok:
                b.setAutoDefault(False)
            b.clicked.connect(lambda _=False, what=what: self._step("button", what))

        grid = QGridLayout()
        grid.addWidget(QLabel("Send Editions:" if publisher else "Get Editions:"), 0, 0)
        grid.addWidget(self.automatic, 0, 1)
        grid.addWidget(self.now, 0, 2)
        grid.addWidget(self.manual, 1, 1)
        grid.addWidget(self.latest, 2, 0, 1, 3)
        buttons = QHBoxLayout()
        buttons.addWidget(self.cancel_section)
        if not publisher:
            buttons.addWidget(self.open_publisher)
        else:
            self.open_publisher.hide()
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.ok)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(13, 10, 13, 13)
        outer.addWidget(self.edition)
        outer.addLayout(grid)
        outer.addLayout(buttons)
        self._show_mode(manual)

    # =====================================================================
    # The application's thread
    # =====================================================================
    def resume(self, manual: bool) -> tuple[Future]:
        """Show the update mode and wait for the next step.  (A tuple, so
        the bridge doesn't wait for the Future itself.)"""
        self._show_mode(manual)
        self._future = Future()
        self._update_buttons()
        return (self._future,)

    def finish(self) -> None:
        """The application has its answer."""
        if self.display is not None and self in self.display.edition_dialogs:
            self.display.edition_dialogs.remove(self)
        self.hide()
        self.deleteLater()

    # =====================================================================
    # The user's side
    # =====================================================================
    def _show_mode(self, manual: bool) -> None:
        (self.manual if manual else self.automatic).setChecked(True)

    def _step(self, *action) -> None:
        fut, self._future = self._future, None
        if fut is not None and not fut.done():
            fut.set_result(action)
        self._update_buttons()

    def _update_buttons(self) -> None:
        waiting = self._future is not None
        for w in (self.automatic, self.manual, self.now, self.cancel_section,
                  self.open_publisher, self.cancel_button, self.ok):
            w.setEnabled(waiting)

    def reject(self) -> None:  # Escape, or the close box
        self._step("button", "cancel")

    def closeEvent(self, event):  # noqa: N802
        event.ignore()
        self.reject()

    # For tests, and anything else that drives the dialog
    def press(self, what: str) -> None:
        self._step("button", what)

    def choose_mode(self, manual: bool) -> None:
        self._step("mode", manual)


def open_options(display: Display, publisher: bool, edition: str, latest: str, manual: bool
                 ) -> tuple[SectionOptionsDialog, tuple[Future]]:
    """On the GUI thread: show a new dialog and wait for the first step."""
    dlg = SectionOptionsDialog(display, publisher, edition, latest, manual)
    display.edition_dialogs.append(dlg)
    waiting = dlg.resume(manual)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg, waiting

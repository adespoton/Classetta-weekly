"""
macrt.ui.finder - A System 6 Finder window over a disk image's folder.

When a disk image is named on the command line with no --app, the Display
opens this instead of running the image's first application: a window with
the chrome of a System 6 document window — Chicago title, pinstripes, a
close box — listing the folder's contents.  Double-clicking an
application runs it, a document opens it with the application that made
it, and a folder opens a window of its own.  The window stays open, so
several applications can be started from one, and its close box closes
it like a real Finder window's.

Nothing here writes back to the disk: the window only lists what the
folder already holds, so its header wears the padlock System 6 showed
beside Name on a locked disk — that the list may be looked at, not
changed.  FinderOptions.writable is how a window says otherwise.
"""

from __future__ import annotations

import time
from concurrent.futures import Future
from dataclasses import dataclass
from typing import TYPE_CHECKING

import machfs
from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QHeaderView, QMessageBox, QTreeWidget, QTreeWidgetItem, QWidget,
)

from ..macfile import MacFile, is_control_panel, launch_target, list_folder
from ..m68k.segload import has_code, why_no_code
from ..resfork import is_fork
from ..toolbox import constants as k
from ..toolbox.windows import WindowKind
from ..viewer import describe, viewer_main
from . import chrome, theme
from .stdfile import icon
from .tracking import BoxTracker, DragTracker
from .window import _Hosted

if TYPE_CHECKING:
    from .display import Display

CONTENT = (316, 236)       # the list's size, inside the frame
LIST_STYLE = """
QTreeWidget { background: white; color: black; border: none; outline: none; }
QTreeWidget::item { padding: 1px; }
QTreeWidget::item:selected { background: black; color: white; }
QHeaderView::section { background: white; color: black; border: none;
                       border-right: 1px solid black; border-bottom: 1px solid black;
                       padding: 2px 4px; }
"""
FOLDER = b"fldr"
KINDS = [(b"ZSYS", "System file"), (b"zsys", "System file"), (b"cdev", "Control Panel"),
         (b"FFIL", "Font")]
# The padlock beside Name while the window is view-only: solid body, white
# keyhole (the transparency behind it), close to the one System 6 drew.
LOCK = [
    "..#####..",
    "..#...#..",
    "..#...#..",
    "..#...#..",
    "#########",
    "#########",
    "#########",
    "####.####",
    "###...###",
    "#########",
    "#########",
]


@dataclass(frozen=True)
class FinderOptions:
    """How applications are launched from the window, from the command
    line: view shows them from their resources without running them,
    trace logs the traps they call, memory is their size in bytes.
    writable is about the window itself: while it is False — always,
    until Finder Windows can be written from here — the list is
    view-only and the header shows the lock."""
    view: bool = False
    trace: bool = False
    memory: int | None = None
    writable: bool = False


def _kind(f: MacFile) -> str:
    if f.type == FOLDER:
        return "folder"
    if f.is_application:
        return "application"
    return next((name for t, name in KINDS if f.type == t), "document")


def _icon_for(f: MacFile) -> str:
    if f.type == FOLDER:
        return "folder"
    return "application" if f.is_application else "document"


def _lock() -> QIcon:
    """The header's padlock: the list may be looked at, not changed."""
    w, h = theme.bitmap_size(LOCK)
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    theme.draw_bitmap(p, 0, 0, LOCK)
    p.end()
    return QIcon(pm)


class FinderWindow(_Hosted):
    """One folder's window: its contents listed, ready to open."""

    def __init__(self, display: Display, volume: machfs.Volume,
                 path: tuple[str, ...] = (), options: FinderOptions | None = None,
                 parent: QWidget | None = None):
        super().__init__(display, parent)
        self.volume = volume
        self.path = path
        self.options = options or FinderOptions()
        self.setWindowTitle(self.path[-1] if self.path else self.volume.name)
        self._hilited = True
        self._pressed = k.wNoHit
        self._last_name: str | None = None
        self._opened_at = 0.0
        self.entries: dict[str, MacFile] = {}
        self.tree = QTreeWidget(self)
        self._fill()
        self.tree.setStyleSheet(LIST_STYLE)
        self.tree.setFont(theme.body_font())
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.tree.setUniformRowHeights(True)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setHeaderLabels(["Name", "Size", "Kind"])
        if not self.options.writable:      # view-only: the lock beside Name
            self.tree.headerItem().setIcon(0, _lock())
        header = self.tree.header()
        header.setFont(theme.title_font())
        header.setStretchLastSection(False)
        header.setSectionsClickable(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tree.setColumnWidth(1, 56)
        self.tree.setColumnWidth(2, 84)
        self.tree.itemActivated.connect(self._activated)
        self.tree.viewport().installEventFilter(self)
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._focus_changed)
        self._relayout()

    # -- content ----------------------------------------------------------
    def _fill(self) -> None:
        files = sorted(list_folder(self.volume, self.path), key=lambda f: f.name.lower())
        self.entries = {f.name: f for f in files}
        self.tree.clear()
        for f in files:
            folder = f.type == FOLDER
            data, rsrc = f.sizes()
            size = "--" if folder else f"{data + rsrc:,}"
            item = QTreeWidgetItem([f.name, size, _kind(f)])
            item.setIcon(0, icon(_icon_for(f)))
            self.tree.addTopLevelItem(item)

    # -- frame ------------------------------------------------------------
    def frame(self) -> chrome.Frame:
        title = self.path[-1] if self.path else self.volume.name
        return chrome.Frame(kind=WindowKind.DOCUMENT, title=title, hilited=self._hilited,
                            go_away=True, pressed=self._pressed)

    def content_size(self) -> tuple[int, int]:
        return CONTENT

    def _relayout(self) -> None:
        f = self.frame()
        w, h = chrome.structure_size(f, *self.content_size())
        s = chrome.shadow(f)
        self.resize(w + s, h + s)
        self.setMask(chrome.mask(f, w, h))
        self.tree.setGeometry(chrome.content_rect(f, w, h))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        f = self.frame()
        w = self.width() - chrome.shadow(f)
        h = self.height() - chrome.shadow(f)
        chrome.paint(QPainter(self), f, w, h)

    def _hit(self, x: int, y: int) -> int:
        f = self.frame()
        w = self.width() - chrome.shadow(f)
        h = self.height() - chrome.shadow(f)
        return chrome.hit(f, w, h, x, y)

    def box_rect(self, part: int):
        if part != k.wInGoAway:
            return None
        f = self.frame()
        w = self.width() - chrome.shadow(f)
        return chrome.close_box_rect(f, w)

    def set_pressed(self, part: int) -> None:
        if part != self._pressed:
            self._pressed = part
            self.update()

    # -- the close box and the title bar ----------------------------------
    def mousePressEvent(self, ev):  # noqa: N802
        self.raise_()
        if self.isWindow():
            self.activateWindow()
        else:
            self.tree.setFocus()       # on the emulated screen the focus says who's front
        self.display.update_mouse(ev.globalPosition().toPoint(), ev.modifiers(), down=True)
        part = self._hit(ev.position().toPoint().x(), ev.position().toPoint().y())
        if part == k.wInGoAway:
            self.display._start_tracker(
                BoxTracker(self.display, Future(), self, k.wInGoAway)
            ).add_done_callback(self._close_box_done)
        elif part == k.wInDrag:
            self.display._start_tracker(DragTracker(
                self.display, Future(), self, self.mac_origin(),
                self.display._drag_limit(None), self.display.input.mac_pos))

    def mouseMoveEvent(self, ev):  # noqa: N802
        self.display.update_mouse(ev.globalPosition().toPoint(), ev.modifiers(), down=None)
        t = self.display.tracker
        if isinstance(t, (BoxTracker, DragTracker)) and self._tracks(t):
            t.move(ev.globalPosition().toPoint())

    def mouseReleaseEvent(self, ev):  # noqa: N802
        self.display.update_mouse(ev.globalPosition().toPoint(), ev.modifiers(), down=False)
        t = self.display.tracker
        if isinstance(t, (BoxTracker, DragTracker)) and self._tracks(t):
            t.release(ev.globalPosition().toPoint())
        self.display.input.releases = self.display.input.presses

    def _tracks(self, t) -> bool:
        return getattr(t, "view", None) is self or getattr(t, "widget", None) is self

    def _close_box_done(self, closed) -> None:
        if closed:
            self.display.close_finder(self)

    def closeEvent(self, event):  # noqa: N802
        event.accept()
        if not self.display.shutting_down:
            self.display.close_finder(self)

    # -- activation, so the pinstripes and close box show when it's front --
    def _set_hilited(self, hilited: bool) -> None:
        if hilited != self._hilited:
            self._hilited = hilited
            self._relayout()

    def changeEvent(self, event):  # noqa: N802
        if event.type() == QEvent.Type.ActivationChange and self.isWindow():
            self._set_hilited(self.isActiveWindow())
        super().changeEvent(event)

    def _focus_changed(self, old: QWidget | None, new: QWidget | None) -> None:
        def inside(w):
            return w is not None and (w is self or self.isAncestorOf(w))
        if inside(new) and not inside(old):
            self._set_hilited(True)
        elif inside(old) and not inside(new):
            self._set_hilited(False)

    def eventFilter(self, obj, ev):  # noqa: N802
        if ev.type() == QEvent.Type.MouseButtonPress:
            self.raise_()
            if self.isWindow():
                self.activateWindow()
        return False

    # -- opening what's clicked -------------------------------------------
    def _activated(self, item: QTreeWidgetItem) -> None:
        name = item.text(0)
        now = time.monotonic()
        if name == self._last_name and now - self._opened_at < 0.4:
            return                      # a double-click arrives as two activations
        self._last_name, self._opened_at = name, now
        f = self.entries.get(name)
        if f is None:
            return
        if f.type == FOLDER:
            self.display.open_finder(self.volume, self.path + (f.name,), self.options)
            return
        self._open(f)

    def _open(self, f: MacFile) -> None:
        try:
            target = launch_target(f)
        except ValueError as e:
            self._say(str(e))
            return
        running = next((p for p in self.display.processes
                        if p.app is not None and p.app.key == target.key), None)
        if running is not None and not target.documents:
            self.display.switch_to(running)
            return
        try:
            if not target.rsrc and is_fork(target.data):
                raise ValueError(
                    f"{target.name}'s resource fork is in its data fork: it was copied "
                    "by something that didn't keep its two forks apart.")
            if not target.rsrc:
                raise ValueError(
                    f"{target.name} has no resource fork. A Mac file has to travel in a "
                    "form that keeps it: MacBinary, BinHex, AppleDouble or a disk image.")
            if not is_fork(target.rsrc):
                raise ValueError(f"{target.name}'s resource fork is damaged")
        except ValueError as e:
            self._say(str(e))
            return
        view = self.options.view
        if not view and not has_code(target) and not is_control_panel(target):
            print(f"{target.name} has no 68k code ({why_no_code(target)}), so macrt shows "
                  "its menus and windows from its resources.")
            view = True
        print(describe(target))
        for doc in target.documents:
            print(f"Opening {doc.name} with it.")
        try:
            self.display.launch(target.name, viewer_main if view else None, app=target,
                                trace=self.options.trace, memory=self.options.memory)
        except (MemoryError, ValueError) as e:
            self._say(str(e))

    def _say(self, message: str) -> None:
        self.display.show_alert(QMessageBox.Icon.Warning, "Could Not Open", message)

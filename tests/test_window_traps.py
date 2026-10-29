"""The Window Manager's traps as a program calls them: a window's title,
reference and variant, its order and highlighting, moving, sizing and
zooming it, tracking the mouse in its boxes, its update region, and
PaintOne and PaintBehind (Inside Macintosh I, the Window Manager)."""

from contextlib import nullcontext

import pytest
from guest import Guest
from test_controls import _dragging
from test_desk import byte, window
from test_dialogs import NoDisplay

from macrt.m68k import glue_controls, glue_windows
from macrt.toolbox import constants as k
from macrt.toolbox import lowmem
from macrt.toolbox.quickdraw import new_rgn
from macrt.toolbox.types import Point, Rect

IN_FRONT = 0xFFFFFFFF
STANDARD = Rect(40, 4, 300, 508)
GROWN = 150 << 16 | 280                 # what the mouse grows a window to


class Host(NoDisplay):
    """The display: the mouse let go in whichever box it was pressed in,
    and a window grown to GROWN.  What's tracked is kept."""

    def __init__(self):
        self.tracked = []

    def is_front(self, p):
        return True

    def standard_state(self, rec):
        return STANDARD

    def track_box(self, w, whit):
        self.tracked.append(whit)
        return True

    def track_grow(self, w, size_rect, pt):
        self.tracked.append(size_rect)
        return GROWN


@pytest.fixture
def g(qapp):
    g = Guest()
    g.yielding = nullcontext
    g.tb._d = Host()
    return g


def new_window(g, title: bytes, bounds=(60, 40, 200, 300), proc_id=k.zoomDocProc, ref_con=0):
    return g("NewWindow", 0, g.rect_ptr(bounds), g.ptr(bytes([len(title)]) + title), True,
             proc_id, IN_FRONT, True, ref_con)


def test_a_windows_title_reference_and_variant(g):
    w = new_window(g, b"First", ref_con=0x1234)
    title = g.ptr(bytes(256))
    g("GetWTitle", w.addr, title)
    assert g.mem.r_pstr(title) == b"First"
    g("SetWTitle", w.addr, g.ptr(b"\x06Second"))
    g("GetWTitle", w.addr, title)
    assert g.mem.r_pstr(title) == b"Second" and w.title_width > 0
    assert g("GetWRefCon", w.addr) == 0x1234
    g("SetWRefCon", w.addr, 0x55AA)
    assert g("GetWRefCon", w.addr) == 0x55AA
    assert g("GetWVariant", w.addr) == k.zoomDocProc & 0xF
    assert g("GetWVariant", new_window(g, b"Round", proc_id=k.rDocProc | 2).addr) == 2
    # NIL changes nothing and has nothing.
    g("SetWTitle", 0, g.ptr(b"\x01X"))
    g("SetWRefCon", 0, 1)
    g("GetWTitle", 0, title)
    assert g.mem.r_pstr(title) == b""
    assert g("GetWRefCon", 0) == g("GetWVariant", 0) == 0


def test_the_order_and_highlighting_of_windows(g, monkeypatch):
    changes = []
    monkeypatch.setattr(glue_windows, "front_changed", [lambda t: changes.append(1)])
    back = new_window(g, b"Back")
    front = new_window(g, b"Front", bounds=(80, 60, 220, 320))
    assert g("FrontWindow") is front and len(changes) == 2
    assert front.hilited and not back.hilited
    g("HiliteWindow", back.addr, 1)
    assert back.hilited
    g("HiliteWindow", back.addr, 0)
    assert not back.hilited
    g("ShowHide", front.addr, False)                # neither order nor highlighting changes
    assert not front.visible and front.hilited and g("FrontWindow") is back
    g("ShowHide", front.addr, True)
    assert front.visible and front.update_pending
    g("SendBehind", front.addr, 0)                  # behind all the others
    assert g("FrontWindow") is back and back.hilited and not front.hilited
    assert len(changes) == 3
    # Closing a window takes its controls with it.
    h = glue_controls.new_control(g, back, Rect(10, 10, 30, 70), b"OK", True, 0, 0, 1,
                                  k.pushButProc, 0)
    g("CloseWindow", back.addr)
    assert back not in g.process.windows and not g.heap.is_handle(h)
    assert g("FrontWindow") is front and len(changes) == 4
    for name in ("HiliteWindow", "ShowHide", "SendBehind", "CloseWindow"):
        g(name, *[0] * (1 if name == "CloseWindow" else 2))
    assert len(changes) == 4


def test_moving_sizing_and_zooming_a_window(g):
    w = new_window(g, b"Moved")
    g("MoveWindow", w.addr, 100, 80, False)
    assert (w.content.left, w.content.top) == (100, 80)
    assert (w.content.width, w.content.height) == (260, 140)
    w.update_pending = False
    g("SizeWindow", w.addr, 300, 140, False)
    assert w.content == Rect(80, 100, 220, 400) and not w.update_pending
    g("SizeWindow", w.addr, 300, 150, True)
    assert w.content == Rect(80, 100, 230, 400) and w.update_pending
    g("ZoomWindow", w.addr, k.inZoomOut, False)
    assert w.content == STANDARD and w.user_state == Rect(80, 100, 230, 400)
    g("ZoomWindow", w.addr, k.inZoomIn, False)
    assert w.content == Rect(80, 100, 230, 400)
    for name, args in (("MoveWindow", (0, 0, 0)), ("SizeWindow", (10, 10, 0)),
                       ("ZoomWindow", (k.inZoomOut, 0))):
        g(name, 0, *args)
    assert w.content == Rect(80, 100, 230, 400)


def test_tracking_the_mouse_in_a_windows_boxes(g):
    w = new_window(g, b"Boxes")
    pt = Point(50, 50)
    assert g("TrackGoAway", w.addr, pt)
    assert g("TrackBox", w.addr, pt, k.inZoomOut) and g("TrackBox", w.addr, pt, k.inZoomIn)
    assert g("GrowWindow", w.addr, pt, g.rect_ptr((60, 100, 2000, 2000))) == GROWN
    assert g.tb._d.tracked == [k.wInGoAway, k.wInZoomOut, k.wInZoomIn,
                               Rect(60, 100, 2000, 2000)]
    assert not g("TrackGoAway", 0, pt) and not g("TrackBox", 0, pt, k.inZoomIn)
    assert g("GrowWindow", 0, pt, g.rect_ptr((60, 100, 2000, 2000))) == 0
    assert len(g.tb._d.tracked) == 4


def test_a_windows_update_region(g):
    w = new_window(g, b"Update")
    g.set_port(w)
    g("ValidRect", g.rect_ptr((0, 0, 140, 260)))
    assert not w.update_pending
    rgn = new_rgn(g.heap, Rect(10, 20, 30, 60))         # local to the window
    g("InvalRgn", rgn)
    assert w.update.bbox == Rect(70, 60, 90, 100)
    g("ValidRgn", rgn)
    assert not w.update_pending


def test_dragging_a_region_with_no_port_or_none(g):
    """However the mouse moves, NIL isn't dragged, and nothing is with no
    port to drag it in."""
    g.port(64, 32)
    limit = slop = g.rect_ptr((0, 0, 32, 64))
    _dragging(g, [Point(10, 15), Point(12, 20), Point(13, 25)])
    assert g("DragGrayRgn", 0, Point(10, 15), limit, slop, k.noConstraint, 0) == 0
    rgn = new_rgn(g.heap, Rect(5, 10, 15, 20))
    _dragging(g, [Point(10, 15), Point(12, 20), Point(13, 25)])
    assert g("DragGrayRgn", rgn, Point(10, 15), limit, slop, k.noConstraint, 0) != 0
    g.mem.w32(glue_windows._the_port_var(g), 0)
    _dragging(g, [Point(10, 15), Point(12, 20), Point(13, 25)])
    assert g("DragTheRgn", rgn, Point(10, 15), limit, slop, k.noConstraint, 0) == 0


def test_paint_one_erases_a_window_and_adds_to_its_update(qapp):
    """What of the clobbered region its content shows is erased and to be
    updated; a hidden window, a region that misses it and no region at
    all change nothing, and the application isn't woken for them."""
    g = Guest(desk_top=20)
    g.tb.qd.repaint = lambda port: None         # no host windows to show it
    w = window(g, Rect(100, 100, 200, 300))
    g.system.screen.look()
    wakes, wake = [], g.process.events.wake
    g.process.events.wake = lambda: wakes.append(1) or wake()
    # With no region the desk isn't painted, nor does it take a new pattern.
    desk, brush = byte(g, 96, 300), g.system.screen.desk_brush
    g.mem.write(lowmem.DeskPattern, bytes([0xF0]) * 8)
    g("PaintOne", 0, 0)
    assert g.system.screen.desk_brush is brush
    g("PaintOne", w.addr, 0)
    g("PaintBehind", w.addr, 0)
    g("PaintOne", w.addr, new_rgn(g.heap, Rect(300, 300, 310, 320)))
    w.visible = False
    g.system.screen.moved()
    g("PaintOne", w.addr, new_rgn(g.heap, Rect(120, 120, 140, 160)))
    w.visible = True
    g.system.screen.moved()
    assert byte(g, 120, 130) == 0xFF and w.update.empty and wakes == []
    assert byte(g, 96, 300) == desk
    g("PaintOne", w.addr, new_rgn(g.heap, Rect(120, 120, 140, 160)))
    assert byte(g, 120, 130) == 0 and byte(g, 160, 130) == 0xFF
    assert w.update.bbox == Rect(120, 120, 140, 160) and wakes == [1]

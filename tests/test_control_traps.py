"""The Control Manager's traps as a program calls them, on a window of
its own: a control's settings, showing, hiding, moving and sizing it,
updating and disposing of controls, and tracking and dragging them with
the mouse (Inside Macintosh I, the Control Manager)."""

from contextlib import nullcontext

import pytest
from guest import Guest
from PyQt6.QtGui import QColor, QImage
from test_controls import _dragging

from macrt.m68k import glue_controls as gc
from macrt.resfork import Resource
from macrt.toolbox import constants as k
from macrt.toolbox import lowmem
from macrt.toolbox.qdraw import ImageSurface
from macrt.toolbox.quickdraw import new_rgn
from macrt.toolbox.types import Point, Rect
from macrt.toolbox.windows import WindowRecord, find_aux_win

CONTENT = Rect(80, 60, 140, 260)
CDEF = 0x123456                 # where a 68k CDEF of the test's own is


class Window:
    """A window with its own image, the current port."""

    def __init__(self, g):
        g.yielding = nullcontext
        self.g = g
        self.w = WindowRecord.new(g.system, g.process, g.heap, 0, CONTENT, "Controls", True,
                                  k.documentProc, True, 0)
        self.img = QImage(CONTENT.width, CONTENT.height, QImage.Format.Format_RGB32)
        self.img.fill(QColor(255, 255, 255))
        g.tb.qd.surfaces[self.w.addr] = ImageSurface(self.img, self.w.port_rect)
        g.set_port(self.w)

    def control(self, r, title=b"", value=0, min_=0, max_=1, proc_id=k.pushButProc, ref=0):
        return gc.new_control(self.g, self.w, Rect(*r), title, True, value, min_, max_,
                              proc_id, ref)

    def inked(self, r) -> bool:
        r = Rect(*r)
        return any(self.img.pixel(x, y) & 0xFFFFFF == 0
                   for y in range(r.top, r.bottom) for x in range(r.left, r.right))

    def clear(self):
        self.img.fill(QColor(255, 255, 255))

    def at(self, h, v) -> Point:
        """A point local to the window, in global coordinates."""
        return Point(v + CONTENT.top, h + CONTENT.left)


@pytest.fixture
def g(qapp):
    return Guest()


def own_cdef(g, answers):
    """A CDEF that's 68k code of the test's own: answers maps each message
    to what it returns (or to a function of its parameter), and every
    message is kept."""
    seen = []
    code = g.handle(bytes(4))

    def cdef(var, h, msg, param):
        seen.append(msg)
        answer = answers.get(msg, 0)
        return answer(param) if callable(answer) else answer

    g.procs[g.heap.deref(code)] = cdef
    return code, seen


def test_a_controls_settings(g):
    win = Window(g)
    h = win.control((10, 10, 26, 110), b"Scroll", value=5, max_=10, proc_id=k.scrollBarProc)
    g("SetControlMinimum", h, 6)
    assert (g("GetControlMinimum", h), g("GetControlValue", h)) == (6, 6)     # pinned
    g("SetControlMaximum", h, 8)
    g("SetControlValue", h, 20)
    assert (g("GetControlMaximum", h), g("GetControlValue", h)) == (8, 8)
    g("SetControlAction", h, 0x4000)
    g("SetControlReference", h, 0x12345678)
    assert g("GetControlAction", h) == 0x4000
    assert g("GetControlReference", h) == 0x12345678
    title = g.ptr(bytes(256))
    g("GetControlTitle", h, title)
    assert g.mem.r_pstr(title) == b"Scroll"
    win.clear()
    g("SetControlTitle", h, g.ptr(b"\x0cA new title!"))
    g("GetControlTitle", h, title)
    assert g.mem.r_pstr(title) == b"A new title!" and win.inked((10, 10, 26, 110))
    set_handle_size, g.heap.set_handle_size = g.heap.set_handle_size, lambda *args: False
    g("SetControlTitle", h, g.ptr(b"\x0eNo room for it"))     # no room: it stays as it was
    g.heap.set_handle_size = set_handle_size
    g("GetControlTitle", h, title)
    assert g.mem.r_pstr(title) == b"A new title!"
    button = win.control((40, 10, 56, 80), b"OK", proc_id=k.pushButProc | k.useWFont)
    assert g("GetControlVariant", button) == k.useWFont
    # NIL changes nothing and has nothing.
    for name in ("SetControlMinimum", "SetControlMaximum", "SetControlValue",
                 "SetControlAction", "SetControlReference", "HiliteControl"):
        g(name, 0, 1)
    g("SetControlTitle", 0, g.ptr(b"\x01X"))
    for name in ("GetControlMinimum", "GetControlMaximum", "GetControlValue",
                 "GetControlAction", "GetControlReference", "GetControlVariant"):
        assert g(name, 0) == 0
    g("GetControlTitle", 0, title)
    assert g.mem.r_pstr(title) == b""


def test_showing_hiding_moving_and_sizing(g):
    win = Window(g)
    h = win.control((10, 10, 30, 70), b"Push")
    assert win.inked((10, 10, 30, 70))
    g("HideControl", h)
    assert gc._ctl(g, h).vis == 0 and not win.inked((10, 10, 30, 70))
    g("HideControl", h)                                     # already hidden
    g("ShowControl", h)
    assert gc._ctl(g, h).vis == 255 and win.inked((10, 10, 30, 70))
    g("MoveControl", h, 100, 30)
    assert gc._ctl(g, h).rect == Rect(30, 100, 50, 160)
    assert not win.inked((10, 10, 30, 70)) and win.inked((30, 100, 50, 160))
    g("SizeControl", h, 80, 25)
    assert gc._ctl(g, h).rect == Rect(30, 100, 55, 180) and win.inked((50, 160, 55, 180))
    g("HideControl", h)
    g("MoveControl", h, 0, 0)                               # hidden, it stays undrawn
    assert not win.inked((0, 0, 60, 200))


def test_updating_what_a_region_covers(g):
    win = Window(g)
    win.control((10, 10, 30, 70), b"Left")
    win.control((10, 120, 30, 180), b"Right")
    win.clear()
    g("UpdateControls", win.w.addr, new_rgn(g.heap, Rect(0, 100, 50, 200)))
    assert win.inked((10, 120, 30, 180)) and not win.inked((10, 10, 30, 70))
    win.clear()
    g("UpdateControls", win.w.addr, new_rgn(g.heap, Rect(40, 0, 60, 200)))   # below them
    assert not win.inked((0, 0, 60, 200))
    g("UpdateControls", win.w.addr, 0)                      # all of them
    assert win.inked((10, 10, 30, 70))
    g("UpdateControls", 0, 0)                               # no window


def test_disposing_of_controls(g):
    win = Window(g)
    hs = [win.control((10, 10 + 40 * i, 30, 40 + 40 * i), b"C") for i in range(3)]
    assert [c.handle for c in gc.controls_of(g, win.w)] == hs[::-1]
    g("DisposeControl", hs[1])                              # from the middle of the list
    assert [c.handle for c in gc.controls_of(g, win.w)] == [hs[2], hs[0]]
    assert not g.heap.is_handle(hs[1]) and not win.inked((10, 50, 30, 80))
    g("KillControls", win.w.addr)
    assert win.w.control_list == 0 and not g.heap.is_handle(hs[0])
    g("KillControls", 0)
    # A control's colour table goes with it.
    h = win.control((10, 10, 30, 40), b"C")
    g("SetControlColor", h, g.handle(bytes(16)))
    aux = find_aux_win(g.mem, h, lowmem.AuxCtlHead)
    assert aux and g.mem.r32(lowmem.AuxCtlHead) == aux
    g("DisposeControl", h)
    assert g.mem.r32(lowmem.AuxCtlHead) != aux and not g.heap.is_handle(aux)
    # The list ends at an empty handle.
    empty = g("NewEmptyHandle", False)
    win.w.control_list = empty
    assert gc.controls_of(g, win.w) == []


def test_controls_with_no_window_or_no_room(g, monkeypatch):
    win = Window(g)
    bounds = g.rect_ptr((0, 0, 20, 60))
    assert g("NewControl", 0, bounds, g.ptr(b"\x01X"), True, 0, 0, 1, 0, 0) == 0
    assert g("GetNewControl", 128, win.w.addr) == 0         # no such CNTL
    h = win.control((0, 0, 20, 60))
    c = gc._ctl(g, h)
    c.owner = 0                                             # its window gone
    assert g("TrackControl", h, Point(5, 5), 0) == 0
    g("DragControl", h, Point(5, 5), bounds, bounds, k.noConstraint)
    gc.dispose(g, c)
    assert not g.heap.is_handle(h)
    popup = win.control((0, 0, 20, 60), proc_id=1008)
    sent = []
    monkeypatch.setattr(gc.popups, "message", lambda t, c, msg, param: sent.append(msg) or 7)
    assert g("SystemCDEF63", 0, popup, k.testCntl, 0) == 7
    assert gc.message(g, gc._ctl(g, popup), k.drawCntl, 0) == 7
    assert sent == [k.testCntl, k.drawCntl]
    gc._ctl(g, popup).owner = 0                             # with no window, none is sent
    assert gc.message(g, gc._ctl(g, popup), k.testCntl, 0) == 0
    assert g("SystemCDEF63", 0, popup, k.testCntl, 0) == 0
    assert g("SystemCDEF63", 0, 0, k.testCntl, 0) == 0 and len(sent) == 2
    monkeypatch.undo()
    # No room for the record, or for what's passed to a CDEF.
    new_handle, g.heap.new_handle = g.heap.new_handle, lambda *args, **kw: 0
    assert win.control((0, 0, 20, 60)) == 0
    g.heap.new_handle = new_handle
    errors = []

    def system_error(error_id, detail=""):
        errors.append(error_id)
        raise RuntimeError(detail)

    g.system_error, g.heap.new_ptr = system_error, lambda *args, **kw: 0
    with pytest.raises(RuntimeError, match="out of memory"), gc.scratch(g, 18):
        pass
    assert errors == [25]


def test_a_cdef_of_the_applications_own(g):
    """Its code is loaded again if it was purged; code that's only an RTS
    answers nothing."""
    g = Guest([Resource(b"CDEF", 5, bytes.fromhex("4EF9 0010 0000")),
               Resource(b"CDEF", 6, bytes.fromhex("4E75"))])
    win = Window(g)
    h = win.control((0, 0, 20, 60), proc_id=5 << 4)
    c = gc._ctl(g, h)
    g.process.heap.empty_handle(c.def_proc & 0xFFFFFF)
    g.calls.clear()
    gc.message(g, c, k.testCntl, 0)
    assert g.calls and g.calls[0][0] == g.mem.r32(c.def_proc & 0xFFFFFF) & 0xFFFFFF
    rts = gc._ctl(g, win.control((0, 0, 20, 60), proc_id=6 << 4))
    g.calls.clear()
    assert gc.message(g, rts, k.testCntl, 0) == 0 and g.calls == []


def test_tracking_a_control_whose_cdef_tracks_it(g):
    """An actionProc of -1, and -1 in contrlAction: the CDEF's autoTrack
    is called all the while the mouse is in the part."""
    win = Window(g)
    code, seen = own_cdef(g, {k.testCntl: 22})
    h = win.control((10, 10, 30, 70))
    c = gc._ctl(g, h)
    c.def_proc = code
    c.action = gc.ACTION_IN_RECORD
    _dragging(g, [win.at(20, 20), win.at(21, 20), win.at(22, 20)])
    seen.clear()
    assert g("TrackControl", h, Point(20, 20), gc.ACTION_IN_RECORD) == 22
    assert seen.count(k.autoTrack) == 4 and c.hilite == 0        # each tick, and at the end


def test_tracking_with_an_action_that_hides_the_control(g):
    """An action procedure in Python, as the List Manager's is: once it's
    hidden the mouse is in no part, whatever its CDEF says, and the
    tracking ends with none.  The point it starts at is given in global
    coordinates, as some programs pass it: where the mouse is is used."""
    win = Window(g)
    code, _ = own_cdef(g, {k.testCntl: lambda pt: k.inButton * Rect(10, 10, 30, 70).contains(
        Point(pt >> 16, pt & 0xFFFF))})
    h = win.control((10, 10, 30, 70), b"Push")
    gc._ctl(g, h).def_proc = code
    _dragging(g, [win.at(20, 20), win.at(21, 20), win.at(22, 20)])
    parts = []

    def action(handle, part):
        parts.append(part)
        g("HideControl", handle)

    assert gc.TrackControl(g, h, win.at(20, 20), action) == 0
    assert parts == [k.inButton]


def test_dragging_a_thumb_out_of_its_slop(g):
    win = Window(g)
    h = win.control((10, 10, 26, 150), value=0, max_=10, proc_id=k.scrollBarProc)
    thumb = gc.controls.Geometry(gc._ctl(g, h)).thumb
    start = Point((thumb.top + thumb.bottom) // 2, (thumb.left + thumb.right) // 2)
    assert gc._test(g, gc._ctl(g, h), start) == k.inThumb
    _dragging(g, [win.at(start.h, start.v), win.at(start.h + 30, start.v + 100)])
    assert g("TrackControl", h, start, 0) == 0
    assert g("GetControlValue", h) == 0
    # A CDEF that drags the indicator itself.
    code, seen = own_cdef(g, {k.testCntl: k.inThumb, k.dragCntl: 1})
    gc._ctl(g, h).def_proc = code
    _dragging(g, [win.at(start.h, start.v)])
    assert g("TrackControl", h, start, 0) == k.inThumb
    assert k.dragCntl in seen and k.thumbCntl not in seen


def test_dragging_a_control(g):
    win = Window(g)
    h = win.control((10, 10, 30, 70), b"Drag")
    limit, slop = g.rect_ptr((0, 0, 60, 200)), g.rect_ptr((0, 0, 60, 200))
    _dragging(g, [win.at(20, 20), win.at(30, 25), win.at(50, 30)])
    g("DragControl", h, Point(20, 20), limit, slop, k.noConstraint)
    assert gc._ctl(g, h).rect == Rect(20, 40, 40, 100)
    assert win.inked((20, 40, 40, 100)) and not win.inked((10, 10, 20, 40))
    _dragging(g, [win.at(50, 30), win.at(300, 30)])         # let go out of the slop
    g("DragControl", h, Point(30, 50), limit, slop, k.noConstraint)
    assert gc._ctl(g, h).rect == Rect(20, 40, 40, 100)
    # One whose CDEF drags it itself doesn't move here.
    code, seen = own_cdef(g, {k.dragCntl: 1})
    gc._ctl(g, h).def_proc = code
    _dragging(g, [win.at(20, 20), win.at(50, 30)])
    g("DragControl", h, Point(20, 20), limit, slop, k.noConstraint)
    assert gc._ctl(g, h).rect == Rect(20, 40, 40, 100) and seen == [k.dragCntl]

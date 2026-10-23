"""The desk's pattern: the binary DeskPattern, or with Color QuickDraw the
pixel pattern DeskCPat (Inside Macintosh V, the Window Manager), which
PaintOne with no window paints the desk in (Desktop Patterns)."""

from macrt.resfork import Resource
from macrt.toolbox import lowmem
from macrt.toolbox.quickdraw import new_rgn
from macrt.toolbox.screen import DESK
from macrt.toolbox.types import Rect
from macrt.toolbox.windows import WindowRecord

from guest import Guest
from test_cport import BLACK, BLUE, RED, STRIPES, WHITE, argb, ppat, screen_colors

STRIPED = bytes([0xF0]) * 8


def byte(g, h, v) -> int:
    """The screen buffer's byte with pixel (h, v), on a 1-bit screen."""
    bits = g.system.screen_bits
    return g.mem.r8(bits.base + v * bits.row_bytes + h // 8)


def test_paint_one_with_no_window_paints_the_desk_in_desk_pattern(qapp):
    g = Guest(desk_top=20)
    g.system.screen.look()
    assert byte(g, 96, 100) == DESK[100 % 8]
    g.mem.write(lowmem.DeskPattern, STRIPED)
    g("PaintOne", 0, new_rgn(g.heap, Rect(96, 96, 104, 128)))
    assert all(byte(g, h, v) == 0xF0 for v in range(96, 104) for h in range(96, 128, 8))
    assert byte(g, 96, 104) == DESK[104 % 8] and byte(g, 128, 100) == DESK[100 % 8]
    bar = byte(g, 96, 5)
    g("PaintOne", 0, new_rgn(g.heap, Rect(0, 0, 480, 640)))
    assert byte(g, 96, 5) == bar and byte(g, 128, 100) == 0xF0  # the bar isn't desk


def test_set_desk_c_pat_paints_the_desk_in_a_pixel_pattern(qapp):
    g = Guest([Resource(b"ppat", 16, ppat(STRIPES, [WHITE, RED, BLUE, BLACK]))], model="ii")
    misc = g.mem.r8(lowmem.SPMisc2)
    h = g("GetPixPat", 16)
    g("SetDeskCPat", h)
    assert g.mem.r32(lowmem.DeskCPat) == h and g.mem.r8(lowmem.SPMisc2) == misc | 0x80
    red, blue = (g.system.devices.nearest(argb(c)) for c in (RED, BLUE))
    r = Rect(200, 200, 204, 208)
    assert screen_colors(g, r) == [[red] * 8, [blue] * 8] * 2
    # With the pixel pattern in use, PaintOne paints in it, not DeskPattern.
    g.mem.write(lowmem.DeskPattern, STRIPED)
    g("PaintOne", 0, new_rgn(g.heap, Rect(200, 200, 204, 208)))
    assert screen_colors(g, r) == [[red] * 8, [blue] * 8] * 2
    g("SetDeskCPat", 0)                                         # back to the binary one
    assert g.mem.r8(lowmem.SPMisc2) == misc & 0x7F
    black, white = argb(BLACK), argb(WHITE)
    assert screen_colors(g, r) == [[black] * 4 + [white] * 4] * 4


def window(g, bounds: Rect) -> WindowRecord:
    """A new window, in front, painted black and with nothing to update."""
    w = WindowRecord.new(g.system, g.process, g.heap, 0, bounds, "", True, 0, False, 0)
    w.next_window = g.process.windows.head
    g.process.windows.head = w.addr
    g.system.screen.moved()
    g("SetPort", w.addr)
    g("PaintRect", g.rect_ptr((0, 0, 100, 200)))
    w.update_pending = False
    return w


def test_paint_behind_erases_the_windows_from_one_and_adds_to_their_updates(qapp):
    """PaintBehind calls PaintOne for the window it names and each behind
    it (Inside Macintosh I, the Window Manager): what of the region each
    one's content has uncovered is erased and to be updated.  The windows
    in front of it are left alone."""
    g = Guest(desk_top=20)
    g.tb.qd.repaint = lambda port: None         # no host windows to show it
    back = window(g, Rect(100, 100, 200, 300))
    front = window(g, Rect(60, 264, 160, 464))
    g.system.screen.look()
    clobbered = Rect(120, 120, 140, 400)
    g("PaintBehind", back.addr, new_rgn(g.heap, clobbered))
    assert byte(g, 120, 130) == 0 and byte(g, 120, 140) == 0xFF     # behind: erased
    assert back.update.bbox == Rect(120, 120, 140, 264)             # what's uncovered of it
    assert byte(g, 264, 130) == 0xFF and front.update.empty         # in front: as it was
    g("PaintBehind", front.addr, new_rgn(g.heap, clobbered))
    assert byte(g, 264, 130) == 0 and front.update.bbox == Rect(120, 264, 140, 400)

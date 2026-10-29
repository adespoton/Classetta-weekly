"""A program's cursor as the host's pointer: SetCursor, HideCursor and the
rest, and Color QuickDraw's colour cursors (Inside Macintosh I-146,
V-62, V-75)."""

import struct

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor

from macrt.m68k.glue_cport import CCRSR_SIZE, newCrsr
from macrt.resfork import Resource
from macrt.toolbox import cursors
from macrt.toolbox.color import color_table
from macrt.toolbox.gdevice import PIXMAP_SIZE, PixMap, deref
from macrt.toolbox.types import Point

from conftest import Recorder
from guest import Guest, Room

WHITE, BLACK, RED = (0xFFFF, 0xFFFF, 0xFFFF), (0, 0, 0), (0xFFFF, 0, 0)
CLEAR = (0, 0, 0, 0)


def cursor(data, mask, hot=(0, 0)) -> bytes:
    return struct.pack(">16H16Hhh", *data, *mask, *hot)


def pixel(shape, h, v) -> tuple:
    at = 4 * (16 * v + h)
    return tuple(shape.rgba[at:at + 4])


# A box: a black edge round white, the mask all of it; and, outside the
# mask, a black pixel (which inverts) at the right of row 0.
BOX = cursor([0xFF01] + [0x8100] * 6 + [0xFF00] + [0] * 8,
             [0xFF00] * 8 + [0] * 8, (3, 20))


def test_a_cursors_pixels():
    shape = cursors.mono(BOX)
    assert len(shape.rgba) == 16 * 16 * 4
    assert pixel(shape, 0, 0) == (0, 0, 0, 255)            # data and mask: black
    assert pixel(shape, 1, 1) == (255, 255, 255, 255)      # mask alone: white
    assert pixel(shape, 15, 0) == (0, 0, 0, 255)           # data alone inverts: black
    assert pixel(shape, 9, 9) == CLEAR                      # neither: what's under it
    assert shape.hot == Point(3, 15)                        # in the cursor


def test_the_standard_arrow_is_the_hosts():
    assert cursors.mono(cursors.ARROW) is None


@pytest.fixture
def g(qapp):
    return Guest(model="ii")


def test_set_hide_show_and_init_cursor(g):
    proc = g.process
    g("SetCursor", g.ptr(BOX))
    assert proc.cursor == proc.cursor_shown == cursors.mono(BOX)
    g("HideCursor")
    g("HideCursor")
    assert proc.cursor_shown == cursors.HIDDEN
    g("ShowCursor")
    assert proc.cursor_shown == cursors.HIDDEN               # still a level down
    g("ShowCursor")
    assert proc.cursor_shown == cursors.mono(BOX)
    g("HideCursor")
    g("InitCursor")                                         # the arrow, and shown
    assert proc.cursor is proc.cursor_shown is None


def crsr(pixels: bytes, colors, one_bit: bytes) -> bytes:
    """A 'crsr' of 16 by 16 pixels of 2 bits: the CCrsr, its PixMap, the
    pixels and the colour table (Inside Macintosh V-78)."""
    map_at = CCRSR_SIZE
    data_at = map_at + PIXMAP_SIZE
    table_at = data_at + len(pixels)
    head = struct.pack(">HLLLhL", newCrsr, map_at, data_at, 0, 0, 0) + one_bit + bytes(8)
    pm = struct.pack(">LH4hhhlllhhhhlLL", 0, 0x8004, 0, 0, 16, 16, 0, 0, 0, 72 << 16,
                     72 << 16, 0, 2, 1, 2, 0, table_at, 0)
    return head + pm + pixels + color_table(colors)


def test_a_colour_cursor(qapp):
    # Rows of red (pixel value 2) inside the mask, white (0) and black (3)
    # outside it, all from a 'crsr'.
    pixels = (b"\xAA\xAA\x00\x00" * 8 + b"\x00\x00\xFF\xFF" * 8)
    colors = [WHITE, BLACK, RED, BLACK]
    g = Guest([Resource(b"crsr", 128, crsr(pixels, colors, BOX))], model="ii")
    assert g("GetCCursor", 129) == 0
    h = g("GetCCursor", 128)
    p = deref(g.mem, h)
    assert g.mem.r16(p) == newCrsr and g.mem.read(p + 0x14, 68) == BOX
    pm_h, data_h, x_h = struct.unpack(">LLL", g.mem.read(p + 2, 12))
    assert g.contents(data_h) == pixels and g.contents(x_h) == b""
    pm = PixMap(g.mem, deref(g.mem, pm_h))
    assert (pm.base_addr, pm.pixel_size) == (0, 2)
    assert g.contents(pm.pm_table) == color_table(colors)

    g("SetCCursor", h)
    shape = g.process.cursor_shown
    assert pixel(shape, 0, 0) == (255, 0, 0, 255)           # in the mask: red
    assert pixel(shape, 9, 0) == pixel(shape, 0, 9) == CLEAR    # outside it, white: clear
    assert pixel(shape, 9, 9) == (0, 0, 0, 255)             # outside it, black: inverts
    assert shape.hot == Point(3, 15)

    g.system.depth = 1                                      # its 1-bit cursor, on 1 bit
    g("SetCCursor", h)
    assert g.process.cursor_shown == cursors.mono(BOX)
    g("DisposeCCursor", h)
    assert g.process.cursor_shown == cursors.mono(BOX)      # still shown


def test_get_c_cursor_with_no_room_gives_back_what_it_made(qapp, monkeypatch):
    pixels = b"\xAA\xAA\x00\x00" * 16
    g = Guest([Resource(b"crsr", 128, crsr(pixels, [WHITE, BLACK, RED, BLACK], BOX)),
               Resource(b"crsr", 130, crsr(pixels, [WHITE, BLACK, RED, BLACK], BOX)[:90])],
              model="ii")
    assert g("GetCCursor", 130) == 0                    # shorter than a CCrsr
    assert g("GetCCursor", 128)                         # and now the resource is in memory
    room = Room(monkeypatch, g)
    for blocks in range(20):
        room.limit(blocks)
        h = g("GetCCursor", 128)
        if h:
            break
        assert room.given_back()
    assert blocks == 7 and g.contents(struct.unpack(">L", g.mem.read(deref(g.mem, h) + 6, 4))[0]) \
        == pixels


def test_set_and_dispose_c_cursor_pass_over_nil_and_what_isnt_a_handle(g):
    g("SetCursor", g.ptr(BOX))
    for h in (0, g.mem.size - 2):
        g("SetCCursor", h)
        g("DisposeCCursor", h)
    assert g.process.cursor_shown == cursors.mono(BOX)


def test_the_screen_shows_the_front_programs_cursor(harness):
    h = harness()
    proc = h.launch(Recorder("App"))
    d, screen = h.d, h.d.screen_widget
    shape = cursors.mono(BOX)
    d.set_cursor(proc, shape)
    assert screen.cursor().shape() == Qt.CursorShape.BitmapCursor
    assert screen.cursor().hotSpot() == QPoint(15, 3)
    image = screen.cursor().pixmap().toImage()
    assert image.pixelColor(1, 1) == QColor(255, 255, 255)
    assert image.pixelColor(9, 9).alpha() == 0
    assert d.global_bar.cursor().shape() == Qt.CursorShape.ArrowCursor
    d.set_cursor(proc, cursors.HIDDEN)
    assert screen.cursor().shape() == Qt.CursorShape.BlankCursor
    d.set_cursor(proc, None)
    assert screen.cursor().shape() == Qt.CursorShape.ArrowCursor

    d.set_cursor(proc, shape)
    proc.cursor_obscured = True
    d.obscure_cursor(proc)                  # hidden till the mouse moves
    assert screen.cursor().shape() == Qt.CursorShape.BlankCursor
    h.move(100, 100)
    h.move(110, 120)
    assert screen.cursor().shape() == Qt.CursorShape.BitmapCursor
    assert not proc.cursor_obscured


def test_a_desktop_window_has_its_programs_cursor(harness):
    h = harness(host="desktop")
    proc = h.launch(Recorder("App"))
    view = h.d.views[proc.windows[0]]
    h.d.set_cursor(proc, cursors.HIDDEN)
    assert view.cursor().shape() == Qt.CursorShape.BlankCursor

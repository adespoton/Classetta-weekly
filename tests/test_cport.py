"""Color QuickDraw's cGrafPorts, pixel maps and pixel patterns, and the
Window Manager's colour windows (Inside Macintosh V-49 to V-79, V-197 to
V-212)."""

import struct

import pytest

from macrt.m68k import glue_controls
from macrt.m68k.glue_cport import STANDARD_CCTB, STANDARD_WCTB
from macrt.resfork import Resource
from macrt.toolbox import lowmem
from macrt.toolbox.color import color_rgb, color_table
from macrt.toolbox.constants import pushButProc, redColor
from macrt.toolbox.gdevice import (PIXMAP_SIZE, PixMap, PixPat, RGBPat, deref, device_pixmap,
                                   oldPat, pixPat, write_pixmap)
from macrt.toolbox.quickdraw import BLACK_PAT, GRAY_PAT, LT_GRAY_PAT, WHITE_PAT, GrafPort
from macrt.toolbox.types import Rect
from macrt.toolbox.windows import WindowRecord, find_aux_win

from builders import wind
from conftest import Recorder
from guest import Guest
from test_dialogs import NoDisplay

WHITE, BLACK = (0xFFFF, 0xFFFF, 0xFFFF), (0, 0, 0)
RED, BLUE = (0xFFFF, 0, 0), (0, 0, 0xFFFF)


@pytest.fixture
def g(qapp):
    return Guest(model="ii")


def rgb(g, *c) -> int:
    return g.ptr(struct.pack(">HHH", *c))


def read_rgb(g, p) -> tuple:
    return struct.unpack(">HHH", g.mem.read(p, 6))


def argb(c) -> int:
    r, gr, b = c
    return 0xFF000000 | (r >> 8) << 16 | (gr >> 8) << 8 | b >> 8


def cport(g) -> GrafPort:
    """A new cGrafPort, the current port."""
    p = g.ptr(bytes(GrafPort.SIZE))
    g("OpenCPort", p)
    return g.system.port_at(p)


def pix_pat(g, h) -> PixPat:
    return PixPat(g.mem, deref(g.mem, h))


def pixmap(g, h) -> PixMap:
    return PixMap(g.mem, deref(g.mem, h))


def screen_colors(g, rect: Rect) -> list[list[int]]:
    """The screen's pixels in rect, as colours."""
    bits, table = g.system.screen_bits, g.system.devices.table()
    return [[table[g.mem.r8(bits.base + v * bits.row_bytes + h)]
             for h in range(rect.left, rect.right)] for v in range(rect.top, rect.bottom)]


def ppat(pixels: bytes, colors, pat1: bytes = GRAY_PAT) -> bytes:
    """A 'ppat' of 8 by 8 pixels of 2 bits: the PixPat, its PixMap, the
    pixels and the colour table (Inside Macintosh V-79)."""
    map_at = 0x1C
    data_at = map_at + PIXMAP_SIZE
    table_at = data_at + len(pixels)
    head = struct.pack(">HLLLhL", pixPat, map_at, data_at, 0, -1, 0) + pat1
    pm = struct.pack(">LH4hhhlllhhhhlLL", 0, 0x8002, 0, 0, 8, 8, 0, 0, 0, 72 << 16, 72 << 16,
                     0, 2, 1, 2, 0, table_at, 0)
    return head + pm + pixels + color_table(colors)


# Rows of red and blue, in pixel values 1 and 2.
STRIPES = (b"\x55\x55" + b"\xAA\xAA") * 4


def test_open_cport_makes_a_colour_port_onto_the_current_device(g):
    port = cport(g)
    assert g.mem.r32(g.mem.r32(g.process.partition.a5)) == port.addr       # thePort
    assert g.mem.r16(port.addr + 6) & 0xC000 == 0xC000 and port.is_color
    device = device_pixmap(g.mem)
    # A copy of the device's PixMap, its colour table the device's own.
    assert g.mem.read(port.pixmap(), PIXMAP_SIZE) == g.mem.read(device, PIXMAP_SIZE)
    assert port.rgb_fg_color == BLACK and port.rgb_bk_color == WHITE
    assert port.fg_color == g("Color2Index", rgb(g, *BLACK)) != 0
    assert port.bk_color == g("Color2Index", rgb(g, *WHITE))
    for field, pat in (("bk_pix_pat", WHITE_PAT), ("pn_pix_pat", BLACK_PAT),
                       ("fill_pix_pat", BLACK_PAT)):
        pp = pix_pat(g, getattr(port, field))
        assert (pp.pat_type, pp.pat1_data) == (oldPat, pat)
    gv = deref(g.mem, port.graf_vars)
    assert g.mem.read(gv, 6) == bytes(6)                                    # rgbOpColor
    assert g.mem.read(gv + 6, 6) == g.mem.read(lowmem.HiliteRGB, 6)


def test_init_cport_resets_a_colour_port_and_leaves_a_grafport(g):
    port = cport(g)
    handles = (port.port_pix_map, port.pn_pix_pat, port.vis_rgn, port.clip_rgn)
    g("RGBForeColor", rgb(g, *RED))
    g("PenPat", g.ptr(GRAY_PAT))
    g("InitCPort", port.addr)
    assert (port.port_pix_map, port.pn_pix_pat, port.vis_rgn, port.clip_rgn) == handles
    assert port.rgb_fg_color == BLACK and port.pn_pat == BLACK_PAT
    plain, _ = g.port()
    before = g.mem.read(plain.addr, GrafPort.SIZE)
    g("InitCPort", plain.addr)
    assert g.mem.read(plain.addr, GrafPort.SIZE) == before


def test_pen_pat_and_pen_pix_pat(g):
    port = cport(g)
    own = port.pn_pix_pat
    g("PenPat", g.ptr(GRAY_PAT))                # in the port's own old-style PixPat
    assert port.pn_pix_pat == own and pix_pat(g, own).pat1_data == GRAY_PAT
    h = g("NewPixPat")
    assert pix_pat(g, h).pat_type == pixPat
    g("PenPixPat", h)
    assert port.pn_pix_pat == h and port.pn_pat.handle == h
    # PenPat then makes a new one: the pixel pattern is the application's.
    g("PenPat", g.ptr(LT_GRAY_PAT))
    assert port.pn_pix_pat not in (h, 0) and port.pn_pat == LT_GRAY_PAT
    assert pix_pat(g, h).pat1_data == GRAY_PAT
    # In a GrafPort, a pixel pattern's 1-bit pattern.
    plain, _ = g.port()
    g("BackPixPat", h)
    assert plain.bk_pat == GRAY_PAT


def test_rgb_colours_in_a_cgrafport_and_a_grafport(g):
    port = cport(g)
    orange = (0xFFFF, 0x8000, 0)
    g("RGBForeColor", rgb(g, *orange))
    assert port.rgb_fg_color == orange
    assert port.fg_color == g("Color2Index", rgb(g, *orange))
    out = g.ptr(bytes(6))
    g("GetForeColor", out)
    assert read_rgb(g, out) == orange
    g("BackColor", redColor)
    assert port.rgb_bk_color == color_rgb(redColor)
    # A GrafPort's is the classic colour of the RGB's top bits (V-68).
    plain, _ = g.port()
    g("RGBForeColor", rgb(g, 0xC000, 0x2000, 0x1000))
    assert plain.fg_color == redColor
    g("GetForeColor", out)
    assert read_rgb(g, out) == color_rgb(redColor)


def test_the_pen_state_keeps_a_pixel_pattern(g):
    port = cport(g)
    h = g("NewPixPat")
    g("PenPixPat", h)
    ps = g.ptr(bytes(18))
    g("GetPenState", ps)
    g("PenPat", g.ptr(GRAY_PAT))
    assert port.pn_pix_pat != h
    g("SetPenState", ps)
    assert port.pn_pix_pat == h
    # An old-style pattern comes back as its pattern.
    g("PenPat", g.ptr(LT_GRAY_PAT))
    g("GetPenState", ps)
    g("PenPixPat", h)
    g("SetPenState", ps)
    assert port.pn_pix_pat != h and port.pn_pat == LT_GRAY_PAT


def test_dispose_pix_pat_takes_it_out_of_the_ports_that_have_it(g):
    port = cport(g)
    h = g("NewPixPat")
    g("PenPixPat", h)
    g("BackPixPat", h)
    g("DisposePixPat", h)
    assert port.pn_pix_pat == port.bk_pix_pat == 0
    g("PenPat", g.ptr(GRAY_PAT))
    assert port.pn_pix_pat and port.pn_pat == GRAY_PAT


def test_get_pix_pat_reads_a_ppat_and_draws_it(qapp):
    colors = [WHITE, RED, BLUE, BLACK]
    g = Guest([Resource(b"ppat", 128, ppat(STRIPES, colors))], model="ii")
    assert g("GetPixPat", 129) == 0
    h = g("GetPixPat", 128)
    pp = pix_pat(g, h)
    assert (pp.pat_type, pp.pat1_data) == (pixPat, GRAY_PAT)
    assert g.contents(pp.pat_data) == STRIPES
    pm = pixmap(g, pp.pat_map)
    assert (pm.base_addr, pm.row_bytes & 0xFFFF, pm.bounds, pm.pixel_size) == \
        (0, 0x8002, Rect(0, 0, 8, 8), 2)
    assert g.contents(pm.pm_table) == color_table(colors)

    cport(g)
    r = Rect(10, 10, 14, 18)
    g("FillCRect", g.rect_ptr(r), h)
    red, blue = (g.system.devices.nearest(argb(c)) for c in (RED, BLUE))
    assert screen_colors(g, r) == [[red] * 8, [blue] * 8] * 2     # rows 10 to 13: 2, 3, 4, 5


def test_make_rgb_pat(g):
    h = g("NewPixPat")
    g("MakeRGBPat", h, rgb(g, *BLUE))
    pp = pix_pat(g, h)
    assert pp.pat_type == RGBPat
    pm = pixmap(g, pp.pat_map)
    assert (pm.bounds, pm.pixel_size) == (Rect(0, 0, 8, 8), 2)
    ct = deref(g.mem, pm.pm_table)
    assert struct.unpack(">HHHH", g.mem.read(ct + 8 + 8 * 4, 8))[1:] == BLUE
    cport(g)
    r = Rect(20, 20, 24, 30)
    g("FillCRect", g.rect_ptr(r), h)
    assert screen_colors(g, r) == [[g.system.devices.nearest(argb(BLUE))] * 10] * 4
    for color, pat in ((WHITE, WHITE_PAT), (BLACK, BLACK_PAT)):
        g("MakeRGBPat", h, rgb(g, *color))
        assert pix_pat(g, h).pat1_data == pat


def test_copy_pix_map_copies_into_the_destinations_own_colour_table(g):
    src, dst = g("NewPixMap"), g("NewPixMap")
    table = color_table([WHITE, RED, BLUE, BLACK], seed=7)
    ct = pixmap(g, src).pm_table
    assert g.heap.set_handle_size(ct, len(table))
    g.mem.write(g.heap.deref(ct), table)
    s = pixmap(g, src)
    s.bounds, s.pixel_size, s.row_bytes = Rect(0, 0, 20, 30), 2, 0x8008
    dst_table = pixmap(g, dst).pm_table
    g("CopyPixMap", src, dst)
    d = pixmap(g, dst)
    assert d.pm_table == dst_table != ct
    assert (d.bounds, d.pixel_size, d.row_bytes & 0xFFFF) == (Rect(0, 0, 20, 30), 2, 0x8008)
    assert g.contents(dst_table) == table


def offscreen(g, rows: list[bytes], table: int) -> int:
    """A new PixMap of 8-bit pixel values, rows of them, in table's colours."""
    h = g("NewPixMap")
    width = len(rows[0])
    base = g.ptr(b"".join(rows))
    write_pixmap(g.mem, deref(g.mem, h), base, width, Rect(0, 0, len(rows), width), 8, table)
    return h


def values(g, h) -> list[bytes]:
    pm = pixmap(g, h)
    rb = pm.row_bytes & 0x3FFF
    return [g.mem.read(pm.base_addr + v * rb, pm.bounds.width) for v in range(pm.bounds.height)]


def test_a_colour_port_draws_pixel_values_on_its_pixmap(g):
    """A cGrafPort's fgColor and bkColor are pixel values: on a PixMap of
    its own they're what's drawn, and what else is there stays as it
    is, whatever colours its table gives the values (here, the same to
    two of them, and two others)."""
    port = cport(g)
    table = g.handle(color_table([WHITE, BLACK, WHITE, BLACK, RED]))
    rows = [bytes([2, 3, 0, 1, 2, 3])] * 3
    h = offscreen(g, rows, table)
    g("SetPortPix", h)
    port.fg_color, port.bk_color = 4, 2                 # as Color2Index gives them
    g("PaintRect", g.rect_ptr(Rect(1, 1, 2, 3)))
    g("EraseRect", g.rect_ptr(Rect(2, 4, 3, 5)))
    g("MoveTo", 0, 0)
    g("LineTo", 5, 0)
    assert values(g, h) == [bytes([4] * 6), bytes([2, 4, 4, 1, 2, 3]),
                            bytes([2, 3, 0, 1, 2, 3])]
    out = g.ptr(bytes(6))
    g("GetCPixel", 2, 1, out)
    assert read_rgb(g, out) == RED


def test_a_pixmap_with_bounds_wider_than_its_rows_is_drawn_on_as_far_as_they_go(g):
    """Tetris draws its tiles in a PixMap whose bounds are 208 pixels
    wide on rows of 170 bytes, in no more than the first 169: drawing
    there isn't lost for want of the rest of the row."""
    port = cport(g)
    table = g.handle(color_table([WHITE, BLACK, WHITE, BLACK, RED]))
    h = offscreen(g, [bytes([2, 3, 0, 1])] * 3, table)
    pm = pixmap(g, h)
    g.mem.w_rect(pm.addr + 6, Rect(0, 0, 3, 6))
    g("SetPortPix", h)
    port.fg_color = 4
    g("PaintRect", g.rect_ptr(Rect(0, 1, 2, 3)))
    rows = [g.mem.read(pm.base_addr + v * 4, 4) for v in range(3)]
    assert rows == [bytes([2, 4, 4, 1])] * 2 + [bytes([2, 3, 0, 1])]


def test_copy_bits_between_pixmaps_of_one_colour_table_copies_pixel_values(g):
    """From a PixMap to one with the same colour table, or one whose seed
    is the same, CopyBits copies pixel values as they are, scaled, with
    no colours to match (two here are white and two black)."""
    cport(g)
    table = g.handle(color_table([WHITE, BLACK, WHITE, BLACK], seed=9))
    src = offscreen(g, [bytes([2, 3]), bytes([0, 1])], table)
    for dst_table in (table, g.handle(color_table([WHITE, BLACK, WHITE, BLACK], seed=9))):
        dst = offscreen(g, [bytes(4)] * 4, dst_table)
        g("CopyBits", deref(g.mem, src), deref(g.mem, dst), g.rect_ptr(Rect(0, 0, 2, 2)),
          g.rect_ptr(Rect(0, 0, 4, 4)), 0, 0)
        assert values(g, dst) == [bytes([2, 2, 3, 3])] * 2 + [bytes([0, 0, 1, 1])] * 2


def test_copy_bits_asks_the_search_procedures_for_a_bitmaps_black_and_white(g):
    """NetTrek draws its ships, black and white bitmaps, in each side's
    colours: its search procedure gives the port's black and white the
    pixel values it wants."""
    port = cport(g)

    def sides(p, pos):
        g.mem.w32(pos, 5 if read_rgb(g, p) == BLACK else 6)
        return True

    g.procs = {0x1000: sides}
    g("AddSearch", 0x1000)
    src = g.ptr(struct.pack(">LH4h", g.ptr(b"\xFF\x00\x00\xFF"), 2, 0, 0, 2, 16))
    r = Rect(40, 40, 42, 56)
    g("CopyBits", src, port.addr + 2, g.rect_ptr(Rect(0, 0, 2, 16)), g.rect_ptr(r), 0, 0)
    table = g.system.devices.table()
    five, six = table[5], table[6]
    assert screen_colors(g, r) == [[five] * 8 + [six] * 8, [six] * 8 + [five] * 8]


def test_a_colour_port_draws_in_its_rgb_colours(g):
    cport(g)
    g("RGBForeColor", rgb(g, *RED))
    g("RGBBackColor", rgb(g, *BLUE))
    red, blue = (g.system.devices.nearest(argb(c)) for c in (RED, BLUE))
    r = Rect(30, 30, 33, 40)
    g("PaintRect", g.rect_ptr(r))
    assert screen_colors(g, r) == [[red] * 10] * 3
    g("EraseRect", g.rect_ptr(r))
    assert screen_colors(g, r) == [[blue] * 10] * 3

    g("SetCPixel", 32, 31, rgb(g, *RED))
    assert screen_colors(g, Rect(31, 31, 32, 34)) == [[blue, red, blue]]
    out = g.ptr(bytes(6))
    g("GetCPixel", 32, 31, out)
    assert argb(read_rgb(g, out)) == red


def test_colour_windows_auxiliary_records(g):
    w = WindowRecord.new(g.system, g.process, g.heap, 0, Rect(40, 40, 100, 200), "Colour",
                         True, 0, False, 0, color=True)
    assert w.is_color
    pp = g.ptr(bytes(4))
    assert not g("GetAuxWin", w.addr, pp)               # the default's
    default = g.mem.r32(pp)
    assert g("GetAuxWin", 0, pp) and g.mem.r32(pp) == default
    assert g.contents(g.mem.r32(deref(g.mem, default) + 8)) == color_table(STANDARD_WCTB)

    lilac = (0x8000, 0x8000, 0xFFFF)
    wctb = g.handle(color_table([lilac, BLACK, BLACK, BLACK, WHITE]))
    g("SetWinColor", w.addr, wctb)
    assert g("GetAuxWin", w.addr, pp)
    aux = g.mem.r32(pp)
    assert aux == g.mem.r32(lowmem.AuxWinHead) != default
    assert g.mem.r32(deref(g.mem, aux) + 4) == w.addr
    assert g.mem.r32(deref(g.mem, aux) + 8) == wctb
    assert w.rgb_bk_color == lilac                      # its content colour
    # The default's colours: no record of its own.
    g("SetWinColor", w.addr, g.handle(color_table(STANDARD_WCTB)))
    assert not g("GetAuxWin", w.addr, pp) and g.mem.r32(pp) == default
    # Closing the window disposes of its record.
    g("SetWinColor", w.addr, wctb)
    assert find_aux_win(g.mem, w.addr)
    w.close()
    assert not find_aux_win(g.mem, w.addr) and find_aux_win(g.mem, 0) == default


def test_get_new_c_window_shows_its_content_in_its_content_colour(qapp):
    """A window coloured by the 'wctb' of its ID is shown with its content
    in its content colour; one without, in white."""
    lilac = (0x8000, 0x8000, 0xFFFF)
    g = Guest([Resource(b"WIND", 128, wind((40, 40, 100, 200), "Lilac")),
               Resource(b"wctb", 128, color_table([lilac, BLACK, BLACK, BLACK, WHITE])),
               Resource(b"WIND", 129, wind((40, 40, 100, 200), "White")),
               Resource(b"WIND", 130, wind((40, 40, 100, 200), "Hidden", visible=False)),
               Resource(b"wctb", 130, color_table([lilac, BLACK, BLACK, BLACK, WHITE]))],
              model="ii")
    g.tb._d = NoDisplay()
    paper = g.system.devices.nearest(argb(lilac))
    for rid, visible, content in ((128, True, paper), (129, True, argb(WHITE)),
                                  (130, False, argb(WHITE))):
        w = g("GetNewCWindow", rid, 0, -1)
        assert w.is_color and w.visible == visible
        assert w.backing.image.pixel(10, 10) | 0xFF000000 == content
    g("ShowWindow", w.addr)
    assert w.backing.image.pixel(10, 10) | 0xFF000000 == paper


def test_controls_auxiliary_records(g):
    """GetAuxCtl and SetCtlColor, as GetAuxWin and SetWinColor, with a list
    of their own: BMAPEdit's own CDEF asks for its controls' colours."""
    w = WindowRecord.new(g.system, g.process, g.heap, 0, Rect(40, 40, 100, 200), "Colour",
                         True, 0, False, 0, color=True)
    h = glue_controls.new_control(g, w, Rect(10, 10, 30, 90), b"OK", False, 0, 0, 1,
                                  pushButProc, 0)
    pp = g.ptr(bytes(4))
    assert not g("GetAuxiliaryControlRecord", h, pp)    # the default's
    default = g.mem.r32(pp)
    assert g("GetAuxiliaryControlRecord", 0, pp) and g.mem.r32(pp) == default
    assert g.contents(g.mem.r32(deref(g.mem, default) + 8)) == color_table(STANDARD_CCTB)
    cctb = g.handle(color_table([RED, WHITE, BLACK, WHITE]))
    g("SetControlColor", h, cctb)
    assert g("GetAuxiliaryControlRecord", h, pp)
    aux = g.mem.r32(pp)
    assert aux == g.mem.r32(lowmem.AuxCtlHead) != default
    assert g.mem.r32(deref(g.mem, aux) + 4) == h
    assert g.mem.r32(deref(g.mem, aux) + 8) == cctb
    assert not find_aux_win(g.mem, h)                   # not a window's
    g("SetControlColor", h, g.handle(color_table(STANDARD_CCTB)))
    assert not g("GetAuxiliaryControlRecord", h, pp) and g.mem.r32(pp) == default
    # Disposing of the control disposes of its record.
    g("SetControlColor", h, cctb)
    assert find_aux_win(g.mem, h, lowmem.AuxCtlHead)
    g("DisposeControl", h)
    assert not find_aux_win(g.mem, h, lowmem.AuxCtlHead)
    assert find_aux_win(g.mem, 0, lowmem.AuxCtlHead) == default


def test_the_window_manager_has_a_colour_port(g):
    pp = g.ptr(bytes(4))
    g("GetCWMgrPort", pp)
    p = g.mem.r32(pp)
    assert p == g.mem.r32(lowmem.WMgrCPort) and p != g.mem.r32(lowmem.WMgrPort)
    assert g.system.port_at(p).is_color


def test_a_picture_in_a_colour_port_leaves_its_colours_and_patterns(g):
    port = cport(g)
    rect = struct.pack(">4h", 2, 2, 8, 8)
    pic = (struct.pack(">h4h", 0, 0, 0, 10, 10) + b"\x11\x01" + b"\x0E"
           + struct.pack(">l", redColor) + b"\x09" + GRAY_PAT + b"\x31" + rect + b"\xFF")
    h = g.handle(pic)
    pn = port.pn_pix_pat
    g("DrawPicture", h, g.rect_ptr((50, 50, 60, 60)))
    red = g.system.devices.nearest(argb(color_rgb(redColor)))
    rows = screen_colors(g, Rect(52, 52, 58, 58))
    assert {c for row in rows for c in row} <= {red, g.system.devices.nearest(argb(WHITE))}
    assert red in rows[0]
    assert port.rgb_fg_color == BLACK and port.pn_pix_pat == pn and port.pn_pat == BLACK_PAT


def test_a_picture_recorded_in_a_colour_port_keeps_its_colours_and_pixel_patterns(qapp):
    """OpenPicture in a cGrafPort records version 2: RGBFgColor, PnPixPat
    and FillPixPat, played back in their colours."""
    g = Guest([Resource(b"ppat", 128, ppat(STRIPES, [WHITE, RED, BLUE, BLACK]))], model="ii")
    cport(g)
    stripes, blue = g("GetPixPat", 128), g("NewPixPat")
    g("MakeRGBPat", blue, rgb(g, *BLUE))
    pic = g("OpenPicture", g.rect_ptr((0, 0, 16, 16)))
    g("RGBForeColor", rgb(g, *RED))
    g("PaintRect", g.rect_ptr((0, 0, 4, 8)))
    g("FillCRect", g.rect_ptr((4, 0, 8, 8)), stripes)
    g("PenPixPat", blue)
    g("PaintRect", g.rect_ptr((8, 0, 12, 8)))
    g("ClosePicture")
    data = g.contents(pic)
    assert data[10:14] == b"\x00\x11\x02\xff"
    ops = data[38:]
    for op in (b"\x00\x1a", b"\x00\x13\x00\x02", b"\x00\x14\x00\x01"):
        assert op in ops

    g("RGBForeColor", rgb(g, *BLACK))
    g("PenPat", g.ptr(BLACK_PAT))
    g("EraseRect", g.rect_ptr((0, 0, 100, 100)))
    g("DrawPicture", pic, g.rect_ptr((40, 40, 56, 56)))
    red, blue_value = (g.system.devices.nearest(argb(c)) for c in (RED, BLUE))
    assert screen_colors(g, Rect(40, 40, 44, 48)) == [[red] * 8] * 4
    assert screen_colors(g, Rect(44, 40, 48, 48)) == [[red] * 8, [blue_value] * 8] * 2
    assert screen_colors(g, Rect(48, 40, 52, 48)) == [[blue_value] * 8] * 4


class ColourRecorder(Recorder):
    def new_window(self):
        return self.tb.NewWindow(Rect.from_xywh(60, 60, 200, 120), "Colour", True, color=True)


def test_new_cwindow_draws_in_colour_on_the_screen(harness):
    h = harness(model="ii", depth=8)
    rec = ColourRecorder("Colour")
    h.launch(rec)
    system = h.d.system
    w = rec.tb.FrontWindow()
    assert w.is_color
    red = system.devices.nearest(argb(RED))
    with system.lock:
        rec.tb.SetPort(w)
        rec.tb.qd.set_rgb_color(w, True, RED)
        rec.tb.PaintRect(Rect(10, 20, 14, 36))
    bits, table = system.screen_bits, system.devices.table()
    c = w.content
    at = bits.base + (c.top + 12) * bits.row_bytes + c.left
    assert all(table[system.mem.r8(at + x)] == red for x in range(20, 36))
    with w.backing.lock:
        assert w.backing.image.pixel(25, 12) | 0xFF000000 == red


def test_save_and_restore_the_colours(g):
    """SaveFore and SaveBack keep the port's colours in a ColorSpec, and
    RestoreFore and RestoreBack set them again."""
    port = cport(g)
    orange, navy = (0xFFFF, 0x8000, 0), (0, 0, 0x8000)
    g("RGBForeColor", rgb(g, *orange))
    g("RGBBackColor", rgb(g, *navy))
    fore, back = g.ptr(b"\xff" * 8), g.ptr(b"\xff" * 8)
    g("SaveFore", fore)
    g("SaveBack", back)
    assert g.mem.read(fore, 8) == struct.pack(">4H", 0, *orange)
    assert g.mem.read(back, 8) == struct.pack(">4H", 0, *navy)
    g("ForeColor", redColor)
    g("BackColor", redColor)
    g("RestoreFore", fore)
    g("RestoreBack", back)
    assert (port.rgb_fg_color, port.rgb_bk_color) == (orange, navy)


def test_op_color_is_kept_in_the_graf_vars_for_the_arithmetic_modes(g):
    """OpColor sets a cGrafPort's rgbOpColor, addPin's ceiling: CopyBits
    in addPin from red on blue gives magenta up to it, and in addMax the
    greater of each component, between PixMaps with no colours in common
    but these."""
    port = cport(g)
    g("OpColor", rgb(g, 0xFFFF, 0, 0xFFFF))
    assert read_rgb(g, deref(g.mem, port.graf_vars)) == (0xFFFF, 0, 0xFFFF)
    table = g.handle(color_table([WHITE, BLACK, RED, BLUE, (0xFFFF, 0, 0xFFFF)]))
    src = offscreen(g, [bytes([2, 2])], table)
    for mode in (33, 37):                                       # addPin, addMax
        dst = offscreen(g, [bytes([3, 1])], table)
        g("CopyBits", deref(g.mem, src), deref(g.mem, dst), g.rect_ptr(Rect(0, 0, 1, 2)),
          g.rect_ptr(Rect(0, 0, 1, 2)), mode, 0)
        assert values(g, dst) == [bytes([4, 2])]
    g.port()
    g("OpColor", rgb(g, *RED))                                  # no effect in a GrafPort
    assert read_rgb(g, deref(g.mem, port.graf_vars)) == (0xFFFF, 0, 0xFFFF)

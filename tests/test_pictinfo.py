"""The Picture Utilities (Imaging With QuickDraw, Pictures, "Collecting
Picture Information"): what GetPictInfo and GetPixMapInfo find in a
picture or pixel map, the colours they pick, and surveys of several."""

import struct
from collections import Counter

import pytest

from macrt.m68k.glue_pictinfo import PICT_INFO
from macrt.toolbox import pict
from macrt.toolbox.gdevice import deref
from macrt.toolbox.pictutil import WIDEN, Survey, medianMethod, popularMethod
from macrt.toolbox.qdraw import srcCopy

from guest import Guest
from test_pict import rect, v2

returnColorTable, returnPalette, recordComments, recordFontInfo = 1, 2, 4, 8
suppressBlackAndWhite = 16
WHITE, BLACK = (0xFFFF, 0xFFFF, 0xFFFF), (0, 0, 0)
RED, GREEN, BLUE = (0xFFFF, 0, 0), (0, 0x8000, 0), (0, 0, 0xFFFF)
FIELDS = ("version", "uniqueColors", "thePalette", "theColorTable", "hRes", "vRes", "depth",
          "top", "left", "bottom", "right", "textCount", "lineCount", "rectCount",
          "rRectCount", "ovalCount", "arcCount", "polyCount", "regionCount", "bitMapCount",
          "pixMapCount", "commentCount", "uniqueComments", "commentHandle", "uniqueFonts",
          "fontHandle", "fontNamesHandle", "reserved1", "reserved2")


@pytest.fixture
def g(qapp):
    return Guest(model="ii")


def info_of(g, p) -> dict:
    return dict(zip(FIELDS, PICT_INFO.unpack(g.mem.read(p, PICT_INFO.size))))


def ctab_colors(g, h) -> list[tuple]:
    p = deref(g.mem, h)
    n = g.mem.r16s(p + 6) + 1
    return [struct.unpack_from(">HHH", g.mem.read(p + 8 + 8 * i + 2, 6)) for i in range(n)]


def pixmap_op(colors, rows) -> tuple:
    """A PackBitsRect of an 8-bit pixel map: rows of pixel values, by a
    table of colours."""
    width, height = len(rows[0]), len(rows)
    ctab = struct.pack(">lHh", 0, 0, len(colors) - 1) + b"".join(
        struct.pack(">HHHH", i, *c) for i, c in enumerate(colors))
    pixmap = struct.pack(">hhlllhhhhlll", 0, 0, 0, 72 << 16, 72 << 16, 0, 8, 1, 8, 0, 0, 0)
    packed = b"".join(bytes([len(p)]) + p for p in (pict.pack_bits(bytes(r)) for r in rows))
    return (0x0098, struct.pack(">H", 0x8000 | width) + rect(0, 0, height, width) + pixmap
            + ctab + rect(0, 0, height, width) + rect(0, 0, height, width)
            + struct.pack(">h", srcCopy) + packed)


def picture(g) -> int:
    """Red and blue pixels, 40 and 24 of them, a green foreground colour,
    a rectangle, an oval, two lines, bold 9-point Geneva text and two of
    one kind of comment."""
    rows = [[1] * 10 + [2] * 6] * 4
    name = b"\x06Geneva"
    data = v2((0, 0, 4, 16), pixmap_op([WHITE, RED, BLUE], rows),
              (0x001A, struct.pack(">HHH", *GREEN)),
              (0x0030, rect(0, 0, 2, 2)), (0x0050, rect(0, 0, 2, 2)),
              (0x0020, struct.pack(">hhhh", 0, 0, 3, 3)), (0x0021, struct.pack(">hh", 1, 1)),
              (0x002C, struct.pack(">Hh", 2 + len(name), 3) + name),
              (0x0003, struct.pack(">h", 3)), (0x0004, b"\x01"), (0x000D, struct.pack(">h", 9)),
              (0x0028, struct.pack(">hh", 3, 0) + b"\x02Hi"),
              (0x00A0, struct.pack(">h", 150)), (0x00A0, struct.pack(">h", 150)))
    return g.handle(data)


def test_get_pict_info_counts_what_a_picture_draws(g):
    info = g.ptr(bytes(PICT_INFO.size))
    verb = returnColorTable | recordComments | recordFontInfo
    assert g("GetPictInfo", picture(g), info, verb, 4, popularMethod, 0) == 0
    got = info_of(g, info)
    assert got["uniqueColors"] == 3 and got["thePalette"] == 0
    assert ctab_colors(g, got["theColorTable"]) == [RED, BLUE, GREEN, BLACK]
    assert (got["hRes"], got["vRes"], got["depth"]) == (72 << 16, 72 << 16, 8)
    assert (got["top"], got["left"], got["bottom"], got["right"]) == (0, 0, 4, 16)
    assert {k: got[k + "Count"] for k in ("text", "line", "rect", "oval", "arc", "pixMap",
                                          "bitMap", "comment")} == {
        "text": 1, "line": 2, "rect": 1, "oval": 1, "arc": 0, "pixMap": 1, "bitMap": 0,
        "comment": 2}
    assert got["uniqueComments"] == 1
    assert g.mem.read(deref(g.mem, got["commentHandle"]), 4) == struct.pack(">hh", 2, 150)
    assert got["uniqueFonts"] == 1
    spec = struct.unpack(">hh4LhL", g.mem.read(deref(g.mem, got["fontHandle"]), 26))
    assert spec[0] == 3 and spec[1] == 3
    assert spec[2:6] == (1 << 9, 0, 0, 0) and spec[6] == 1
    names = deref(g.mem, got["fontNamesHandle"])
    assert g.mem.read(names + spec[7], 7) == b"\x06Geneva"


def test_what_isnt_asked_for_is_left_nil(g):
    info = g.ptr(b"\xAA" * PICT_INFO.size)
    assert g("GetPictInfo", picture(g), info, 0, 0, 0, 0) == 0
    got = info_of(g, info)
    assert got["uniqueColors"] == 3
    assert [got[k] for k in ("thePalette", "theColorTable", "commentCount", "uniqueComments",
                             "commentHandle", "uniqueFonts", "fontHandle",
                             "fontNamesHandle")] == [0] * 8


def test_a_palette_has_the_colours_found_and_a_table_all_asked_for(g):
    info = g.ptr(bytes(PICT_INFO.size))
    assert g("GetPictInfo", picture(g), info, returnColorTable | returnPalette, 8, 0, 0) == 0
    got = info_of(g, info)
    assert len(ctab_colors(g, got["theColorTable"])) == 8
    assert g.mem.r16(deref(g.mem, got["thePalette"])) == 3


def test_an_extended_header_gives_the_resolution_and_source_rectangle(g):
    data = bytearray(v2((0, 0, 10, 20)))
    struct.pack_into(">hhll4h", data, 16, -2, 0, 144 << 16, 144 << 16, 0, 0, 20, 40)
    info = g.ptr(bytes(PICT_INFO.size))
    assert g("GetPictInfo", g.handle(bytes(data)), info, 0, 0, 0, 0) == 0
    got = info_of(g, info)
    assert (got["hRes"], got["vRes"]) == (144 << 16, 144 << 16)
    assert (got["top"], got["left"], got["bottom"], got["right"]) == (0, 0, 20, 40)
    assert got["depth"] == 1


@pytest.mark.parametrize("verb, colors, method, version, err", [
    (0, 0, 0, 1, -11000),                       # pictInfoVersionErr
    (0x20, 0, 0, 0, -11002),                    # pictInfoVerbErr
    (returnColorTable, 0, 0, 0, -11004),        # colorsRequestedErr
    (returnPalette, 257, 0, 0, -11004),
    (returnColorTable, 4, 200, 0, -11003),      # cantLoadPickMethodErr: no 'cpmt' 200
    (recordComments, 0, 200, 0, 0),             # no colours: no method
])
def test_what_get_pict_info_refuses(g, verb, colors, method, version, err):
    info = g.ptr(bytes(PICT_INFO.size))
    assert g("GetPictInfo", picture(g), info, verb, colors, method, version) == err


def test_a_picture_that_cant_be_read_is_a_picture_data_error(g):
    data = v2((0, 0, 4, 4), (0x0001, struct.pack(">H", 4)))     # a region of 4 bytes
    info = g.ptr(bytes(PICT_INFO.size))
    assert g("GetPictInfo", g.handle(data), info, 0, 0, 0, 0) == -11005


def pixmap_handle(g, base, row_bytes, bounds, depth, table=0) -> int:
    rec = struct.pack(">LH4hhhlllhhhhlLl", base, 0x8000 | row_bytes, *bounds, 0, 0, 0,
                      72 << 16, 72 << 16, 16 if depth > 8 else 0, depth,
                      3 if depth > 8 else 1, 8 if depth == 32 else 5 if depth == 16 else depth,
                      0, table, 0)
    return g.handle(rec)


def test_get_pixmap_info_reads_the_pixels_through_the_table(g):
    table = g.handle(struct.pack(">lHh", 0, 0, 1) + struct.pack(">HHHH", 0, *WHITE)
                     + struct.pack(">HHHH", 1, 0x1234, 0x5678, 0x9ABC))
    base = g.ptr(bytes([0x01, 0x11, 0x10, 0x00]))           # 7 pixels at 4 bits: 0 1 1 1 1 0 0
    pm = pixmap_handle(g, base, 4, (0, 0, 1, 7), 4, table)
    info = g.ptr(bytes(PICT_INFO.size))
    assert g("GetPixMapInfo", pm, info, returnColorTable, 2, 0, 0) == 0
    got = info_of(g, info)
    assert got["uniqueColors"] == 2 and got["pixMapCount"] == 1 and got["depth"] == 4
    assert ctab_colors(g, got["theColorTable"]) == [(0x1234, 0x5678, 0x9ABC), WHITE]


def test_a_32_bit_pixel_map_is_counted_to_5_bits_a_component(g):
    base = g.ptr(bytes([0, 0x12, 0x34, 0x56, 0, 0x13, 0x35, 0x57, 0, 0xFF, 0xFF, 0xFF]))
    pm = pixmap_handle(g, base, 12, (0, 0, 1, 3), 32)
    info = g.ptr(bytes(PICT_INFO.size))
    assert g("GetPixMapInfo", pm, info, returnColorTable, 3, 0, 0) == 0
    got = info_of(g, info)
    assert got["uniqueColors"] == 2
    assert ctab_colors(g, got["theColorTable"]) == [(WIDEN[2], WIDEN[6], WIDEN[10]), WHITE,
                                                    BLACK]


def test_a_bitmap_is_black_and_white(g):
    base = g.ptr(bytes([0xF0, 0]))
    bm = g.handle(struct.pack(">LH4h", base, 2, 0, 0, 1, 16))
    info = g.ptr(bytes(PICT_INFO.size))
    verb = returnColorTable | suppressBlackAndWhite
    assert g("GetPixMapInfo", bm, info, verb, 2, 0, 0) == 0
    got = info_of(g, info)
    assert got["uniqueColors"] == 2 and got["bitMapCount"] == 1 and got["depth"] == 1
    assert ctab_colors(g, got["theColorTable"]) == [BLACK, BLACK]       # none, all black


def test_without_color_quickdraw_there_are_no_colour_handles(qapp):
    g = Guest()
    info = g.ptr(bytes(PICT_INFO.size))
    assert g("GetPictInfo", picture(g), info, returnColorTable | returnPalette, 4, 0, 0) == 0
    got = info_of(g, info)
    assert got["uniqueColors"] == 3 and got["thePalette"] == got["theColorTable"] == 0


def test_a_survey_of_pictures_and_pixel_maps(g):
    id_p = g.ptr(bytes(4))
    verb = returnColorTable | recordComments
    assert g("NewPictInfo", id_p, verb, 4, 0, 0) == 0
    pict_id = g.mem.r32(id_p)
    pic = picture(g)
    assert g("RecordPictInfo", pict_id, pic) == 0
    assert g("RecordPictInfo", pict_id, pic) == 0
    base = g.ptr(bytes([0, 0, 0, 0xFF] * 2))
    assert g("RecordPixMapInfo", pict_id, pixmap_handle(g, base, 8, (0, 0, 1, 2), 32)) == 0
    info = g.ptr(bytes(PICT_INFO.size))
    assert g("RetrievePictInfo", pict_id, info, 5) == -11004      # more than NewPictInfo's
    assert g("RetrievePictInfo", pict_id, info, 4) == 0
    got = info_of(g, info)
    assert got["pixMapCount"] == 3 and got["rectCount"] == 2 and got["commentCount"] == 4
    assert got["depth"] == 32
    assert ctab_colors(g, got["theColorTable"])[0] == RED
    assert g("DisposePictInfo", pict_id) == 0
    assert g("RecordPictInfo", pict_id, pic) == -11001           # pictInfoIDErr
    assert g("DisposePictInfo", pict_id) == -11001


def test_the_popular_method_picks_the_colours_used_most():
    s = Survey()
    s.add_colors(Counter({RED: 1, BLUE: 5, BLACK: 9, GREEN: 3}))
    assert s.pick(2, popularMethod) == [BLACK, BLUE]
    assert s.pick(2, popularMethod, keep_black_and_white=False) == [BLUE, GREEN]


def test_the_median_method_spreads_its_colours_over_those_used():
    s = Survey()
    s.add_colors(Counter({(0, 0, 0): 1, (0x1000, 0, 0): 1, (0xF000, 0, 0): 1,
                          (0xFFFF, 0, 0): 1}))
    assert s.pick(2, medianMethod) == [(0x0800, 0, 0), (0xF800, 0, 0)]
    assert len(s.pick(4, medianMethod)) == 4


def test_more_than_256_colours_are_counted_to_5_bits():
    s = Survey()
    s.add_colors(Counter({(v << 8, 0, 0): 1 for v in range(256)}))
    assert not s.banked and len(s.colors) == 256
    s.add_colors(Counter({(0, 0, 0x0123): 1}))
    assert s.banked and len(s.colors) == 32         # 32 reds, the first black
    assert s.colors[BLACK] == 9

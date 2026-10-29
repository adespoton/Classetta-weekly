"""
Font Manager traps: fonts by name and number, outline font preferences,
FMSwapFont and FontMetrics, and the records programs read in low memory
after a swap (the output record and the global width table).
"""

from __future__ import annotations

import struct
from contextlib import contextmanager

from ..memory import from_mac
from ..toolbox import lowmem
from ..toolbox.api import CHICAGO_SYMBOLS
from ..toolbox.bitfont import font_family, font_id
from ..toolbox.memmgr import noErr
from ..toolbox.qdraw import STANDARD_FAMILIES, text_size
from .dispatch import trap
from .glue_common import _port
from .glue_resources import _rm


# =========================================================================
# Font Manager
# =========================================================================
@trap
def InitFonts(t):
    pass


def _family(t, family: int) -> int:
    """Families 0 and 1 are the system and application fonts."""
    if family == 0:
        return t.mem.r16(lowmem.SysFontFam)
    if family == 1:
        return t.mem.r16(lowmem.ApFontID)
    return family


@contextmanager
def _unloaded(t):
    """Resources found without being read in, for their names and IDs."""
    rm = _rm(t)
    load = rm.res_load
    rm.SetResLoad(False)
    try:
        yield rm
    finally:
        rm.SetResLoad(load)


def family_name(t, family: int) -> str:
    """The family's name: its FOND's, or the name of the FONT or NFNT that
    heads it (ID family * 128), "" for a family not installed."""
    family = _family(t, family)
    with _unloaded(t) as rm:
        font = font_id(family)
        for kind, rid in (("FOND", family), ("FONT", font), ("NFNT", font)):
            h = rm.GetResource(kind, rid) if rid is not None and -0x8000 <= rid < 0x8000 else 0
            if h:
                return rm.GetResInfo(h)[2]
    return ""


def family_named(t, name: str) -> int | None:
    """The number of the family named, in any case; None if none has it."""
    if not name:
        return None
    with _unloaded(t) as rm:
        h = rm.GetNamedResource("FOND", name)
        if h:
            return rm.GetResInfo(h)[0]
        h = rm.GetNamedResource("FONT", name) or rm.GetNamedResource("NFNT", name)
        return font_family(rm.GetResInfo(h)[0]) if h else None


@trap
def GetFontName(t, family, p):
    t.set_str255(p, family_name(t, family))


@trap
def GetFNum(t, p, num_p):
    """0 if no family has the name."""
    num = family_named(t, t.str255(p))
    t.w16(num_p, num or 0)


@trap
def RealFont(t, family, size):
    """Whether the family is installed at the size, not scaled to it: a FONT
    of that size, or a size, or an outline font (size 0), its FOND lists.
    Size 0 is the system font size, 12, as for TextSize (IM I-171): DOCMaker
    asks after Chicago in size 0."""
    family = _family(t, family)
    size = size or 12
    if not 0 < size < 128:
        return False
    with _unloaded(t) as rm:
        rid = font_id(family, size)
        if rid is not None and rm.GetResource("FONT", rid):
            return True
    rm = _rm(t)
    h = rm.GetResource("FOND", family)
    if not h:
        return False
    heap = t.system.heap_of(h)
    data = t.mem.read(heap.deref(h), heap.handle_size(h))
    if len(data) < 54:
        return False
    n = struct.unpack_from(">h", data, 52)[0] + 1
    sizes = {struct.unpack_from(">h", data, 54 + 6 * i)[0]
             for i in range(min(n, (len(data) - 54) // 6))}
    return size in sizes or 0 in sizes


@trap
def SetFontLock(t, lock):
    pass


@trap
def IsOutline(t, numer, denom):
    """Whether the port's text would be drawn from an outline font: never,
    as text is drawn from bitmap fonts here."""
    return False


# Whether outline fonts are to be preferred to bitmapped ones, and whether
# glyphs keep their shapes when they go past the font's ascent or descent
# (Inside Macintosh: Text, the Font Manager): kept for whoever asks, as
# text is drawn from bitmap fonts here either way.
@trap
def SetOutlinePreferred(t, preferred):
    t.system.outline_preferred = bool(preferred)


@trap
def GetOutlinePreferred(t):
    return getattr(t.system, "outline_preferred", False)


@trap
def SetPreserveGlyph(t, preserve):
    t.system.preserve_glyph = bool(preserve)


@trap
def GetPreserveGlyph(t):
    return getattr(t.system, "preserve_glyph", False)


@trap
def FlushFonts(t):
    """Empty the cache of glyphs drawn from outline fonts, which there
    isn't one of here."""
    return noErr


# The two flags are kept where programs read them; widths here are whole
# pixels and fonts are scaled either way.
@trap
def SetFractEnable(t, enable):
    t.mem.w8(lowmem.FractEnable, 0xFF if enable else 0)


@trap
def SetFScaleDisable(t, disable):
    t.mem.w8(lowmem.FScaleDisable, 0xFF if disable else 0)


# The output record, FMOutput, at FMgrOutRec (Inside Macintosh I, "The Font
# Manager").  Programs of 1984 read it after measuring a character: Word
# 1.0 takes every character's width from the FONT its fontHandle holds,
# and scales it by numer and denom, rather than call CharWidth again.
FMOUTPUT = ">hIBBBBBBbBBBbBhhhh"
FONT_HEADER = ">HHHHhhhhHhhhH"
propFont = 0x9000
_bold, _italic, _underline, _outline, _shadow = (1 << i for i in range(5))

# The global width table (Inside Macintosh IV, "The Font Manager"): each
# character's width, Fixed, then the request it was made for and what
# answered it.  Microsoft Word 4 adds up widths from it.
WIDTH_TABLE = ">256lIllhhhhIIhIBBhhhhhh"
UNITY_POINT = 0x00010001
FACTOR_ONE = 0x100              # 1 in the table's 16-bit fixed-point factors


@trap
def FMSwapFont(t, inp):
    """The font for an FMInput record's family, size and face."""
    family, size, face, _bits, device, numer, denom = struct.unpack(">hhBBhII",
                                                                    t.mem.read(inp, 16))
    return _swap_font(t, family, size, face, (device, numer, denom))


@trap
def FontMetrics(t, p):
    """GetFontInfo's measures in Fixed, and the global width table
    (Inside Macintosh IV, "The Font Manager")."""
    _swap_port_font(t)
    ascent, descent, wid_max, leading = t.tb.GetFontInfo()
    t.mem.write(p, struct.pack(">llllI", ascent << 16, descent << 16, leading << 16,
                               wid_max << 16, t.mem.r32(lowmem.WidthTabHandle)))


def _swap_port_font(t) -> None:
    port = _port(t)
    if port is not None:
        _swap_font(t, port.tx_font, port.tx_size, port.tx_face)


def _swap_font(t, family: int, size: int, face: int,
               more: tuple[int, int, int] = (0, UNITY_POINT, UNITY_POINT)) -> int:
    """Pick the font, as QuickDraw draws it, and leave the output record
    in low memory.  An application's own family, or a standard one it
    has its own strike of, is drawn from its FONT or NFNT, which is the
    fontHandle, with extra the pixels its style adds to each character;
    any other standard family is drawn with a host font, and the
    fontHandle is the FONT it's measured with, a real System file's, or
    else a FONT made from the host font, style and all."""
    qd = t.tb.qd
    request = (family, size, face, *more)         # and the FMInput's device, numer and denom
    size = text_size(size)
    found = None
    if qd.app_fonts is not None:
        found = qd.app_fonts.source(family, size)
    if found is None and qd.app_fonts is not None and family in STANDARD_FAMILIES:
        measured = qd.app_fonts.measure(family, size)
        found = (measured[0], 1.0, *measured[1:]) if measured is not None else None
    if found is not None:
        strike, scale, kind, rid = found
        handle = _rm(t).GetResource(kind, rid)
        extra = (1 if face & _bold else 0) + (1 if face & (_outline | _shadow) else 0)
        info = [round(n * scale) for n in (strike.ascent, strike.descent, strike.wid_max,
                                           strike.leading)]
        numer, denom = (size, round(size / scale)) if scale != 1 else (1, 1)
    else:
        handle = _host_font(t, family, size, face)
        extra = 0
        info = list(qd.host_font_info(family, size, face))
        numer = denom = 1
    ascent, descent, wid_max = (max(0, min(n, 255)) for n in info[:3])
    leading = max(-128, min(info[3], 127))
    t.mem.write(lowmem.FMgrOutRec, struct.pack(
        FMOUTPUT, 0, handle, 1 if face & _bold else 0, 1 if face & _italic else 0, 1, 1, 1,
        1 if face & (_outline | _shadow) else 0, extra, ascent, descent, wid_max, leading, 0,
        numer, numer, denom, denom))
    _put_width_table(t, request, handle, size, found, extra)
    return lowmem.FMgrOutRec


def _put_width_table(t, request: tuple, font: int, size: int, found, extra: int) -> None:
    """The global width table for the font FMSwapFont has picked, found
    (a strike and its scale) or a host font: made once, in the system
    heap, and filled in again when the font or the request changes.  Its
    widths are the ones QuickDraw draws with, whole unless fractional
    widths are enabled; space extra isn't in them."""
    m, system = t.mem, t.system
    heap = system.sys_heap
    h = system.width_table
    if not h:
        h = heap.new_handle(struct.calcsize(WIDTH_TABLE))
        listed = heap.new_handle(8)                     # it, and 0 for the list's end
        if not h or not listed:
            return
        m.w32(heap.deref(listed), h)
        m.w32(lowmem.WidthListHand, listed)
        system.width_table = h
    fract = m.r8(lowmem.FractEnable) != 0
    key = (request, font, fract)
    p = heap.deref(h)
    if system.width_request != key:
        system.width_request = key
        family, asked, face, device, numer, denom = request
        if found is None:
            widths, scale = _host_widths(t, family, size, face), 1.0
        else:
            strike, scale = found[:2]
            widths = [(strike.char_width(c) + extra) * scale for c in range(256)]
        m.write(p, struct.pack(
            WIDTH_TABLE, *(round((w if fract else round(w)) * 0x10000) for w in widths), font,
            0, extra << 16, family, asked, face, device, numer, denom, _family(t, family), 0,
            False, face, FACTOR_ONE, FACTOR_ONE, FACTOR_ONE, FACTOR_ONE, round(size / scale),
            struct.calcsize(WIDTH_TABLE)))
    m.w32(lowmem.WidthTabHandle, h)
    m.w32(lowmem.WidthPtr, p)


def _host_widths(t, family: int, size: int, face: int) -> list[int]:
    """How far QuickDraw moves the pen for each character in a host font."""
    text = from_mac(bytes(range(256))).translate(CHICAGO_SYMBOLS)
    return t.tb.qd.host_widths(family, size, face, text)


def _host_font(t, family: int, size: int, face: int) -> int:
    """A FONT record for a host font: its widths are the ones macrt draws
    with, so what a program adds up from them is where the pen goes.  Its
    strike is blank, since nothing draws from it."""
    fonts = t.system.font_records
    key = (family, size, face)
    if key not in fonts:
        qd = t.tb.qd
        widths = [min(w, 255) for w in _host_widths(t, family, size, face)]
        ascent, descent, wid_max, leading = qd.host_font_info(family, size, face)
        height = max(ascent + descent, 1)
        n = 256 + 2                         # each character, the missing one, and the end
        strike = bytes(2 * height)          # a word wide
        ow_table = struct.calcsize(FONT_HEADER) + len(strike) + 2 * n
        record = (struct.pack(FONT_HEADER, propFont, 0, 255, min(wid_max, 255), 0, -descent,
                              wid_max, height, (ow_table - 16) // 2, ascent, descent, leading, 1)
                  + strike + bytes(2 * n) + struct.pack(f">{n}H", *widths, 0, 0xFFFF))
        h = t.system.sys_heap.new_handle_with(record)
        if not h:
            return 0
        fonts[key] = h
    return fonts[key]

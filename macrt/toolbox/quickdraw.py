"""
QuickDraw data in guest memory: GrafPorts, the QuickDraw globals in an
application's A5 world, and regions.

The drawing is in qdraw.  Each window port has a Backing, a QImage that
the drawing calls paint into and the window shows; other ports draw into
their portBits.  Guests draw on their own thread, so every access to a
Backing goes through its lock.

A cGrafPort (Inside Macintosh V-49) is a GrafPort of the same size whose
portBits is a PixMap handle, with portVersion's top two bits set where
a BitMap's rowBytes would be, and whose patterns are PixPat handles,
with RGB colours between them.  GrafPort reads either: port_bits_base
and the rest find a cGrafPort's in its PixMap, and its patterns are
PixPatRefs, the 1-bit pattern each PixPat has with its handle.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

from PyQt6.QtGui import QColor, QImage, QPainter

from ..memory import LONG, LONGINT, BYTE, INTEGER, POINT, RAM, RECT, RGB, BusError, Field, Record
from . import gdevice, lowmem
from .color import BLACK as BLACK_RGB, WHITE as WHITE_RGB
from .constants import blackColor, patCopy, srcOr, whiteColor
from .memmgr import Heap
from .types import Point, Rect

BLACK = QColor("#000000")
WHITE = QColor("#FFFFFF")

WHITE_PAT = bytes(8)
BLACK_PAT = b"\xFF" * 8
GRAY_PAT = b"\xAA\x55" * 4
LT_GRAY_PAT = b"\x88\x22" * 4
DK_GRAY_PAT = b"\x77\xDD" * 4

# The arrow cursor: 16 rows of data, 16 of mask, then the hot spot (v, h).
ARROW_DATA = (0x0000, 0x4000, 0x6000, 0x7000, 0x7800, 0x7C00, 0x7E00, 0x7F00,
              0x7F80, 0x7C00, 0x6C00, 0x4600, 0x0600, 0x0300, 0x0300, 0x0000)
ARROW_MASK = (0xC000, 0xE000, 0xF000, 0xF800, 0xFC00, 0xFE00, 0xFF00, 0xFF80,
              0xFFC0, 0xFFE0, 0xFE00, 0xEF00, 0xCF00, 0x8780, 0x0780, 0x0380)
ARROW_HOT_SPOT = Point(1, 1)

WIDE_OPEN = Rect(-32767, -32767, 32767, 32767)


class BitMap:
    """A BitMap's three fields: baseAddr, rowBytes, bounds."""

    def __init__(self, base: int, row_bytes: int, bounds: Rect):
        self.base = base
        self.row_bytes = row_bytes
        self.bounds = bounds


# ---------------------------------------------------------------------------
# QuickDraw globals.  0(A5) holds the address of thePort; the other globals
# sit below it (Inside Macintosh I-163).  InitGraf is handed that address.
# ---------------------------------------------------------------------------
QD_THE_PORT = 0
QD_WHITE = -8
QD_BLACK = -16
QD_GRAY = -24
QD_LT_GRAY = -32
QD_DK_GRAY = -40
QD_ARROW = -108
QD_SCREEN_BITS = -122
QD_RAND_SEED = -126
QD_GLOBALS_SIZE = 206       # including 76 private bytes below randSeed


def init_qd_globals(mem: RAM, the_port: int, screen: BitMap) -> None:
    """What InitGraf puts in an application's QuickDraw globals."""
    mem.fill(the_port + 4 - QD_GLOBALS_SIZE, QD_GLOBALS_SIZE)
    mem.w32(the_port + QD_THE_PORT, 0)
    for offset, pat in ((QD_WHITE, WHITE_PAT), (QD_BLACK, BLACK_PAT), (QD_GRAY, GRAY_PAT),
                        (QD_LT_GRAY, LT_GRAY_PAT), (QD_DK_GRAY, DK_GRAY_PAT)):
        mem.write(the_port + offset, pat)
    arrow = the_port + QD_ARROW
    for i, (row, mask) in enumerate(zip(ARROW_DATA, ARROW_MASK)):
        mem.w16(arrow + 2 * i, row)
        mem.w16(arrow + 32 + 2 * i, mask)
    mem.w_point(arrow + 64, ARROW_HOT_SPOT)
    bits = the_port + QD_SCREEN_BITS
    mem.w32(bits, screen.base)
    mem.w16(bits + 4, screen.row_bytes)
    mem.w_rect(bits + 6, screen.bounds)
    mem.w32(the_port + QD_RAND_SEED, 1)


# ---------------------------------------------------------------------------
# Regions.  A region is a handle to rgnSize, rgnBBox, then (for anything
# but a rectangle) the region data.  These make rectangular ones; qdraw
# reads and writes the rest.
# ---------------------------------------------------------------------------
RECT_RGN_SIZE = 10


def new_rgn(heap: Heap, r: Rect = Rect(0, 0, 0, 0)) -> int:
    h = heap.new_handle(RECT_RGN_SIZE)
    if h:
        set_rect_rgn(heap, h, r)
    return h


def set_rect_rgn(heap: Heap, h: int, r: Rect) -> None:
    if r.empty:
        r = Rect(0, 0, 0, 0)
    if heap.handle_size(h) != RECT_RGN_SIZE:
        heap.set_handle_size(h, RECT_RGN_SIZE)
    p = heap.deref(h)
    heap.mem.w16(p, RECT_RGN_SIZE)
    heap.mem.w_rect(p + 2, r)


def rgn_bbox(mem: RAM, h: int) -> Rect:
    return mem.r_rect((mem.r32(h) & 0xFFFFFF) + 2)


# ---------------------------------------------------------------------------
# GrafPort
# ---------------------------------------------------------------------------
CPORT_VERSION = 0xC000          # portVersion's flags: a cGrafPort
GRAF_VARS_SIZE = 26             # rgbOpColor, rgbHiliteColor, pmFgColor ... pmFlags


class PixPatRef(bytes):
    """A cGrafPort's pattern: the 1-bit pattern its PixPat has, and the
    PixPat's handle, which drawing looks in for its pixels."""

    def __new__(cls, pat: bytes, handle: int):
        ref = super().__new__(cls, pat)
        ref.handle = handle
        return ref


class _Pattern:
    """A pattern field: 8 bytes in a GrafPort; in a cGrafPort, a PixPat
    handle at another offset.  Setting a pattern in a cGrafPort is
    PenPat's or BackPat's: it goes in the PixPat if that's an old-style
    one, the port's, or else in a new one, since a pixel pattern is the
    application's (Inside Macintosh V-74); a PixPatRef sets its handle,
    as PenPixPat does."""

    def __init__(self, offset: int, color_offset: int, default: bytes):
        self.offset, self.color_offset, self.default = offset, color_offset, default

    def __get__(self, port, owner=None):
        if port is None:
            return self
        if not port.is_color:
            return port.mem.read(port.addr + self.offset, 8)
        h = port.mem.r32(port.addr + self.color_offset)
        p = gdevice.deref(port.mem, h)
        return PixPatRef(port.mem.read(p + 0x14, 8) if p else self.default, h)

    def __set__(self, port, value: bytes) -> None:
        if not port.is_color:
            port.mem.write(port.addr + self.offset, bytes(value)[:8])
            return
        at = port.addr + self.color_offset
        handle = getattr(value, "handle", None)
        if handle is not None:
            port.mem.w32(at, handle)
            return
        h = port.mem.r32(at)
        p = gdevice.deref(port.mem, h)
        if p and (port.mem.r16(p) == gdevice.oldPat or port.heap is None):
            gdevice.PixPat(port.mem, p).pat1_data = bytes(value)[:8]
            return
        if port.heap is not None:
            h = gdevice.new_pix_pat(port.mem, port.heap, bytes(value)[:8])
            if h:
                port.mem.w32(at, h)


def black_white(depth: int) -> tuple[int, int]:
    """The pixel values black and white are at a depth, in the standard
    colour tables, or as direct colours."""
    if depth > 8:
        return 0, (1 << (15 if depth == 16 else 24)) - 1
    return (1 << depth) - 1, 0


class GrafPort(Record):
    SIZE = 108

    device = Field(0, INTEGER)
    # portBits, as it is in a GrafPort; port_bits_base and the rest read a
    # cGrafPort's too
    bits_base = Field(2, LONG)
    bits_row_bytes = Field(6, INTEGER)
    bits_bounds = Field(8, RECT)
    port_rect = Field(16, RECT)
    vis_rgn = Field(24, LONG)
    clip_rgn = Field(28, LONG)
    bk_pat = _Pattern(32, 32, bytes(8))
    fill_pat = _Pattern(40, 62, b"\xFF" * 8)
    pn_loc = Field(48, POINT)
    pn_size = Field(52, POINT)
    pn_mode = Field(56, INTEGER)
    pn_pat = _Pattern(58, 58, b"\xFF" * 8)
    pn_vis = Field(66, INTEGER)
    tx_font = Field(68, INTEGER)
    tx_face = Field(70, BYTE)
    tx_mode = Field(72, INTEGER)
    tx_size = Field(74, INTEGER)
    sp_extra = Field(76, LONGINT)
    fg_color = Field(80, LONGINT)
    bk_color = Field(84, LONGINT)
    colr_bit = Field(88, INTEGER)
    pat_stretch = Field(90, INTEGER)
    pic_save = Field(92, LONG)
    rgn_save = Field(96, LONG)
    poly_save = Field(100, LONG)
    graf_procs = Field(104, LONG)
    # a cGrafPort's own fields, where a GrafPort has portBits and patterns
    port_pix_map = Field(2, LONG)
    port_version = Field(6, INTEGER)
    graf_vars = Field(8, LONG)
    ch_extra = Field(12, INTEGER)
    pn_loc_h_frac = Field(14, INTEGER)
    bk_pix_pat = Field(32, LONG)
    rgb_fg_color = Field(36, RGB)
    rgb_bk_color = Field(42, RGB)
    pn_pix_pat = Field(58, LONG)
    fill_pix_pat = Field(62, LONG)

    def __init__(self, mem: RAM, addr: int):
        super().__init__(mem, addr)
        self.backing: Backing | None = None
        self.heap: Heap | None = None           # where its patterns go, a cGrafPort's
        self.gw_device = 0                      # a GWorld's GDevice (glue_gworld)
        self.gw_own_device = False              # whether the GWorld made it

    @property
    def is_color(self) -> bool:
        return self.mem.r16(self.addr + 6) & CPORT_VERSION == CPORT_VERSION

    def pixmap(self) -> int:
        """Where a cGrafPort's PixMap is; 0 if it has none."""
        try:
            return gdevice.deref(self.mem, self.port_pix_map)
        except BusError:
            return 0

    def _bits(self) -> int:
        """Where the portBits' baseAddr, rowBytes and bounds are: in a
        cGrafPort, its PixMap's; 0 if it has none."""
        return self.pixmap() if self.is_color else self.addr + 2

    @property
    def port_bits_base(self) -> int:
        at = self._bits()
        return self.mem.r32(at) if at else 0

    @port_bits_base.setter
    def port_bits_base(self, base: int) -> None:
        at = self._bits()
        if at:
            self.mem.w32(at, base)

    @property
    def port_bits_row_bytes(self) -> int:
        """rowBytes; a PixMap's without its flags."""
        if not self.is_color:
            return self.mem.r16(self.addr + 6)
        at = self.pixmap()
        return self.mem.r16(at + 4) & gdevice.ROW_BYTES_MASK if at else 0

    @port_bits_row_bytes.setter
    def port_bits_row_bytes(self, row_bytes: int) -> None:
        if not self.is_color:
            self.bits_row_bytes = row_bytes
        elif at := self.pixmap():
            self.mem.w16(at + 4, row_bytes & gdevice.ROW_BYTES_MASK | gdevice.PIXMAP_FLAG)

    @property
    def port_bits_bounds(self) -> Rect:
        at = self._bits()
        return self.mem.r_rect(at + 6) if at else Rect(0, 0, 0, 0)

    @port_bits_bounds.setter
    def port_bits_bounds(self, bounds: Rect) -> None:
        at = self._bits()
        if at:
            self.mem.w_rect(at + 6, bounds)

    def open(self, heap: Heap, screen: BitMap) -> None:
        """OpenPort: a port onto the whole screen with default settings."""
        self.mem.fill(self.addr, GrafPort.SIZE)
        self.port_bits_base = screen.base
        self.port_bits_row_bytes = screen.row_bytes
        self.port_bits_bounds = screen.bounds
        self.port_rect = screen.bounds
        self.vis_rgn = new_rgn(heap, screen.bounds)
        self.clip_rgn = new_rgn(heap, WIDE_OPEN)
        self.bk_pat = WHITE_PAT
        self.fill_pat = BLACK_PAT
        self.pn_size = Point(1, 1)
        self.pn_mode = patCopy
        self.pn_pat = BLACK_PAT
        self.tx_mode = srcOr
        self.fg_color = blackColor
        self.bk_color = whiteColor

    def open_color(self, heap: Heap, screen: BitMap) -> bool:
        """OpenCPort: a cGrafPort onto the current device, with a PixMap,
        three patterns and its GrafVars of its own (Inside Macintosh
        V-67); False if there isn't the memory for them."""
        self.mem.fill(self.addr, GrafPort.SIZE)
        self.heap = heap
        handles = [heap.new_handle(gdevice.PIXMAP_SIZE, clear=True),
                   heap.new_handle(GRAF_VARS_SIZE, clear=True)]
        handles += [gdevice.new_pix_pat(heap.mem, heap, pat)
                    for pat in (WHITE_PAT, BLACK_PAT, BLACK_PAT)]
        if not all(handles):
            for h in handles[:2]:
                if h:
                    heap.dispose_handle(h)
            for h in handles[2:]:
                if h:
                    gdevice.dispose_pix_pat(heap.mem, heap, h)
            return False
        self.port_pix_map, self.graf_vars = handles[:2]
        self.bk_pix_pat, self.pn_pix_pat, self.fill_pix_pat = handles[2:]
        self.init_color(heap, screen)
        return True

    def init_color(self, heap: Heap, screen: BitMap) -> None:
        """InitCPort: the PixMap the current device's (with the device's
        colour table), black on white, patterns of black and white, and
        the rest of the fields as InitPort sets them."""
        mem = self.mem
        handles = (self.port_pix_map, self.graf_vars, self.bk_pix_pat, self.pn_pix_pat,
                   self.fill_pix_pat)
        self.open(heap, screen)
        (self.port_pix_map, self.graf_vars, self.bk_pix_pat, self.pn_pix_pat,
         self.fill_pix_pat) = handles
        self.heap = heap
        self.port_version = CPORT_VERSION
        self.ch_extra = 0
        self.pn_loc_h_frac = 0x8000             # a half
        pm, device = self.pixmap(), gdevice.device_pixmap(mem)
        if pm and device:
            mem.move(device, pm, gdevice.PIXMAP_SIZE)
        elif pm:
            gdevice.write_pixmap(mem, pm, screen.base, screen.row_bytes, screen.bounds, 1, 0)
        self.rgb_fg_color, self.rgb_bk_color = BLACK_RGB, WHITE_RGB
        depth = mem.r16(pm + 0x20) if pm else 1
        self.fg_color, self.bk_color = black_white(depth)
        self.bk_pat, self.pn_pat, self.fill_pat = WHITE_PAT, BLACK_PAT, BLACK_PAT
        gv = gdevice.deref(mem, self.graf_vars)
        if gv:
            mem.fill(gv, GRAF_VARS_SIZE)
            mem.write(gv + 6, mem.read(lowmem.HiliteRGB, 6))      # rgbOpColor black

    def close(self, heap: Heap) -> None:
        """ClosePort: release the regions, not the record; CloseCPort the
        PixMap (not its colour table, the device's), the patterns and the
        GrafVars too."""
        for h in (self.vis_rgn, self.clip_rgn):
            heap.dispose_handle(h)
        self.vis_rgn = self.clip_rgn = 0
        if self.is_color:
            for h in (self.bk_pix_pat, self.pn_pix_pat, self.fill_pix_pat):
                if h:
                    gdevice.dispose_pix_pat(self.mem, heap, h)
            for h in (self.graf_vars, self.port_pix_map):
                if h:
                    heap.dispose_handle(h)
            self.bk_pix_pat = self.pn_pix_pat = self.fill_pix_pat = 0
            self.graf_vars = self.port_pix_map = 0

    def local_to_global(self, pt: Point) -> Point:
        b = self.port_bits_bounds
        return Point(pt.v - b.top, pt.h - b.left)

    def global_to_local(self, pt: Point) -> Point:
        b = self.port_bits_bounds
        return Point(pt.v + b.top, pt.h + b.left)


class Backing:
    """Where a window port's drawing goes until QuickDraw draws through
    portBits.  It keeps the pixels in `area`, relative to the top left of
    the portRect: the whole port, but for a window that reaches far off
    the screen (WindowRecord.kept)."""

    def __init__(self, area: Rect, port: Rect | None = None):
        self.lock = threading.RLock()
        self.area = area
        self.port = port or area        # the portRect, relative to its top left
        self.paper = WHITE              # what clear() leaves: a colour window's content colour
        self.image = self._blank(area.width, area.height)

    @staticmethod
    def _blank(width: int, height: int) -> QImage:
        image = QImage(max(width, 1), max(height, 1), QImage.Format.Format_RGB32)
        image.fill(WHITE)
        return image

    def fit(self, area: Rect, port: Rect) -> bool:
        """Keep the pixels in area of the port, now port, instead: those the
        two areas share as they were.  True if area has pixels the port had
        before but this didn't keep, which need drawing again."""
        with self.lock:
            had = self.port.sect(area)
            dropped = not had.empty and had.sect(self.area) != had
            self.port = port
            if area != self.area:
                old, before = self.image, self.area
                self.image = self._blank(area.width, area.height)
                p = QPainter(self.image)
                p.drawImage(before.left - area.left, before.top - area.top, old)
                p.end()
                self.area = area
            return dropped

    def clear(self) -> None:
        """All white, or a colour window's content colour, as the Window
        Manager leaves a window's content when it shows it."""
        with self.lock:
            self.image.fill(self.paper)

    def scroll(self, dh: int, dv: int) -> None:
        """Move the pixels kept by (dh, dv), what's left behind white."""
        with self.lock:
            old = self.image
            self.image = self._blank(old.width(), old.height())
            p = QPainter(self.image)
            p.drawImage(dh, dv, old)
            p.end()

    @contextmanager
    def painter(self):
        """A painter whose (0, 0) is the top left of the portRect."""
        with self.lock:
            p = QPainter(self.image)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.translate(-self.area.left, -self.area.top)
            try:
                yield p
            finally:
                p.end()

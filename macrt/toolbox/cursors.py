"""
macrt.toolbox.cursors - A program's cursor, as the host's pointer shows it.

A Cursor is 16 rows of 16 bits of data, 16 of mask, then its hot spot
(Inside Macintosh I-146).  Where the mask has a bit set the cursor is
black or white as the data's bit is; where it hasn't, a data bit set
inverts what's under it and a clear one leaves it be.  A colour cursor's
mask is the same, its picture a PixMap's pixels: those inside the mask
replace the screen's, those outside it are XORed with it, so white
leaves the screen be and black inverts it (V-62).  The host's pointer
can't invert, so macrt shows those black.

What the display makes the pointer of, a cursor's "shape", is one of:
None, the host's own arrow, which the standard arrow is shown as; HIDDEN,
while the program has the cursor hidden; or a Shape, its pixels.
"""

from __future__ import annotations

import struct
from functools import lru_cache
from typing import NamedTuple

from .quickdraw import ARROW_DATA, ARROW_HOT_SPOT, ARROW_MASK
from .types import Point

SIZE = 16                   # a cursor's width and height
CURSOR_SIZE = 68            # a Cursor record: data, mask, hot spot
HIDDEN = "hidden"

ARROW = struct.pack(">16H16Hhh", *ARROW_DATA, *ARROW_MASK, *ARROW_HOT_SPOT)

_WHITE, _BLACK = 0xFFFFFFFF, 0xFF000000
_CLEAR = 0


class Shape(NamedTuple):
    """A pointer's picture: 16 rows of 16 pixels, each red, green, blue
    and alpha bytes; and where in it the pointer points."""
    rgba: bytes
    hot: Point


def _hot(v: int, h: int) -> Point:
    return Point(min(max(v, 0), SIZE - 1), min(max(h, 0), SIZE - 1))


def _shape(pixels: list[int], hot: Point) -> Shape:
    """From 0xAARRGGBB pixels, row by row."""
    return Shape(b"".join(struct.pack(">I", (p << 8 | p >> 24) & 0xFFFFFFFF) for p in pixels),
                 hot)


@lru_cache(maxsize=64)
def mono(cursor: bytes) -> Shape | None:
    """A Cursor record's shape: None for the standard arrow."""
    if cursor[:CURSOR_SIZE] == ARROW:
        return None
    words = struct.unpack_from(">16H16Hhh", cursor)
    data, mask = words[:SIZE], words[SIZE:2 * SIZE]
    pixels = []
    for row, keep in zip(data, mask):
        for x in range(SIZE):
            bit = 0x8000 >> x
            if keep & bit:
                pixels.append(_BLACK if row & bit else _WHITE)
            else:
                pixels.append(_BLACK if row & bit else _CLEAR)
    return _shape(pixels, _hot(*words[2 * SIZE:]))


@lru_cache(maxsize=64)
def color(pixels: bytes, row_bytes: int, pixel_size: int, table: tuple[int, ...],
          mask: bytes, hot: Point) -> Shape:
    """A colour cursor's shape: its PixMap's pixels, of pixel_size bits
    each, rows row_bytes apart, their colours (0xAARRGGBB) by value in
    table; the cursor's 1-bit mask and its hot spot."""
    rows = struct.unpack(">16H", mask[:2 * SIZE].ljust(2 * SIZE, b"\0"))
    per_byte = 8 // pixel_size if pixel_size in (1, 2, 4, 8) else 0
    out = []
    for y in range(SIZE):
        for x in range(SIZE):
            if per_byte:
                at = y * row_bytes + x // per_byte
                byte = pixels[at] if at < len(pixels) else 0
                shift = 8 - pixel_size * (x % per_byte + 1)
                value = byte >> shift & (1 << pixel_size) - 1
                c = table[value] | _BLACK if value < len(table) else _BLACK
            else:
                c = _BLACK
            if rows[y] & 0x8000 >> x:
                out.append(c)
            else:
                out.append(_CLEAR if c & 0xFFFFFF == 0xFFFFFF else c)
    return _shape(out, _hot(*hot))

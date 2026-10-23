"""
Pixels in guest memory as host images, and back: a BitMap's 1 bit a
pixel, or a PixMap's 1, 2, 4 or 8 bits of a colour table's index, or 16
or 32 bits of the colour itself (Inside Macintosh V-52).

    16 bits   x, then 5 bits each of red, green and blue
    32 bits   a byte unused, then a byte each of red, green and blue

A table is a list of 0xAARRGGBB colours by pixel value.  Writing a colour
that isn't in the table writes the nearest that is, as Qt finds it.
"""

from __future__ import annotations

from array import array
from functools import lru_cache

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

WHITE_RGB = 0xFFFFFFFF
BLACK_RGB = 0xFF000000
MONO_TABLE = [WHITE_RGB, BLACK_RGB]     # bit 0 white, bit 1 black, as on a Mac
DEPTHS = (1, 2, 4, 8, 16, 32)
_THRESHOLD = Qt.ImageConversionFlag.ThresholdDither


@lru_cache(maxsize=None)
def _spread(depth: int) -> bytes:
    """For each byte of depth-bit pixels, its pixels a byte each."""
    n = 8 // depth
    mask = (1 << depth) - 1
    return b"".join(bytes((b >> (8 - depth * (i + 1))) & mask for i in range(n))
                    for b in range(256))


def _unpack(data: bytes, depth: int) -> bytes:
    """2- or 4-bit pixels a byte each."""
    n = 8 // depth
    table = _spread(depth)
    return b"".join([table[b * n:b * n + n] for b in data])


_LOW_BITS = {depth: bytes(i & (1 << depth) - 1 for i in range(256)) for depth in (2, 4)}


def _pack(data: bytes, depth: int) -> bytes:
    """Bytes of pixel values packed depth bits each: each value's low
    bits (a Qt image's rows are padded with bytes it leaves as they were)."""
    n = 8 // depth
    data = data.translate(_LOW_BITS[depth])
    if len(data) % n:
        data += bytes(n - len(data) % n)
    planes = [data[i::n] for i in range(n)]
    if n == 2:
        return bytes(a << 4 | b for a, b in zip(*planes))
    return bytes(a << 6 | b << 4 | c << 2 | d for a, b, c, d in zip(*planes))


def _swapped(data: bytes, size: int) -> bytes:
    """data with each size-byte word's bytes reversed: big-endian pixels
    as the host's (little-endian) formats have them."""
    words = array("H" if size == 2 else "I", data)
    words.byteswap()
    return words.tobytes()


def decode(data: bytes, width: int, height: int, row_bytes: int, depth: int,
           table: list[int] | None = None) -> QImage:
    """Rows of pixels, row_bytes apart, as an RGB32 image width pixels wide."""
    if depth == 1:
        img = QImage(data, width, height, row_bytes, QImage.Format.Format_Mono)
        img.setColorTable(table or MONO_TABLE)
    elif depth in (2, 4):
        wide = _unpack(data, depth)
        img = QImage(wide, width, height, row_bytes * (8 // depth), QImage.Format.Format_Indexed8)
        img.setColorTable(_full(table, depth))
    elif depth == 8:
        img = QImage(data, width, height, row_bytes, QImage.Format.Format_Indexed8)
        img.setColorTable(_full(table, depth))
    elif depth == 16:
        img = QImage(_swapped(data, 2), width, height, row_bytes, QImage.Format.Format_RGB555)
    else:
        img = QImage(_swapped(data, 4), width, height, row_bytes, QImage.Format.Format_RGB32)
    return img.convertToFormat(QImage.Format.Format_RGB32)


def _full(table: list[int] | None, depth: int) -> list[int]:
    """table, with as many entries as depth has values: black for any it lacks."""
    n = 1 << depth
    table = list(table or MONO_TABLE)[:n]
    return table + [BLACK_RGB] * (n - len(table))


def encode(img: QImage, depth: int, table: list[int] | None = None) -> tuple[bytes, int]:
    """img's pixels at depth: the bytes, and how many there are a row
    (rows padded as Qt pads them, to 4 bytes; a 2- or 4-bit image's rows
    are packed from its 8-bit ones, so as long as they need be)."""
    if depth == 1:
        out = img.convertToFormat(QImage.Format.Format_Mono, table or MONO_TABLE, _THRESHOLD)
        return raw(out), out.bytesPerLine()
    if depth <= 8:
        out = img.convertToFormat(QImage.Format.Format_Indexed8, _full(table, depth), _THRESHOLD)
        data, bpl = raw(out), out.bytesPerLine()
        if depth == 8:
            return data, bpl
        return _pack(data, depth), bpl * depth // 8
    if depth == 16:
        out = img.convertToFormat(QImage.Format.Format_RGB555)
        return _swapped(raw(out), 2), out.bytesPerLine()
    out = img.convertToFormat(QImage.Format.Format_RGB32)
    return _swapped(raw(out), 4), out.bytesPerLine()


def raw(img: QImage) -> bytes:
    """An image's bytes, as Qt keeps them."""
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return bytes(ptr)


def value_rgb(value: int, depth: int, table: list[int] | None = None) -> int:
    """The colour (0xAARRGGBB) a pixel value is."""
    if depth <= 8:
        return _full(table, depth)[value & ((1 << depth) - 1)]
    if depth == 16:
        r, g, b = (value >> 10) & 31, (value >> 5) & 31, value & 31
        return 0xFF000000 | (r << 19 | (r >> 2) << 16) | (g << 11 | (g >> 2) << 8) | b << 3 | b >> 2
    return 0xFF000000 | (value & 0xFFFFFF)


def rgb_value(rgb: int, depth: int, table: list[int] | None = None) -> int:
    """The pixel value nearest a colour (0xAARRGGBB)."""
    if depth <= 8:
        img = QImage(1, 1, QImage.Format.Format_RGB32)
        img.setPixel(0, 0, rgb)
        fmt = QImage.Format.Format_Mono if depth == 1 else QImage.Format.Format_Indexed8
        return img.convertToFormat(fmt, _full(table, depth), _THRESHOLD).pixelIndex(0, 0)
    if depth == 16:
        return ((rgb >> 19 & 31) << 10) | ((rgb >> 11 & 31) << 5) | (rgb >> 3 & 31)
    return rgb & 0xFFFFFF

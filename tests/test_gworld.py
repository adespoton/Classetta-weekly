"""Offscreen graphics worlds: 32-Bit QuickDraw's GWorlds (Inside Macintosh
VI-21)."""

import struct

import pytest

from macrt.m68k.glue_gworld import (GWORLD_VERSION, clipPix, newRowBytes, noNewDevice,
                                    pixelsLocked, pixelsPurgeable, reallocPix, stretchPix)
from macrt.toolbox import lowmem
from macrt.toolbox.color import color_table
from macrt.toolbox.gdevice import GDevice, PixMap, deref, read_table
from macrt.toolbox.quickdraw import GrafPort
from macrt.toolbox.types import Rect

from guest import Guest, Processor

WHITE, BLACK = (0xFFFF, 0xFFFF, 0xFFFF), (0, 0, 0)
RED, GREEN = (0xFFFF, 0, 0), (0, 0xFFFF, 0)


@pytest.fixture
def g(qapp):
    return Guest(model="ii")


def rgb(g, *c) -> int:
    return g.ptr(struct.pack(">HHH", *c))


def new_gworld(g, depth: int, r: Rect, table: int = 0, flags: int = 0) -> int:
    out = g.ptr(bytes(4))
    assert g("NewGWorld", out, depth, g.rect_ptr(r), table, 0, flags) == 0
    return g.mem.r32(out)


def pixmap(g, gw: int) -> PixMap:
    return PixMap(g.mem, deref(g.mem, g("GetGWorldPixMap", gw)))


def values(g, gw: int) -> list[bytes]:
    """A world's 8-bit pixel values, a row at a time."""
    pm = pixmap(g, gw)
    rb = pm.row_bytes & 0x3FFF
    return [g.mem.read(pm.base_addr + v * rb, pm.bounds.width) for v in range(pm.bounds.height)]


def cport(g) -> GrafPort:
    """A new cGrafPort onto the screen, the current port."""
    p = g.ptr(bytes(GrafPort.SIZE))
    g("OpenCPort", p)
    return g.system.port_at(p)


def screen_colors(g, rect: Rect) -> list[list[int]]:
    bits, table = g.system.screen_bits, g.system.devices.table()
    return [[table[g.mem.r8(bits.base + v * bits.row_bytes + h)]
             for h in range(rect.left, rect.right)] for v in range(rect.top, rect.bottom)]


def current(g) -> tuple[int, int]:
    port, device = g.ptr(bytes(4)), g.ptr(bytes(4))
    g("GetGWorld", port, device)
    return g.mem.r32(port), g.mem.r32(device)


def test_new_gworld_makes_a_colour_port_with_pixels_and_a_device_of_its_own(g):
    before = current(g)
    r = Rect(10, 20, 15, 30)
    gw = new_gworld(g, 8, r)
    assert current(g) == before                 # neither the port nor the device changes
    port = g.system.port_at(gw)
    assert port.is_color and port.port_version & 0xFFFF == GWORLD_VERSION
    assert port.port_rect == r
    pm = pixmap(g, gw)
    assert pm.bounds == r and pm.pixel_size == 8 and pm.row_bytes & 0x3FFF == 12
    assert values(g, gw) == [bytes(10)] * 5     # white
    assert read_table(g.mem, pm.pm_table) == g.system.devices.table()
    device = g("GetGWorldDevice", gw)
    assert device and device != g.system.devices.main
    gd = GDevice(g.mem, deref(g.mem, device))
    assert gd.pmap == port.port_pix_map and gd.rect == r


def test_a_gworld_draws_in_its_own_colours_and_copies_to_the_screen(g):
    screen = cport(g)
    table = g.handle(color_table([WHITE, RED, GREEN, BLACK], seed=7))
    gw = new_gworld(g, 8, Rect(0, 0, 2, 4), table)
    saved = current(g)
    assert saved == (screen.addr, g.system.devices.main)
    g("SetGWorld", gw, 0)
    assert current(g) == (gw, g("GetGWorldDevice", gw))
    g("RGBForeColor", rgb(g, *GREEN))
    assert g.system.port_at(gw).fg_color == 2   # its table's green, not the screen's
    g("PaintRect", g.rect_ptr(Rect(0, 1, 2, 3)))
    assert values(g, gw) == [bytes([0, 2, 2, 0])] * 2
    g("SetGWorld", *saved)
    assert current(g) == saved

    g("CopyBits", deref(g.mem, g("GetGWorldPixMap", gw)), screen.addr + 2,
      g.rect_ptr(Rect(0, 0, 2, 4)), g.rect_ptr(Rect(40, 50, 42, 54)), 0, 0)
    green = g.system.devices.nearest(0xFF00FF00)
    assert screen_colors(g, Rect(40, 50, 42, 54)) == [[0xFFFFFFFF, green, green, 0xFFFFFFFF]] * 2


def test_set_gworld_without_a_device_gives_a_port_on_the_screen_the_main_one(g):
    """FloorTiles goes back to its window from a GWorld with SetGWorld(window,
    NIL), then makes a colour dialog, whose PixMap is the current device's."""
    screen = cport(g)
    gw = new_gworld(g, 8, Rect(0, 0, 4, 4))
    g("SetGWorld", gw, 0)
    g("SetGWorld", screen.addr, 0)
    assert current(g) == (screen.addr, g.system.devices.main)
    # A port whose pixels are elsewhere keeps the device there is.
    g("SetGWorld", gw, 0)
    offscreen = g.ptr(bytes(GrafPort.SIZE))
    g("OpenPort", offscreen)
    g("SetPortBits", g.ptr(struct.pack(">LH4h", g.ptr(bytes(8)), 2, 0, 0, 4, 16)))
    g("SetGWorld", offscreen, 0)
    assert current(g) == (offscreen, g("GetGWorldDevice", gw))


@pytest.mark.parametrize("mode, op", [
    (1, lambda d, s: d | s), (2, lambda d, s: d ^ s), (3, lambda d, s: d & ~s),
    (4, lambda d, s: ~s), (5, lambda d, s: d | ~s), (6, lambda d, s: d ^ ~s),
    (7, lambda d, s: d & s)])
def test_copy_bits_in_a_source_mode_combines_pixel_values_bit_by_bit(g, mode, op):
    """In black and white, each mode applies the foreground colour (all 1's)
    and the background colour (all 0's) to a source's 1's and 0's (Inside
    Macintosh V-57): taken bit by bit, the values' Or, Xor, Bic and so on,
    as FloorTiles masks its coloured tiles offscreen."""
    r = Rect(0, 0, 1, 4)
    src, dst = new_gworld(g, 8, r), new_gworld(g, 8, r)
    s, d = bytes([0x0F, 0x3C, 0x00, 0xFF]), bytes([0x5A, 0xF0, 0x81, 0x18])
    g.mem.write(pixmap(g, src).base_addr, s)
    g.mem.write(pixmap(g, dst).base_addr, d)
    saved = current(g)
    g("SetGWorld", dst, 0)
    g("CopyBits", deref(g.mem, g("GetGWorldPixMap", src)),
      deref(g.mem, g("GetGWorldPixMap", dst)), g.rect_ptr(r), g.rect_ptr(r), mode, 0)
    g("SetGWorld", *saved)
    assert values(g, dst) == [bytes(op(a, b) & 0xFF for a, b in zip(d, s))]


def test_the_pixels_state(g):
    gw = new_gworld(g, 8, Rect(0, 0, 4, 4))
    pm = g("GetGWorldPixMap", gw)
    assert g("GetPixelsState", pm) == 0
    assert g("LockPixels", pm) is True
    assert g("GetPixelsState", pm) == pixelsLocked
    g("AllowPurgePixels", pm)
    g("UnlockPixels", pm)
    assert g("GetPixelsState", pm) == pixelsPurgeable
    g("SetPixelsState", pm, pixelsLocked)
    assert g("GetPixelsState", pm) == pixelsLocked
    assert g("GetPixBaseAddr", pm) == pixmap(g, gw).base_addr
    assert g("PixMap32Bit", pm) is False


def test_update_gworld_stretches_or_clips_what_it_has(g):
    table = g.handle(color_table([WHITE, RED, GREEN, BLACK], seed=7))
    gw = new_gworld(g, 8, Rect(0, 0, 2, 2), table)
    saved = current(g)
    g("SetGWorld", gw, 0)
    g("RGBForeColor", rgb(g, *RED))
    g("PaintRect", g.rect_ptr(Rect(0, 0, 1, 1)))
    g("SetGWorld", *saved)
    out = g.ptr(struct.pack(">L", gw))

    def update(r: Rect, flags: int) -> int:
        return g("UpdateGWorld", out, 8, g.rect_ptr(r), 0, 0, flags)

    assert update(Rect(0, 0, 2, 2), 0) == 0     # nothing to change
    assert update(Rect(0, 0, 4, 4), stretchPix) & (reallocPix | stretchPix) == (
        reallocPix | stretchPix)
    assert values(g, gw) == [bytes([1, 1, 0, 0])] * 2 + [bytes(4)] * 2
    done = update(Rect(1, 1, 3, 7), clipPix)
    assert done & (reallocPix | clipPix | newRowBytes) == reallocPix | clipPix | newRowBytes
    assert values(g, gw) == [bytes([1, 0, 0, 0, 0, 0]), bytes([0, 0, 0, 0, 0, 0])]
    port = g.system.port_at(gw)
    assert port.port_rect == pixmap(g, gw).bounds == Rect(1, 1, 3, 7)
    assert read_table(g.mem, pixmap(g, gw).pm_table)[:4] == [
        0xFFFFFFFF, 0xFFFF0000, 0xFF00FF00, 0xFF000000]
    assert update(Rect(0, 0, 2, 6), 0) == 0     # the same size: moved


def test_dispose_gworld(g):
    out, r = g.ptr(bytes(4)), g.rect_ptr(Rect(0, 0, 40, 40))
    saved = current(g)
    for _ in range(2):                          # the second time, from the same free memory
        free = g.heap.free_bytes()
        assert g("NewGWorld", out, 8, r, 0, 0, 0) == 0
        gw = g.mem.r32(out)
        g("SetGWorld", gw, 0)
        g("DisposeGWorld", gw)
        assert g.mem.r32(lowmem.TheGDevice) == g.system.devices.main
        assert g.system.port_at(gw) is None
        g("SetGWorld", *saved)
    assert g.heap.free_bytes() == free


def test_a_gworld_of_depth_0_is_like_the_deepest_screen(g):
    gw = new_gworld(g, 0, Rect(0, 0, 4, 4))
    pm, main = pixmap(g, gw), g.system.devices.pixmap(g.system.devices.main)
    assert pm.pixel_size == main.pixel_size
    assert read_table(g.mem, pm.pm_table) == g.system.devices.table()
    assert pm.pm_table != main.pm_table


def test_given_depth_0_a_world_is_the_size_of_its_global_rectangle_at_0_0(g):
    gw = new_gworld(g, 0, Rect(92, 112, 388, 512))
    assert g.system.port_at(gw).port_rect == Rect(0, 0, 296, 400)
    assert pixmap(g, gw).bounds == Rect(0, 0, 296, 400)
    out = g.ptr(struct.pack(">L", gw))
    g("UpdateGWorld", out, 0, g.rect_ptr(Rect(20, 30, 70, 90)), 0, 0, 0)
    gw = g.mem.r32(out)
    assert pixmap(g, gw).bounds == g.system.port_at(gw).port_rect == Rect(0, 0, 50, 60)
    # Given a depth, the rectangle is the world's own.
    gw = new_gworld(g, 8, Rect(10, 20, 30, 40))
    assert pixmap(g, gw).bounds == Rect(10, 20, 30, 40)


def test_given_depth_0_new_gworld_ignores_its_device_argument(g):
    """Imaging With QuickDraw, Offscreen Graphics Worlds: with a pixel depth
    of 0, aGDevice is ignored even when noNewDevice is set."""
    gw = new_gworld(g, 0, Rect(0, 0, 4, 4), flags=noNewDevice)
    device = g("GetGWorldDevice", gw)
    assert device and device != g.system.devices.main
    out = g.ptr(bytes(4))
    assert g("NewGWorld", out, 8, g.rect_ptr(Rect(0, 0, 4, 4)), 0, 0, noNewDevice) == -50


def test_a_screen_buffer_is_a_pixmap_like_the_screens(g):
    gdh, pm_p = g.ptr(bytes(4)), g.ptr(bytes(4))
    assert g("NewScreenBuffer", g.rect_ptr(Rect(0, 0, 3, 5)), False, gdh, pm_p) == 0
    devices = g.system.devices
    assert g.mem.r32(gdh) == devices.main
    pm = PixMap(g.mem, deref(g.mem, g.mem.r32(pm_p)))
    main = devices.pixmap(devices.main)
    assert pm.pixel_size == main.pixel_size and pm.pm_table == main.pm_table
    assert pm.bounds == Rect(0, 0, 3, 5) and pm.base_addr
    g("DisposeScreenBuffer", g.mem.r32(pm_p))
    assert deref(g.mem, main.pm_table)          # the screen's table is left


def test_newgworld_without_the_size_of_its_arguments_in_the_selector(qapp):
    """32-Bit QuickDraw's first interfaces call it with MOVEQ #0,D0: its
    dispatcher looks only at D0's low word (Pico)."""
    m = Processor(model="ii")
    out, bounds = m.ptr(bytes(4)), m.rect_ptr((0, 0, 8, 16))
    m.run(bytes.fromhex("4267"                          # CLR.W -(SP): the result
                        f"2F3C{out:08X}"                # MOVE.L #out,-(SP)
                        "3F3C0008"                      # MOVE.W #8,-(SP): the depth
                        f"2F3C{bounds:08X}"             # MOVE.L #bounds,-(SP)
                        + "42A7" * 3                    # CLR.L -(SP): no table, device, flags
                        + "7000AB1D"))                  # MOVEQ #0,D0; _QDExtensions
    assert m.missing == [] and m.cpu.sp == m.stack_top - 2
    assert m.mem.r16(m.cpu.sp) == 0 and m.mem.r32(out) != 0

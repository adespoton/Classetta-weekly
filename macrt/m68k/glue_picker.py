"""
The Color Picker Package, Pack 12 (Inside Macintosh V-171): a colour as
RGB, CMY, HSV or HSL, each a record of three components; and GetColor,
the dialog a user picks a colour in, here the host's own.

A component is a SmallFract, a fraction of 1 in an unsigned word (the
low word of a Fixed), $FFFF all of it: hue round the circle, the others
as much of each as there is.  CMY is RGB's complement.
"""

from __future__ import annotations

import colorsys
import struct

from ..toolbox.events import ProcessKilled
from .dispatch import trap

FULL = 0xFFFF


def _read(t, p: int) -> tuple[float, float, float]:
    return tuple(c / FULL for c in struct.unpack(">HHH", t.mem.read(p, 6)))


def _write(t, p: int, color: tuple[float, float, float]) -> None:
    t.mem.write(p, struct.pack(">HHH", *(min(max(round(c * FULL), 0), FULL) for c in color)))


@trap
def Fix2SmallFract(t, f):
    """Its fraction, or all of 1 for 1 or more."""
    return 0 if f < 0 else min(f, FULL)


@trap
def SmallFract2Fix(t, s):
    return s


@trap
def CMY2RGB(t, cmy, rgb):
    _write(t, rgb, [1 - c for c in _read(t, cmy)])


@trap
def RGB2CMY(t, rgb, cmy):
    _write(t, cmy, [1 - c for c in _read(t, rgb)])


@trap
def HSL2RGB(t, hsl, rgb):
    h, s, lightness = _read(t, hsl)
    _write(t, rgb, colorsys.hls_to_rgb(h, lightness, s))


@trap
def RGB2HSL(t, rgb, hsl):
    h, lightness, s = colorsys.rgb_to_hls(*_read(t, rgb))
    _write(t, hsl, (h, s, lightness))


@trap
def HSV2RGB(t, hsv, rgb):
    _write(t, rgb, colorsys.hsv_to_rgb(*_read(t, hsv)))


@trap
def RGB2HSV(t, rgb, hsv):
    _write(t, hsv, colorsys.rgb_to_hsv(*_read(t, rgb)))


@trap
def GetColor(t, where, prompt, in_color, out_color):
    """Ask the user for a colour, starting from in_color: TRUE and the
    one chosen in out_color, or FALSE (out_color in_color) if cancelled
    or there's no one to ask."""
    m = t.mem
    rgb = struct.unpack(">HHH", m.read(in_color, 6))
    text = m.r_pstr(prompt).decode("mac_roman") if prompt else ""
    chosen = _ask(t, text, rgb)
    m.write(out_color, struct.pack(">HHH", *(chosen or rgb)))
    return chosen is not None


def _ask(t, prompt: str, rgb: tuple[int, int, int]) -> tuple[int, int, int] | None:
    """Show the colour dialog and wait for its answer, letting other
    applications run meanwhile."""
    display = getattr(t.tb, "_d", None)
    if display is None:
        return None
    from ..ui import colordlg
    bridge = display.bridge
    with t.tb.host_dialog():
        dlg, (fut,) = bridge.call(colordlg.open_color, display, prompt, rgb)
        try:
            with t.yielding():
                while True:
                    try:
                        answer = fut.result(timeout=0.1)
                        break
                    except TimeoutError:
                        if t.process.events.killed or bridge.closed:
                            raise ProcessKilled() from None
        finally:
            bridge.post(dlg.finish)
    return answer[1] if answer[0] == "ok" else None

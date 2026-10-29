"""The Color Picker Package (glue_picker): colours as RGB, CMY, HSV and
HSL, and GetColor."""

import struct

import pytest

from guest import Guest

FULL = 0xFFFF


@pytest.fixture
def g(qapp):
    return Guest(model="ii")


def convert(g, name: str, *color: int) -> tuple[int, int, int]:
    src, dst = g.ptr(struct.pack(">HHH", *color)), g.ptr(bytes(6))
    g(name, src, dst)
    return struct.unpack(">HHH", g.mem.read(dst, 6))


def test_small_fracts(g):
    assert g("Fix2SmallFract", 0x8000) == 0x8000
    assert g("Fix2SmallFract", 0x10000) == FULL
    assert g("Fix2SmallFract", -1) == 0
    assert g("SmallFract2Fix", 0xC000) == 0xC000


def test_hsv(g):
    assert convert(g, "HSV2RGB", 0, FULL, FULL) == (FULL, 0, 0)               # red
    assert convert(g, "HSV2RGB", FULL // 3, FULL, FULL) == (0, FULL, 0)       # green
    assert convert(g, "HSV2RGB", 0x1234, 0, 0x8000) == (0x8000,) * 3          # grey
    assert convert(g, "RGB2HSV", 0, 0, FULL) == (round(FULL * 2 / 3), FULL, FULL)
    rgb = (0x1234, 0x9876, 0xCDEF)
    back = convert(g, "HSV2RGB", *convert(g, "RGB2HSV", *rgb))
    assert all(abs(a - b) <= 4 for a, b in zip(back, rgb))   # as near as the words keep it


def test_hsl(g):
    assert convert(g, "HSL2RGB", 0, FULL, 0x8000) == (FULL, 1, 1)             # red, nearly
    assert convert(g, "RGB2HSL", FULL, FULL, FULL)[2] == FULL
    rgb = (0x1234, 0x9876, 0xCDEF)
    back = convert(g, "HSL2RGB", *convert(g, "RGB2HSL", *rgb))
    assert all(abs(a - b) <= 4 for a, b in zip(back, rgb))   # as near as the words keep it


def test_cmy(g):
    assert convert(g, "RGB2CMY", FULL, 0x4000, 0) == (0, 0xBFFF, FULL)
    assert convert(g, "CMY2RGB", 0, 0xBFFF, FULL) == (FULL, 0x4000, 0)


def test_get_color_with_no_one_to_ask_keeps_the_colour(g):
    out = g.ptr(bytes(6))
    assert g("GetColor", 0, 0, g.ptr(struct.pack(">HHH", 1, 2, 3)), out) is False
    assert g.mem.read(out, 6) == struct.pack(">HHH", 1, 2, 3)


def test_the_colour_dialog_answers_with_the_colour_chosen(qapp):
    from PyQt6.QtGui import QColor

    from macrt.ui.colordlg import ColorDialog
    dlg = ColorDialog(None, "Pick a colour", (0x1234, 0x5678, 0x9ABC))
    assert dlg.windowTitle() == "Pick a colour"
    dlg.accept()
    assert dlg._future.result(timeout=1) == ("ok", (0x1234, 0x5678, 0x9ABC))
    dlg = ColorDialog(None, "", (0, 0, 0))
    dlg.reject()
    assert dlg._future.result(timeout=1) == ("cancel",)
    dlg = ColorDialog(None, "", (0, 0, 0))
    dlg.setCurrentColor(QColor(0x12, 0x34, 0x56))
    dlg.accept()
    assert dlg._future.result(timeout=1) == ("ok", (0x1212, 0x3434, 0x5656))

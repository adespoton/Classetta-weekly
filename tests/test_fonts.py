"""The Font Manager's names and numbers, and font menus: the standard
System's font families, and an application's own fonts."""

import struct

from macrt.m68k import runtime
from macrt.resfork import Resource
from macrt.toolbox import lowmem, sysres
from macrt.toolbox.bitfont import font_id
from macrt.toolbox.menus import parse_menu_items

from guest import Guest, Processor


class FontGuest(Guest):
    menu = runtime.Runner.menu

    def __init__(self, resources=()):
        super().__init__(resources)
        self.mem.w16(lowmem.ApFontID, 3)                # as the machine starts
        self.tb.menus_changed = lambda menu=None: None            # no display to show them on

    def name(self, family: int) -> str:
        p = self.ptr(bytes(256))
        self("GetFontName", family, p)
        return self.str255(p)

    def number(self, name: str) -> int:
        p, num = self.ptr(bytes([len(name)]) + name.encode("mac_roman")), self.ptr(bytes(2))
        self("GetFNum", p, num)
        return self.mem.r16(num)

    def new_menu(self, items: str = "") -> int:
        h = self("NewMenu", 200, self.ptr(b"\x04Font"))
        self.menu(h).append(parse_menu_items(items) if items else [])
        return h

    def items(self, h: int) -> list[str]:
        return [it.text for it in self.menu(h).items]

    def font_menu(self, items: str = "") -> list[str]:
        h = self.new_menu(items)
        self("AppendResMenu", h, FONT)
        return self.items(h)


FONT = int.from_bytes(b"FONT", "big")


def font(family: int, size: int, name: bytes | None = None) -> Resource:
    return Resource(b"FONT", font_id(family, size), b"", name)


def test_the_standard_fonds_list_the_sizes():
    data = sysres.fond(21, (9, 12))
    assert len(data) == 52 + 2 + 2 * 6
    assert struct.unpack_from(">4h", data) == (0, 21, 0, 255)
    assert struct.unpack_from(">h", data, 50) == (1,)                   # ffVersion
    assert struct.unpack_from(">7h", data, 52) == (1, 9, 0, 21 * 128 + 9, 12, 0, 21 * 128 + 12)


def test_names_and_numbers_of_the_standard_families(qapp):
    g = FontGuest()
    assert [g.name(n) for n in (0, 2, 3, 4, 20, 21, 22)] == [
        "Chicago", "New York", "Geneva", "Monaco", "Times", "Helvetica", "Courier"]
    assert g.name(1) == "Geneva"                        # the application font
    assert g.name(7) == ""
    assert g.number("Helvetica") == 21 and g.number("HELVETICA") == 21
    assert g.number("Chicago") == 0 and g.number("Zapf Dingbats") == 0
    assert g.process.resources.res_load


def test_real_fonts_are_the_sizes_installed(qapp):
    g = FontGuest()
    assert g("RealFont", 21, 12) and g("RealFont", 4, 9)
    assert not g("RealFont", 21, 13) and not g("RealFont", 4, 10)
    assert g("RealFont", 1, 18)                         # Geneva
    assert not g("RealFont", 7, 12) and not g("RealFont", 21, -12)
    assert g("RealFont", 0, 0) and g("RealFont", 21, 0)    # 0 is the system font size, 12


def test_an_applications_own_fonts(qapp):
    g = FontGuest([font(200, 0, b"Gothic"), font(200, 14)])
    assert g.name(200) == "Gothic" and g.number("gothic") == 200
    assert g("RealFont", 200, 14) and not g("RealFont", 200, 12)


def test_families_256_to_511_have_font_ids_below_0(qapp):
    """PageMaker's tool icons are in its AldusFont, FONT -16384 on."""
    assert (font_id(384), font_id(384, 16), font_id(255, 127), font_id(512)) == (
        -16384, -16368, 0x7FFF, None)
    g = FontGuest([font(384, 0, b"AldusFont"), font(384, 16)])
    assert g.name(384) == "AldusFont" and g.number("AldusFont") == 384
    assert g("RealFont", 384, 16) and not g("RealFont", 384, 12)


def test_an_outline_font_is_real_at_any_size(qapp):
    fond = sysres.fond(300, (0,), ids=(1000,))
    g = FontGuest([Resource(b"FOND", 300, fond, b"Swirl")])
    assert g.number("Swirl") == 300 and g.name(300) == "Swirl"
    assert g("RealFont", 300, 37)


def test_a_font_menu_lists_the_families_by_name(qapp):
    g = FontGuest([font(200, 0, b"Gothic"), font(200, 14), font(201, 0, b".Hidden")])
    assert g.font_menu() == ["Chicago", "Courier", "Geneva", "Gothic", "Helvetica",
                             "Monaco", "New York", "Times"]


def test_a_font_menu_goes_after_the_items_there(qapp):
    g = FontGuest([Resource(b"FOND", 300, sysres.fond(300, (0,), (1000,)), b"Geneva")])
    menu = g.font_menu("Other;(-")
    assert menu[:2] == ["Other", "-"]
    assert menu[2:].count("Geneva") == 1 and len(menu) == 2 + 7


def test_insert_res_menu_puts_them_after_the_item(qapp):
    g = FontGuest()
    h = g.new_menu("First;Last")
    g("InsertResMenu", h, FONT, 1)
    items = g.items(h)
    assert items[0] == "First" and items[-1] == "Last" and items[1] == "Chicago"


def test_text_isnt_drawn_from_outlines(qapp):
    g = FontGuest()
    assert g("IsOutline", 0x00010001, 0x00010001) is False


def test_the_outline_preferences_are_kept(qapp):
    g = FontGuest()
    for get, put in (("GetOutlinePreferred", "SetOutlinePreferred"),
                     ("GetPreserveGlyph", "SetPreserveGlyph")):
        assert not g(get)
        g(put, True)
        assert g(get)
        g(put, False)
        assert not g(get)
    assert g("FlushFonts") == 0


def test_a_font_menu_of_one_script_leaves_out_the_others_fonts(qapp):
    """A family's script is in its number: 16384 is the first of script
    1's (Inside Macintosh: Text)."""
    g = FontGuest([Resource(b"FOND", 16384, sysres.fond(16384, (12,), (1000,)), b"Osaka")])
    h = g.new_menu()
    g("InsertFontResMenu", h, 0, 0)                     # smRoman
    assert "Osaka" not in g.items(h) and "Geneva" in g.items(h)
    h = g.new_menu()
    g("InsertFontResMenu", h, 0, -1)                    # smSystemScript, which is Roman
    assert "Osaka" not in g.items(h) and "Geneva" in g.items(h)
    h = g.new_menu()
    g("InsertFontResMenu", h, 0, -3)                    # smAllScripts
    assert "Osaka" in g.items(h)
    h = g.new_menu()
    g("InsertFontResMenu", h, 0, 1)                     # smJapanese
    assert g.items(h) == ["Osaka"]


def test_a_menu_of_the_international_resources_lists_the_regions(qapp):
    """Date & Time's Date Formats pop-up, of the 'itl0's."""
    g = FontGuest()
    h = g.new_menu()
    g("InsertIntlResMenu", h, int.from_bytes(b"itl0", "big"), 0, 0)
    assert g.items(h) == [sysres.US]
    rm = g.process.resources
    assert all(rm.GetResInfo(rm.GetResource(kind, 0))[2] == sysres.US
               for kind in ("itl0", "itl1", "itl4"))


def test_insert_font_res_menu_through_menu_dispatch(qapp):
    """_InsertFontResMenu is _MenuDispatch ($A825) with its selector in D0."""
    m = Processor([Resource(b"FOND", 16384, sysres.fond(16384, (12,), (1000,)), b"Osaka")])
    m.tb.menus_changed = lambda menu=None: None
    h = m("NewMenu", 200, m.ptr(b"\x04Font"))
    m.cpu.push32(h)
    m.cpu.push16(0)                     # afterItem
    m.cpu.push16(1)                     # the script
    m.cpu.set_d(0, 0x0400)
    m.run(b"\xa8\x25")
    assert [it.text for it in FontGuest.menu(m, h).items] == ["Osaka"]
    assert m.cpu.sp == m.stack_top and not m.missing

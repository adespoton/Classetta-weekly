"""The Color Menu Manager's menu colour table, and the host's menus drawn
in its colours."""

from collections import Counter
from types import SimpleNamespace

from PyQt6.QtGui import QColor

from macrt.m68k.glue_cport import STANDARD_CCTB, STANDARD_WCTB
from macrt.resfork import Resource
from macrt.toolbox import lowmem
from macrt.toolbox.color import color_table
from macrt.toolbox.gdevice import deref
from macrt.toolbox.menus import (MCT_ENTRY, Menu, MenuColors, mct_entry, mctAllItems,
                                 parse_menu_items)
from macrt.toolbox.windows import aux_wins, find_aux_win
from macrt.ui.menubar import MenuBarWidget, Pulldown

from builders import menu
from guest import Guest
from test_dialogs import NoDisplay

BLACK = (0, 0, 0)
WHITE = (0xFFFF, 0xFFFF, 0xFFFF)
RED = (0xFFFF, 0, 0)
BLUE = (0, 0, 0xDDDD)
YELLOW = (0xFFFF, 0xFFFF, 0)


def _entries(g, *entries) -> int:
    return g.ptr(b"".join(mct_entry(*e) for e in entries))


def _entry(g, p):
    """An entry GetMCEntry gave: its menu, item and colours."""
    v = [g.mem.r16(p + 4 + 2 * i) for i in range(12)]
    return g.mem.r16s(p), g.mem.r16s(p + 2), [tuple(v[i:i + 3]) for i in (0, 3, 6, 9)]


def test_entries_are_set_found_replaced_and_deleted(qapp):
    g = Guest()
    assert g("GetMCEntry", 0, 0) == 0                           # no table yet
    g("SetMCEntries", 3, _entries(g, (0, 0, [BLACK, WHITE, BLACK, YELLOW]),
                                  (200, 0, [RED, WHITE, BLACK, YELLOW]),
                                  (200, 2, [BLACK, BLUE, BLACK, WHITE])))
    table = g.process.world.r32(lowmem.MenuCInfo)
    assert table and g.heap.handle_size(table) == 4 * MCT_ENTRY  # and the last
    p = g("GetMCEntry", 200, 2)
    assert _entry(g, p) == (200, 2, [BLACK, BLUE, BLACK, WHITE])
    assert g("GetMCEntry", 200, 3) == 0
    g("SetMCEntries", 2, _entries(g, (200, 2, [BLACK, RED, BLACK, WHITE]),
                                  (200, 3, [BLACK, BLUE, BLACK, WHITE])))
    assert _entry(g, g("GetMCEntry", 200, 2))[2][1] == RED      # replaced
    assert _entry(g, g("GetMCEntry", 200, 3))[2][1] == BLUE     # added
    g("DeleteMCEntries", 200, 2)
    assert g("GetMCEntry", 200, 2) == 0 and g("GetMCEntry", 200, 3)
    g("DeleteMCEntries", 200, mctAllItems)
    assert g("GetMCEntry", 200, 0) == g("GetMCEntry", 200, 3) == 0
    assert g("GetMCEntry", 0, 0)                                # the bar's stays


def test_a_copy_of_the_table_can_be_put_back(qapp):
    g = Guest()
    g("SetMCEntries", 1, _entries(g, (200, 1, [BLACK, RED, BLACK, WHITE])))
    copy = g("GetMCInfo")
    assert g.contents(copy) == g.contents(g.process.world.r32(lowmem.MenuCInfo))
    g("DeleteMCEntries", 200, 1)
    assert not g("GetMCEntry", 200, 1)
    g("SetMCInfo", copy)
    assert _entry(g, g("GetMCEntry", 200, 1))[2][1] == RED
    g("DisposeMCInfo", copy)
    assert not g.heap.is_handle(copy)


def _mctb(*entries) -> bytes:
    return len(entries).to_bytes(2, "big") + b"".join(mct_entry(*e) for e in entries)


def test_get_menu_adds_its_mctb_with_color_quickdraw(qapp):
    """Glider 4's menus each have an 'mctb' of their ID."""
    resources = [Resource(b"MENU", 200, menu(200, "Game", [("Begin", ""), ("Quit", "Q")])),
                 Resource(b"mctb", 200, _mctb((200, 1, [BLACK, BLUE, BLACK, WHITE])))]
    g = Guest(resources, model="ii")
    g("GetMenu", 200)
    assert _entry(g, g("GetMCEntry", 200, 1))[2][1] == BLUE
    g = Guest(resources)                                        # a Plus: no Color Menu Manager
    g("GetMenu", 200)
    assert not g("GetMCEntry", 200, 1)


def test_init_menus_makes_the_table_with_color_quickdraw(qapp):
    """InitMenus makes the menu colour table, with the 'mctb' 0's entries,
    and ClearMenuBar empties it: Microsoft Word 4 reads it from MenuCInfo."""
    resources = [Resource(b"mctb", 0, _mctb((0, 0, [BLACK, WHITE, BLACK, YELLOW])))]
    g = Guest(resources, model="ii")
    g.tb._d = NoDisplay()
    g("InitMenus")
    table = g.process.world.r32(lowmem.MenuCInfo)
    assert table and _entry(g, g("GetMCEntry", 0, 0))[2][3] == YELLOW
    g("ClearMenuBar")
    assert g.process.world.r32(lowmem.MenuCInfo) == table
    assert g("GetMCEntry", 0, 0) == 0 and g.heap.handle_size(table) == MCT_ENTRY
    g = Guest(resources)                                        # no Color QuickDraw
    g.tb._d = NoDisplay()
    g("InitMenus")
    assert g.process.world.r32(lowmem.MenuCInfo) == 0


def test_init_windows_makes_the_default_auxiliary_records(qapp):
    """With Color QuickDraw: Microsoft Word 4 reads the default control
    record's colour table from AuxCtlHead."""
    g = Guest(model="ii")
    g.process.resources.error = 0
    g("InitWindows")
    for head, standard in ((lowmem.AuxWinHead, STANDARD_WCTB),
                           (lowmem.AuxCtlHead, STANDARD_CCTB)):
        h = g.mem.r32(head)
        assert h and find_aux_win(g.mem, 0, head) == h
        assert g.contents(g.mem.r32(deref(g.mem, h) + 8)) == color_table(standard)
    assert g.process.resources.error == 0
    g("InitWindows")                                            # not made twice
    assert all(len(list(aux_wins(g.mem, head))) == 1
               for head in (lowmem.AuxWinHead, lowmem.AuxCtlHead))
    g = Guest()
    g("InitWindows")
    assert g.mem.r32(lowmem.AuxWinHead) == g.mem.r32(lowmem.AuxCtlHead) == 0


def test_an_item_without_an_entry_has_its_menus_or_the_bars_colours():
    colors = MenuColors([mct_entry(0, 0, [RED, YELLOW, BLUE, WHITE]),
                         mct_entry(200, 0, [BLUE, BLACK, RED, WHITE]),
                         mct_entry(200, 2, [RED, BLUE, YELLOW, BLACK])])
    assert colors.bar() == WHITE
    assert colors.title(200) == (BLUE, BLACK) and colors.title(300) == (RED, WHITE)
    assert colors.background(200) == WHITE and colors.background(300) == YELLOW
    assert colors.item(200, 2) == (RED, BLUE, YELLOW, BLACK)
    assert colors.item(200, 1) == (RED, RED, RED, WHITE)       # the menu's
    assert colors.item(300, 1) == (BLUE, BLUE, BLUE, YELLOW)   # the bar's
    assert not MenuColors([])


def _colours(pd, index):
    """The two colours most of an item's row is: its background, then its
    text (whose edges Qt blends)."""
    img = pd.grab().toImage()
    r = pd.item_rect(index)
    seen = Counter(img.pixelColor(x, y).rgb() & 0xFFFFFF
                   for y in range(r.top(), r.bottom() + 1) for x in range(r.left(), r.right() + 1))
    return [c for c, _ in seen.most_common(2)]


def _rgb(c):
    return QColor(c[0] >> 8, c[1] >> 8, c[2] >> 8).rgb() & 0xFFFFFF


def test_a_pulled_down_menu_is_drawn_in_its_colours(qapp):
    m = Menu(200, "Game", parse_menu_items("Begin;Quit"))
    colors = MenuColors([mct_entry(200, 0, [BLACK, WHITE, BLACK, YELLOW]),
                         mct_entry(200, 2, [BLACK, BLUE, BLACK, WHITE])])
    pd = Pulldown(m, None, None, colors)
    try:
        assert _colours(pd, 1) == [_rgb(YELLOW), _rgb(BLACK)]    # the menu's
        assert _colours(pd, 2) == [_rgb(WHITE), _rgb(BLUE)]      # its own
        pd.set_hilite(2)
        assert _colours(pd, 2) == [_rgb(BLUE), _rgb(WHITE)]      # swapped
    finally:
        pd.deleteLater()
    plain = Pulldown(m, None)
    try:
        assert _colours(plain, 2) == [_rgb(WHITE), _rgb(BLACK)]
    finally:
        plain.deleteLater()


def test_the_bar_and_its_titles_are_drawn_in_their_colours(qapp):
    game = Menu(200, "Game", parse_menu_items("Begin"))
    colors = MenuColors([mct_entry(0, 0, [BLACK, WHITE, BLACK, YELLOW]),
                         mct_entry(200, 0, [WHITE, BLUE, BLACK, WHITE])])
    proc = SimpleNamespace(bar_menus=lambda: [game], menu_colors=lambda: colors)
    bar = MenuBarWidget(SimpleNamespace(application_menu_for=lambda bar: None))
    try:
        bar.resize(300, bar.height())
        bar.process = proc
        img = bar.image()
        (_, cell), = bar.cells()
        assert img.pixel(cell.right() + 20, 5) & 0xFFFFFF == _rgb(YELLOW)
        assert img.pixel(cell.left() + 1, 2) & 0xFFFFFF == _rgb(BLUE)
        bar.hilite_id = 200
        assert bar.image().pixel(cell.left() + 1, 2) & 0xFFFFFF == _rgb(WHITE)
    finally:
        bar.deleteLater()

"""Menu definition procedures: an application's own, and the System's
MDEF 0 for the 68k code that calls it."""

from PyQt6.QtGui import QColor, QImage

from macrt.m68k import mdefs
from macrt.toolbox import constants as k
from macrt.toolbox import lowmem
from macrt.toolbox.menus import MENU_PROC, MenuInfo, parse_menu_items
from macrt.toolbox.qdraw import ImageSurface
from macrt.toolbox.types import Point, Rect
from macrt.ui import theme

from guest import Guest

ITEMS = "Alpha;Beta/B;(Gamma;-;Delta"       # Gamma disabled, then a line


def _menu(g, menu_id=300):
    m = MenuInfo.new(g.system, g.heap, menu_id, "Spells", g.system.defproc("MDEF", 0))
    m.append(parse_menu_items(ITEMS))
    return m


def _wmgr(g):
    """The Window Manager port, made the current port, as an application's
    MDEF is called in it."""
    port = g.system.port_at(g.mem.r32(lowmem.WMgrPort))
    g.set_port(port)
    return port


def _mdef_0(g, msg, m, rect=Rect(0, 0, 0, 0), hit=Point(0, 0), item=0):
    """Send MDEF 0 a message: menuRect and whichItem as it leaves them."""
    rp = g.rect_ptr(rect)
    ip = g.ptr((item & 0xFFFF).to_bytes(2, "big"))
    g("SystemMDEF0", msg, m.handle, rp, hit, ip)
    return g.mem.r_rect(rp), g.mem.r16s(ip)


def _line(g):
    asc, desc, _, leading = g.tb.GetFontInfo()
    return asc + desc + leading


def _image(rect):
    img = QImage(rect.width, rect.height, QImage.Format.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    return img


def _black(img, x, y):
    return img.pixel(x, y) & 0xFFFFFF == 0


def _inked(img, top, bottom):
    """How many black pixels the rows top to bottom have."""
    return sum(_black(img, x, y) for y in range(top, bottom) for x in range(img.width()))


def test_mdef_0_sizes_a_menu_in_the_current_ports_font(qapp):
    """Theldrow's MDEF sets the port's font, then leaves its menus to MDEF
    0: each item is a line of that font, and the menu is as wide as its
    widest item, with room for the mark and Command keys."""
    g = Guest()
    m = _menu(g)
    port = _wmgr(g)
    _mdef_0(g, k.mSizeMsg, m)
    widest = max(g.tb.StringWidth(s) for s in ("Alpha", "Beta", "Gamma", "Delta"))
    key = g.tb.StringWidth(k.commandMark + "B")
    assert m.size == (theme.MENU_LEFT_PAD + widest + theme.MENU_RIGHT_PAD + theme.MENU_KEY_GAP
                      + key, 5 * _line(g))
    small = m.size
    port.tx_size = 24
    _mdef_0(g, k.mSizeMsg, m)
    assert m.size[0] > small[0] and m.size[1] == 5 * _line(g) > small[1]


def test_mdef_0_draws_its_items_and_highlights_the_one_chosen(qapp):
    """mDrawMsg draws the items down from TopMenuItem; mChooseMsg inverts
    the enabled item under the mouse, un-inverting the last, and says
    which it is: none for a disabled item, a line or outside the menu."""
    g = Guest()
    m = _menu(g)
    port = _wmgr(g)
    _mdef_0(g, k.mSizeMsg, m)
    w, h = m.size
    line = _line(g)
    rect = Rect(40, 30, 40 + h, 30 + w)
    img = _image(rect)
    g.tb.qd.surfaces[port.addr] = ImageSurface(img, rect)
    g.mem.w16(lowmem.TopMenuItem, rect.top)
    _mdef_0(g, k.mDrawMsg, m, rect)
    assert all(_inked(img, i * line, (i + 1) * line) for i in (0, 1, 2, 4))
    mid = 3 * line + line // 2                  # the line: grey across the menu
    assert _black(img, 10, mid) != _black(img, 11, mid)
    margin = 1                                  # left of the text: white unless inverted
    assert not _black(img, margin, line + 1)

    def choose(v, item):
        return _mdef_0(g, k.mChooseMsg, m, rect, Point(rect.top + v, rect.left + 5), item)[1]

    assert choose(line + 2, 0) == 2
    assert _black(img, margin, line + 1) and not _black(img, margin, 1)
    assert choose(2, 2) == 1
    assert _black(img, margin, 1) and not _black(img, margin, line + 1)
    assert choose(2 * line + 2, 1) == 0                 # Gamma's disabled
    assert not _black(img, margin, 1) and not _black(img, margin, 2 * line + 1)
    assert choose(mid, 0) == 0
    assert choose(h + 10, 0) == 0
    assert choose(4 * line + 2, 0) == 5


def test_mdef_0_puts_a_pop_up_menu_with_its_item_at_the_point(qapp):
    """mPopUpMsg's hitPt has the top in its h and the left in its v: the
    item goes there, and the menu's top is TopMenuItem; but the menu
    stays below the menu bar."""
    g = Guest()
    m = _menu(g)
    _wmgr(g)
    _mdef_0(g, k.mSizeMsg, m)
    w, h = m.size
    line = _line(g)
    r, _ = _mdef_0(g, k.mPopUpMsg, m, hit=Point(100, 150), item=3)
    assert r == Rect(150 - 2 * line, 100, 150 - 2 * line + h, 100 + w)
    assert g.mem.r16s(lowmem.TopMenuItem) == r.top
    r, _ = _mdef_0(g, k.mPopUpMsg, m, hit=Point(100, 25), item=5)
    assert r.top == g.mem.r16s(lowmem.MBarHeight) + 1 and r.height == h


def _s16(n):
    n &= 0xFFFF
    return n - 0x10000 if n & 0x8000 else n


def _own_mdef(g, m):
    """Give m an MDEF of its own, at $100000 for g's procs."""
    code = g.handle(bytes.fromhex("4EF9 0010 0000"))                # JMP $100000
    g.mem.w32(m.ptr + MENU_PROC, code)
    return g.heap.deref(code)


def test_an_own_mdef_is_sent_messages_in_the_window_manager_port(qapp):
    g = Guest()
    m = _menu(g)
    assert not m.own_mdef and mdefs.entry(g, m) == 0
    at = _own_mdef(g, m)
    assert m.own_mdef and mdefs.entry(g, m) == at
    seen = []
    a5_port = g.mem.r32(g.process.partition.a5)
    g.procs[at] = lambda *args: seen.append((args, g.mem.r32(a5_port)))
    port, _ = g.port()
    assert mdefs.message(g, m, k.mChooseMsg, 0x1234, 0x00100020, 0x5678)
    assert seen == [((k.mChooseMsg, m.handle, 0x1234, 0x00100020, 0x5678),
                     g.mem.r32(lowmem.WMgrPort))]
    assert g.mem.r32(a5_port) == port.addr
    g.mem.write(at, bytes.fromhex("4E75"))                            # RTS: nothing to run
    assert mdefs.entry(g, m) == 0 and not mdefs.message(g, m, k.mDrawMsg, 0)


def test_an_own_mdef_through_a_handle_outside_the_heap(qapp):
    """The MacPaint demo's Tools and Patterns menus have handles of its own
    making for their MDEFs, master pointers in its globals."""
    g = Guest()
    m = _menu(g)
    at = g.ptr(bytes.fromhex("4EF9 0010 0000"))                    # JMP $100000
    a5 = g.process.partition.a5
    g.mem.w32(a5 - 8, at)                                           # the master pointer
    g.mem.w32(m.ptr + MENU_PROC, a5 - 8)
    assert m.own_mdef and mdefs.entry(g, m) == at
    seen = []
    g.procs[at] = lambda *args: seen.append(args[0])
    assert mdefs.message(g, m, k.mSizeMsg, 0) and seen == [k.mSizeMsg]
    g.mem.w32(a5 - 8, 0)
    assert not m.own_mdef


def test_menus_has_an_own_mdef_size_draw_choose_and_pop_up_its_menu(qapp):
    """The host's tracker asks Menus for what an own MDEF draws: here one
    that sets its font and leaves the rest to MDEF 0, as Theldrow's does."""
    g = Guest()
    m = _menu(g)
    at = _own_mdef(g, m)

    def mdef(msg, h, rect_p, hit, item_p):
        port = g.system.port_at(g.mem.r32(g.mem.r32(g.process.partition.a5)))
        port.tx_size = 18
        g("SystemMDEF0", msg, h, rect_p, Point(_s16(hit >> 16), _s16(hit)), item_p)

    g.procs[at] = mdef
    menus = mdefs.Menus(g, popup=m)
    rect, img = menus.draw(m.id, 20, 30)
    w, h = m.size
    assert rect == Rect(20, 30, 20 + h, 30 + w) and (img.width(), img.height()) == (w, h)
    line = h // 5
    assert line > 16 and _inked(img, 0, line)           # in its 18-point font
    item, now = menus.choose(m.id, Point(rect.top + line + 2, rect.left + 5), 0)
    assert item == 2 and _black(now, 1, line + 1)
    rect, img = menus.popup(m.id, 150, 100, 3)
    assert rect == Rect(150 - 2 * line, 100, 150 - 2 * line + h, 100 + w)
    item, now = menus.choose(m.id, Point(150 + 2, 105), 0)
    assert item == 0                                    # Gamma: disabled
    item, now = menus.choose(m.id, Point(150 + 2 * line + 2, 105), 0)
    assert item == 5

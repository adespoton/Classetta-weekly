"""Pop-up menu controls: the System's CDEF 63 (procIDs 1008 to 1023),
which macrt draws and tracks itself."""

from contextlib import nullcontext
from types import SimpleNamespace

from PyQt6.QtGui import QColor, QImage

from macrt.m68k import glue_controls, popups
from macrt.resfork import Resource
from macrt.toolbox import constants as k
from macrt.toolbox.controls import Control
from macrt.toolbox.qdraw import ImageSurface, bold
from macrt.toolbox.types import Point, Rect
from macrt.toolbox.windows import WindowRecord

from builders import menu
from guest import Guest

MENU_ID = 200
ITEMS = [("Red", ""), ("Green", ""), ("A rather long sort of blue", "")]
CONTENT = Rect(80, 60, 200, 260)
BOUNDS = Rect(10, 10, 30, 190)


class Host:
    """The display, as far as pop-ups need it: the menu pops up and
    answers with the item `chosen`, noting the item it was put over and
    the marks the menu had."""

    def __init__(self, chosen=0):
        self.chosen = chosen
        self.seen = []
        self.bridge = SimpleNamespace(call=lambda fn, *args, serve=None: fn(*args))

    def track_popup(self, process, m, at, item):
        self.seen.append((m.id, at, item, [it.mark for it in m.items]))
        return self.chosen

    def refresh_bars(self):
        pass


def _guest(resources=()):
    g = Guest([Resource(b"MENU", MENU_ID, menu(MENU_ID, "Colours", ITEMS)), *resources])
    g.yielding = nullcontext
    g.tb._d = Host()
    return g


def _window(g):
    """A window drawn in an image, made the current port."""
    w = WindowRecord.new(g.system, g.process, g.heap, 0, CONTENT, "Pops", True,
                         k.documentProc, True, 0)
    img = QImage(CONTENT.width, CONTENT.height, QImage.Format.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    g.tb.qd.surfaces[w.addr] = ImageSurface(img, w.port_rect)
    g.set_port(w)
    return w, img


def _popup(g, w, title=b"Colour:", style=0, title_width=60, variation=0, ref_con=0):
    """NewControl's pop-up: contrlMin the MENU, contrlMax the title's
    width and contrlValue its style."""
    h = glue_controls.new_control(g, w, BOUNDS, title, True, style, MENU_ID, title_width,
                                  popups.CDEF_ID << 4 | variation, ref_con)
    return Control(g.mem, h)


def _data(g, c):
    return g.mem.r32(c.data)


def _black(img, x, y):
    return img.pixel(x, y) & 0xFFFFFF == 0


def _inked(img, r):
    return sum(_black(img, x, y) for y in range(r.top, r.bottom) for x in range(r.left, r.right))


def _param(pt):
    return (pt.v & 0xFFFF) << 16 | pt.h & 0xFFFF


def test_a_pop_up_is_made_an_ordinary_control_of_its_menus_items(qapp):
    g = _guest()
    w, _ = _window(g)
    c = _popup(g, w)
    assert (c.min, c.max, c.value) == (1, len(ITEMS), 1)
    assert c.action == glue_controls.ACTION_IN_RECORD          # tracked by the menu
    d = _data(g, c)
    assert g.mem.r32(d + popups.MENU_HANDLE) == g.process.resources.GetResource("MENU", MENU_ID)
    assert g.mem.r16(d + popups.MENU_ID) == MENU_ID
    assert g.mem.r16(d + popups.TITLE_WIDTH) == 60
    untitled = _popup(g, w, title_width=1)                      # 0 or 1: no title
    assert g.mem.r16(_data(g, untitled) + popups.TITLE_WIDTH) == 0


def test_the_title_style_and_justification_come_from_the_value(qapp):
    g = _guest()
    w, _ = _window(g)
    d = _data(g, _popup(g, w, style=bold << 8 | popups.teFlushRight & 0xFF))
    assert g.mem.r8(d + popups.TITLE_STYLE) == bold
    assert g.mem.r8s(d + popups.JUSTIFY) == popups.teFlushRight
    d = _data(g, _popup(g, w, style=popups.popupTitleNoStyle | bold << 8))
    assert g.mem.r8(d + popups.TITLE_STYLE) == 0


def test_the_title_and_the_box_with_its_item_and_arrow_are_drawn(qapp):
    g = _guest()
    w, img = _window(g)
    c = _popup(g, w)
    m = g.menu(g.process.resources.GetResource("MENU", MENU_ID))
    geo = popups._Geometry(g, c, m)
    assert geo.area.top >= BOUNDS.top and geo.area.bottom <= BOUNDS.bottom
    assert geo.box.left == BOUNDS.left + 60 and geo.box.right <= BOUNDS.right
    box = geo.box
    assert _inked(img, Rect(box.top + 2, BOUNDS.left, box.bottom - 2, box.left))      # title
    assert all(_black(img, box.left, v) for v in range(box.top, box.bottom))           # frame
    assert _black(img, box.right, box.bottom - 1)                                      # shadow
    text = Rect(box.top + 2, box.left + 2, box.bottom - 2, box.left + 40)
    assert _inked(img, text)                                                           # "Red"
    arrow = Rect(box.top + 2, box.right - 22, box.bottom - 2, box.right - 2)
    assert _inked(img, arrow)


def test_a_long_item_is_shortened_to_fit_the_box(qapp):
    g = _guest()
    w, img = _window(g)
    c = _popup(g, w)
    c.value = 3
    glue_controls._draw(g, c)
    m = g.menu(g.process.resources.GetResource("MENU", MENU_ID))
    box = popups._Geometry(g, c, m).box
    arrow = box.right - 1 - popups.ARROW_RIGHT - popups.ARROW_WIDTH
    assert not _inked(img, Rect(box.top + 2, arrow - 2, box.bottom - 2, arrow))


def test_a_click_hits_the_pop_up_only_inside_it_while_its_active(qapp):
    g = _guest()
    w, _ = _window(g)
    c = _popup(g, w)
    inside = _param(Point(BOUNDS.top + 10, BOUNDS.left + 100))
    assert glue_controls.message(g, c, k.testCntl, inside) == 1
    assert glue_controls.message(g, c, k.testCntl, _param(Point(5, 5))) == 0
    c.hilite = k.inactiveHilite
    assert glue_controls.message(g, c, k.testCntl, inside) == 0


def test_tracking_pops_the_menu_up_over_the_box_with_the_item_checked(qapp):
    g = _guest()
    w, _ = _window(g)
    c = _popup(g, w)
    c.value = 2
    g.tb._d.chosen = MENU_ID << 16 | 3
    pt = Point(BOUNDS.top + 10, BOUNDS.left + 100)
    assert glue_controls.TrackControl(g, c.handle, pt, glue_controls.ACTION_IN_RECORD) == 1
    m = g.menu(g.process.resources.GetResource("MENU", MENU_ID))
    box = popups._Geometry(g, c, m).box
    (menu_id, at, item, marks), = g.tb._d.seen
    assert (menu_id, item) == (MENU_ID, 2)
    assert at == w.local_to_global(Point(box.top + 1, box.left + 1))
    assert marks[1] == k.checkMark and marks[0] == marks[2] == k.noMark
    assert c.value == 3 and c.hilite == 0
    assert all(it.mark == k.noMark for it in m.items)                   # unchecked again


def test_letting_go_outside_the_menu_changes_nothing(qapp):
    g = _guest()
    w, _ = _window(g)
    c = _popup(g, w)
    pt = Point(BOUNDS.top + 10, BOUNDS.left + 100)
    assert glue_controls.TrackControl(g, c.handle, pt, 0) == 0          # NIL: the menu too
    assert len(g.tb._d.seen) == 1 and c.value == 1


def test_use_add_res_menu_adds_the_resource_types_names(qapp):
    g = _guest([Resource(b"snd ", 1, b"", b"Zap"), Resource(b"snd ", 2, b"", b"Boing"),
                Resource(b"snd ", 3, b"", b".Hidden")])
    w, _ = _window(g)
    c = _popup(g, w, variation=popups.popupUseAddResMenu, ref_con=int.from_bytes(b"snd ", "big"))
    m = g.menu(g.process.resources.GetResource("MENU", MENU_ID))
    assert [it.text for it in m.items][len(ITEMS):] == ["Boing", "Zap"]
    assert c.max == len(ITEMS) + 2


def test_disposing_of_a_pop_up_releases_its_menu(qapp, monkeypatch):
    g = _guest()
    w, _ = _window(g)
    c = _popup(g, w)
    rm = g.process.resources
    h = rm.GetResource("MENU", MENU_ID)
    released = []
    real = rm.ReleaseResource
    monkeypatch.setattr(rm, "ReleaseResource", lambda r: (released.append(r), real(r)))
    g("DisposeControl", c.handle)
    assert released == [h]
    assert w.control_list == 0


def test_a_pop_up_keeps_its_menu_when_its_file_isnt_current(qapp):
    """Text, a control panel, fills its pop-ups' menus with the System's
    file current, where their MENUs can't be found: the menu the control
    has is still the one it draws."""
    g = _guest()
    w, img = _window(g)
    c = _popup(g, w)
    rm = g.process.resources
    h = g.mem.r32(_data(g, c) + popups.MENU_HANDLE)
    rm.UseResFile(rm.sys_refnum)
    g("AppendMenu", h, g.ptr(b"\x05Mauve"))
    c.max = len(ITEMS) + 1
    g("SetControlValue", c.handle, len(ITEMS) + 1)
    assert popups._menu(g, c).handle == h == g.mem.r32(_data(g, c) + popups.MENU_HANDLE)
    assert c.value == len(ITEMS) + 1
    g("DisposeMenu", h)                         # gone: it's looked for again
    assert popups._menu(g, c) is None

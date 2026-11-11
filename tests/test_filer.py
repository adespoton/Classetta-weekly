"""The Filer window a disk image opens in when no --app names what to run."""

import machfs
import os
import pytest
import struct
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtTest import QTest

from conftest import LB, NO_MODS, Recorder
from macrt.demo import finish, open_targets, parse_args
from macrt.macfile import ContainerFolder, HostFolder, MacFile, open_disks
from macrt.resfork import build_fork, Resource, resPurgeable
from macrt.toolbox import constants as k
from macrt.ui import theme
from macrt.ui.filer import ARCHIVE_ICON, SPECIAL_MENU_ID, FilerOptions, _container_icon
from macrt.ui.stdfile import DISK_ICON, DOCUMENT_ICON, FOLDER_ICON
from builders import binhex
from test_files import FORK, apple_single, macbinary


def _volume(games: bool = True) -> machfs.Volume:
    v = machfs.Volume()
    v.name = "Browse"
    app = machfs.File()
    app.type, app.creator, app.rsrc = b"APPL", b"TEST", bytearray(FORK)
    v["Widget"] = app
    doc = machfs.File()
    doc.type, doc.creator, doc.data = b"TEXT", b"TEST", b"Hello."
    v["Letter"] = doc
    if games:
        games_ = machfs.Folder()
        game = machfs.File()
        game.type, game.creator, game.rsrc = b"APPL", b"TEST", bytearray(FORK)
        games_["Game"] = game
        v["Games"] = games_
    return v


def _disk(tmp_path):
    p = tmp_path / "browse.dsk"
    p.write_bytes(_volume().write(800 * 1024))
    return p


def _icon_folder_volume() -> machfs.Volume:
    """A disk whose folder keeps its own icon: all black at 32 by 32."""
    v = machfs.Volume()
    v.name = "Custom"
    folder = machfs.Folder()
    icon = machfs.File()
    icon.rsrc = bytearray(build_fork([Resource(b"ICN#", 128, bytes([0xFF]) * 256)]))
    folder["Icon\r"] = icon
    v["Mystery"] = folder
    return v


def _n_volume() -> machfs.Volume:
    """A disk whose only file's name begins as the header's Name does."""
    v = machfs.Volume()
    v.name = "Browse"
    note = machfs.File()
    note.data = b"Hello."
    v["Nimbus"] = note
    return v


# -- what the command line asks for ---------------------------------------
def test_browse_leaves_every_application_to_the_window(tmp_path):
    apps, disks = open_disks([_disk(tmp_path)], browse=True)
    assert apps == []
    assert [v.name for v in disks] == ["Browse"]


def test_browse_still_takes_loose_files(tmp_path):
    lone = tmp_path / "Lone.bin"
    lone.write_bytes(macbinary("Lone", b"", FORK))
    apps, disks = open_disks([lone, _disk(tmp_path)], browse=True)
    assert [f.name for f in apps] == ["Lone"]
    assert len(disks) == 1


def test_without_browse_the_only_application_still_runs(tmp_path):
    v = _volume(games=False)
    p = tmp_path / "one.dsk"
    p.write_bytes(v.write(800 * 1024))
    apps, disks = open_disks([p])
    assert [f.name for f in apps] == ["Widget"]
    assert len(disks) == 1


def test_open_targets_shows_the_disk_in_a_finder_window(tmp_path):
    args = parse_args([str(_disk(tmp_path))])
    targets, disks, finder, error = open_targets(args)
    assert error is None
    assert targets == []
    assert finder == disks and len(disks) == 1


def test_open_targets_with_app_picks_the_application(tmp_path):
    args = parse_args([str(_disk(tmp_path)), "--app", "Widget"])
    targets, disks, finder, error = open_targets(args)
    assert error is None
    assert [f.name for f, _ in targets] == ["Widget"]
    assert finder == []


def test_list_keeps_the_old_pick(tmp_path):
    v = _volume(games=False)
    p = tmp_path / "one.dsk"
    p.write_bytes(v.write(800 * 1024))
    args = parse_args([str(p), "--list"])
    targets, disks, finder, error = open_targets(args)
    assert error is None
    assert targets == []
    assert finder == []
    assert len(disks) == 1


# -- the window itself ------------------------------------------------------
def _rows(win):
    return [(win.tree.topLevelItem(i).text(0), win.tree.topLevelItem(i).text(2))
            for i in range(win.tree.topLevelItemCount())]


def _item(win, name):
    return next(win.tree.topLevelItem(i) for i in range(win.tree.topLevelItemCount())
                if win.tree.topLevelItem(i).text(0) == name)


def _ink(img, y, x0, x1):
    """The first black pixel of a row between x0 and x1, or None."""
    for x in range(x0, x1):
        r, g, b, _ = img.pixelColor(x, y).getRgb()
        if r < 128 and g < 128 and b < 128:
            return x
    return None


def _label_lefts(win, name, after):
    """The x of the header's Name label and of a row of the same first letter."""
    img = win.tree.grab().toImage()
    hdr = win.tree.header()
    rows = range(hdr.geometry().top() + 1, hdr.geometry().bottom())
    head = min((x for y in rows
                if (x := _ink(img, y, after, 170)) is not None), default=None)
    rect = win.tree.visualItemRect(_item(win, name))
    y = win.tree.viewport().geometry().top() + rect.y() + rect.height() // 2
    return head, _ink(img, y, 21, 170)


def _lock_left(win):
    """The x of the header's padlock at the header's middle row."""
    img = win.tree.grab().toImage()
    hdr = win.tree.header()
    return _ink(img, hdr.geometry().top() + hdr.height() // 2, 0, 17)


def _dblclick(win, name, settle):
    """A real double-click: click, then click again on the same spot."""
    c = win.tree.visualItemRect(_item(win, name)).center()
    vp = win.tree.viewport()
    QTest.mousePress(vp, LB, NO_MODS, c)
    QTest.mouseRelease(vp, LB, NO_MODS, c)
    settle(30)
    QTest.mouseDClick(vp, LB, NO_MODS, c)
    settle(150)


def _front_the_filer(h, win):
    """Click in a Filer window's list, so its own menus come back to the bar."""
    c = win.tree.visualItemRect(_item(win, "Games")).center()
    h.click(*h.mac(win.tree.viewport(), c))
    h.settle()
    assert h.d.front_filer is win


def test_the_window_lists_the_folder(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert win.isVisible()
    assert _rows(win) == [("Games", "folder"), ("Letter", "document"),
                          ("Widget", "application")]
    assert win in h.d.filer_windows


def test_the_name_column_fits_32_Ws_without_truncating(harness):
    h = harness(disks=[_n_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    fm = QFontMetrics(win.tree.font())
    assert win.tree.columnWidth(0) >= fm.horizontalAdvance("W" * 32)


def test_the_header_wears_the_lock_while_the_window_is_view_only(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert not win.tree.headerItem().icon(0).isNull()
    assert win.tree.headerItem().text(0) == "Name"      # beside it, not instead of it


def test_a_window_that_can_be_modified_would_wear_no_lock(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0], options=FilerOptions(writable=True))
    h.settle()
    assert win.tree.headerItem().icon(0).isNull()


def test_the_name_label_begins_where_the_file_names_begin(harness):
    h = harness(disks=[_n_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert _lock_left(win) == 8
    head, nimbus = _label_lefts(win, "Nimbus", after=17)
    assert abs(head - nimbus) <= 2


def test_the_name_label_begins_where_the_file_names_begin_without_the_lock(harness):
    h = harness(disks=[_n_volume()])
    win = h.d.open_filer(h.d.config.disks[0], options=FilerOptions(writable=True))
    h.settle()
    assert _lock_left(win) is None
    head, nimbus = _label_lefts(win, "Nimbus", after=0)
    assert abs(head - nimbus) <= 2


# -- what the title bar wears -----------------------------------------------
def test_the_title_bar_wears_the_disk_icon_at_the_root(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert win.frame().title_icon == DISK_ICON


def test_the_title_bar_wears_the_folder_icon_inside(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0], ("Games",))
    h.settle()
    assert win.frame().title_icon == FOLDER_ICON


def test_a_folder_with_its_own_icon_wears_it_in_the_title_bar(harness):
    h = harness(disks=[_icon_folder_volume()])
    win = h.d.open_filer(h.d.config.disks[0], ("Mystery",))
    h.settle()
    assert win.frame().title_icon == ["#" * 16] * 16


def test_a_file_container_wears_what_the_file_is():
    v = machfs.Volume()
    v.name = "Files"
    packed = machfs.File()
    packed.data = b"SIT!" + bytes(6) + b"rLau"
    v["Pack.sit"] = packed
    text = machfs.File()
    text.data = b"Hello."
    v["Letter"] = text
    assert _container_icon(v, ("Pack.sit",)) == ARCHIVE_ICON
    assert _container_icon(v, ("Letter",)) == DOCUMENT_ICON


def test_a_file_wears_its_own_icon_only_when_marked_as_having_one():
    v = machfs.Volume()
    v.name = "Files"
    icon_rsrc = bytearray(build_fork([Resource(b"ICON", 128, bytes([0xFF]) * 128)]))
    marked = machfs.File()
    marked.data, marked.flags = b"Text.", 0x0400      # kHasCustomIcon
    marked.rsrc = icon_rsrc
    v["Marked"] = marked
    plain = machfs.File()
    plain.data, plain.rsrc = b"Text.", bytearray(icon_rsrc)
    v["Plain"] = plain
    assert _container_icon(v, ("Marked",)) == ["#" * 16] * 16
    assert _container_icon(v, ("Plain",)) == DOCUMENT_ICON


def test_the_same_folder_is_one_window(harness):
    h = harness(disks=[_volume()])
    volume = h.d.config.disks[0]
    win = h.d.open_filer(volume)
    assert h.d.open_filer(volume) is win
    assert h.d.filer_windows == [win]


def test_double_click_launches_the_application(harness, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    launched = []
    monkeypatch.setattr(h.d, "launch",
                        lambda name, main, **kw: launched.append((name, main, kw)))
    _dblclick(win, "Widget", h.settle)
    h.settle()
    assert [(n, kw["app"].name) for n, _, kw in launched] == [("Widget", "Widget")]
    assert win in h.d.filer_windows       # the window carries on


def test_a_document_opens_with_its_creator(harness, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    launched = []
    monkeypatch.setattr(h.d, "launch",
                        lambda name, main, **kw: launched.append((name, kw)))
    _dblclick(win, "Letter", h.settle)
    h.settle()
    assert [n for n, _ in launched] == ["Widget"]
    assert [d.name for d in launched[0][1]["app"].documents] == ["Letter"]


def test_double_click_a_folder_opens_its_window(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    _dblclick(win, "Games", h.settle)
    h.settle()
    assert len(h.d.filer_windows) == 2
    child = h.d.filer_windows[1]
    assert child.path == ("Games",)
    assert [name for name, _ in _rows(child)] == ["Game"]
    assert child.frame().title == "Games"


def test_the_close_box_closes_the_window(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    o = win.mac_origin()
    box = win.box_rect(4)                   # wInGoAway
    assert box is not None
    h.click(o.h + box.x() + 5, o.v + box.y() + 5)
    h.wait_until(lambda: win not in h.d.filer_windows, what="the finder to close")
    assert h.d.shutting_down                # it was all that was up: macrt quits


def test_a_second_window_survives_the_first_closing(harness):
    h = harness(disks=[_volume()])
    volume = h.d.config.disks[0]
    win = h.d.open_filer(volume)
    child = h.d.open_filer(volume, ("Games",))
    h.settle()
    child.close()                           # closing its box goes through closeEvent
    h.wait_until(lambda: child not in h.d.filer_windows, what="the folder window to close")
    assert win in h.d.filer_windows
    assert not h.d.shutting_down


def _file_menu_open_enabled(h) -> bool:
    """File > Open as the bar itself would draw it: through bar_menus."""
    for menu, _cell in h.d.global_bar.cells():
        if menu.title == "File":
            return menu.items[0].enabled
    raise AssertionError("the menu bar is showing no File menu")


def test_file_open_menu_item_enabled_state(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert _file_menu_open_enabled(h) is False       # nothing is selected
    win.tree.setCurrentItem(_item(win, "Games"))
    h.settle()
    assert _file_menu_open_enabled(h) is True        # a folder is selected


def test_file_open_opens_selected_item(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Games"))
    h.settle()
    win.open_selected()
    h.settle()
    assert len(h.d.filer_windows) == 2
    assert h.d.front_filer.path == ("Games",)


def test_the_file_menu_pulls_down_and_opens(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Games"))
    h.settle()
    h.choose(h.d.global_bar, "File", 1)
    h.wait_until(lambda: len(h.d.filer_windows) == 2, what="the folder window")
    assert h.d.front_filer.path == ("Games",)


def test_the_apple_menu_opens_about_classetta(harness):
    h = harness(disks=[_volume()])
    h.d.open_filer(h.d.config.disks[0])
    h.settle()
    h.choose(h.d.global_bar, k.APPLE_MENU_TITLE, 1)
    h.wait_until(lambda: len(h.d.about_windows) == 1, what="the About window")
    assert h.d.front_filer is not None             # the Filer is still front
    h.d.about_windows[0].close()
    h.settle()
    assert h.d.about_windows == []


def test_about_classetta_appears(harness):
    h = harness(disks=[_volume()])
    h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert len(h.d.about_windows) == 0
    h.d.show_about_classetta()
    h.settle()
    assert len(h.d.about_windows) == 1
    about = h.d.about_windows[0]
    assert about.windowTitle() == "About Classetta"
    assert any("Classetta" in line for line in about._lines)
    assert any(line.startswith("Total Memory") for line in about._lines)
    assert any(line.startswith("Largest Unused Block") for line in about._lines)
    assert about._logo_icon in (theme.MAC_II_ICON, theme.MAC_PLUS_ICON)
    assert about._processes[0][0] == "System"      # the System heap is listed
    about.close()
    h.settle()


def test_about_window_can_be_dragged(harness):
    h = harness(disks=[_volume()])
    h.d.open_filer(h.d.config.disks[0])
    h.settle()
    h.d.show_about_classetta()
    h.settle()
    about = h.d.about_windows[0]
    start_pos = about.pos()
    o = about.mac_origin()
    h.press(o.h + 40, o.v + 10)
    h.move(o.h + 80, o.v + 30)
    h.release(o.h + 80, o.v + 30)
    h.settle()
    assert about.pos() != start_pos
    about.close()
    h.settle()


def test_about_window_close_box_closes_it(harness):
    h = harness(disks=[_volume()])
    h.d.open_filer(h.d.config.disks[0])
    h.settle()
    h.d.show_about_classetta()
    h.settle()
    about = h.d.about_windows[0]
    o = about.mac_origin()
    box = about.box_rect(4)                   # wInGoAway
    assert box is not None
    h.click(o.h + box.x() + 5, o.v + box.y() + 5)
    h.wait_until(lambda: about not in h.d.about_windows,
                 what="the About window to close")


@pytest.mark.parametrize("host", ["screen", "desktop"])
def test_control_opens_the_selection(harness, host):
    h = harness(disks=[_volume()], host=host)
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setFocus()
    win.tree.setCurrentItem(_item(win, "Games"))
    h.settle()
    QTest.keyClick(win.tree, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
    h.settle()
    assert len(h.d.filer_windows) == 2
    assert h.d.front_filer.path == ("Games",)


def test_the_bar_goes_to_an_application_and_back(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert h.d.global_bar.process is h.d.filer_menus
    alpha = h.launch(Recorder("Alpha", at=(30, 60)))
    h.wait_until(lambda: h.d.front_process is alpha, what="Alpha to come forward")
    assert h.d.front_filer is None
    assert h.d.global_bar.process is alpha
    c = win.tree.visualItemRect(_item(win, "Games")).center()
    h.click(*h.mac(win.tree.viewport(), c))         # click back into the Filer
    h.settle()
    assert h.d.front_filer is win
    assert h.d.global_bar.process is h.d.filer_menus


def test_keys_typed_in_the_filer_are_not_left_for_an_application(harness, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    alpha = Recorder("Alpha", at=(30, 60))
    proc = h.launch(alpha)
    h.wait_until(lambda: h.d.front_process is proc, what="Alpha to come forward")
    c = win.tree.visualItemRect(_item(win, "Games")).center()
    h.click(*h.mac(win.tree.viewport(), c))         # the Filer is front again
    h.settle()
    posted = []
    post = proc.events.post

    def spy(ev):
        posted.append(ev.what)
        return post(ev)

    monkeypatch.setattr(proc.events, "post", spy)
    QTest.keyClick(win, Qt.Key.Key_A)               # a keystroke in the Filer
    h.settle()
    assert posted == []                             # Alpha behind it gets none


def test_control_w_closes_the_front_filer_window(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setFocus()
    QTest.keyClick(win.tree, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    h.settle()
    assert win not in h.d.filer_windows
    assert h.d.front_filer is None


def _file_menu_info_enabled(h) -> bool:
    """File > Get Info as the bar itself would draw it: through bar_menus."""
    for menu, _cell in h.d.global_bar.cells():
        if menu.title == "File":
            return menu.items[2].enabled
    raise AssertionError("the menu bar is showing no File menu")


def test_file_info_menu_item_enabled_state(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert _file_menu_info_enabled(h) is False       # nothing is selected
    win.tree.setCurrentItem(_item(win, "Games"))
    h.settle()
    assert _file_menu_info_enabled(h) is True        # an item is selected


def test_control_i_opens_get_info_window(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setFocus()
    win.tree.setCurrentItem(_item(win, "Games"))
    h.settle()
    QTest.keyClick(win.tree, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    h.settle()
    assert len(h.d.info_windows) == 1
    assert "Games Info" in h.d.info_windows[0].windowTitle()
    h.d.info_windows[0].close()
    h.settle()
    assert h.d.info_windows == []


def test_file_menu_get_info_opens_window(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Widget"))
    h.settle()
    h.choose(h.d.global_bar, "File", 3)
    h.wait_until(lambda: len(h.d.info_windows) == 1, what="the Get Info window")
    assert "Widget Info" in h.d.info_windows[0].windowTitle()
    h.d.info_windows[0].close()
    h.settle()
    assert h.d.info_windows == []


def test_control_w_closes_get_info_window_when_front(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Widget"))
    h.settle()
    win.get_info()
    h.settle()
    assert len(h.d.info_windows) == 1
    info_win = h.d.info_windows[0]
    info_win.setFocus()
    info_win.activateWindow()
    h.settle()
    QTest.keyClick(info_win, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    h.settle()
    assert len(h.d.info_windows) == 0
    assert win in h.d.filer_windows



def test_get_info_displays_minimum_and_desired_heap(harness):
    v = _volume()
    app = machfs.File()
    app.type, app.creator = b"APPL", b"TEST"
    app.rsrc = build_fork([Resource(b"SIZE", 0, struct.pack(">HII", 0, 2000000, 1000000))])
    v["SizedApp"] = app
    h = harness(disks=[v])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "SizedApp"))
    h.settle()
    win.get_info()
    h.settle()
    assert len(h.d.info_windows) == 1
    info_win = h.d.info_windows[0]
    assert any("Minimum heap:" in line for line in info_win._lines)
    assert any("Desired heap:" in line for line in info_win._lines)
    info_win.close()
    h.settle()


def _file_menu_display_contents_enabled(h) -> bool:
    for menu, _cell in h.d.global_bar.cells():
        if menu.title == "File":
            return menu.items[3].enabled
    raise AssertionError("the menu bar is showing no File menu")


def test_file_display_contents_menu_item_enabled_state(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert _file_menu_display_contents_enabled(h) is False
    win.tree.setCurrentItem(_item(win, "Widget"))
    h.settle()
    assert _file_menu_display_contents_enabled(h) is True
    win.tree.setCurrentItem(_item(win, "Letter"))
    h.settle()
    assert _file_menu_display_contents_enabled(h) is True


def test_file_menu_display_contents_opens_window(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Letter"))
    h.settle()
    h.choose(h.d.global_bar, "File", 4)
    h.wait_until(lambda: len(h.d.viewer_windows) == 1, what="the Content Viewer window")
    assert "Letter" in h.d.viewer_windows[0].windowTitle()
    h.d.viewer_windows[0].close()
    h.settle()
    assert h.d.viewer_windows == []


def test_open_host_folder(harness, tmp_path):
    folder = tmp_path / "host"
    folder.mkdir()
    (folder / "test.txt").write_bytes(b"hello")
    subfolder = folder / "sub"
    subfolder.mkdir()
    (subfolder / "inner.txt").write_bytes(b"world")

    h = harness(disks=[])
    win = h.d.open_filer(HostFolder(folder))
    h.settle()
    assert win.windowTitle() == "host"
    assert _rows(win) == [("sub", "folder"), ("test.txt", "document")]
    win.tree.setCurrentItem(_item(win, "sub"))
    h.settle()
    win.open_selected()
    h.settle()
    assert len(h.d.filer_windows) == 2
    sub_win = h.d.filer_windows[1]
    assert sub_win.windowTitle() == "sub"
    assert _rows(sub_win) == [("inner.txt", "document")]
    sub_win.tree.setCurrentItem(_item(sub_win, "inner.txt"))
    h.settle()
    assert sub_win.selected_actions() == {"open", "info", "display_contents"}

    empty = tmp_path / "empty"
    empty.mkdir()
    h.d.open_filer(HostFolder(empty))
    h.settle()
    assert _rows(h.d.filer_windows[-1]) == []

    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "ok.txt").write_bytes(b"ok")
    (bad / "bad.bin").write_bytes(b"not a mac file")
    bad_win = h.d.open_filer(HostFolder(bad))
    h.settle()
    assert _rows(bad_win) == [("bad.bin", "document"), ("ok.txt", "document")]

    inaccessible = tmp_path / "inaccessible"
    inaccessible.mkdir()
    inaccessible.chmod(0o000)
    h.d.open_filer(HostFolder(inaccessible))
    h.settle()
    assert _rows(h.d.filer_windows[-1]) == []
    inaccessible.chmod(0o755)


def test_control_space_opens_content_viewer(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setFocus()
    win.tree.setCurrentItem(_item(win, "Letter"))
    h.settle()
    for menu, _cell in h.d.global_bar.cells():          # the item draws ⌘ over a space
        if menu.title == "File":
            assert menu.items[3].key == " "
    QTest.keyClick(win.tree, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    h.wait_until(lambda: len(h.d.viewer_windows) == 1, what="the Content Viewer window")
    assert "Letter" in h.d.viewer_windows[0].windowTitle()
    h.d.viewer_windows[0].close()
    h.settle()
    assert h.d.viewer_windows == []


def test_content_viewer_ordinary_and_text_only_fork(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Letter"))
    h.settle()
    win.display_contents()
    h.settle()
    assert len(h.d.viewer_windows) == 1
    viewer = h.d.viewer_windows[0]
    assert "Hello" in viewer.text_edit.toPlainText()
    viewer.checkbox.setChecked(True)
    h.settle()
    assert "Hello" in viewer.text_edit.toPlainText()
    viewer.close()
    h.settle()


def test_content_viewer_resource_only_file(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Widget"))
    h.settle()
    assert _file_menu_display_contents_enabled(h) is True
    win.display_contents()
    h.settle()
    viewer = h.d.viewer_windows[-1]
    rows = [viewer.list_widget.item(i).text() for i in range(viewer.list_widget.count())]
    assert not any(row.startswith("DATA") for row in rows)
    assert any("Greeting" in row for row in rows)
    greeting_row = next(i for i in range(viewer.list_widget.count())
                        if "Greeting" in viewer.list_widget.item(i).text())
    viewer.list_widget.setCurrentRow(greeting_row)
    h.settle()
    assert "05 48 65 6C 6C 6F" in viewer.text_edit.toPlainText()
    viewer.checkbox.setChecked(True)
    h.settle()
    assert "Hello" in viewer.text_edit.toPlainText()
    viewer.close()
    h.settle()
    assert h.d.viewer_windows == []


def test_content_viewer_resource_and_data_file(harness):
    v = _volume()
    mixed = machfs.File()
    mixed.type, mixed.creator = b"APPL", b"TEST"
    mixed.data = b"A data fork."
    mixed.rsrc = bytearray(FORK)
    v["Mixed"] = mixed

    h = harness(disks=[v])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Mixed"))
    h.settle()
    assert _file_menu_display_contents_enabled(h) is True
    win.display_contents()
    h.settle()
    viewer = h.d.viewer_windows[-1]
    rows = [viewer.list_widget.item(i).text() for i in range(viewer.list_widget.count())]
    assert rows[0].startswith("DATA")
    assert f"({len(b'A data fork.'):,} bytes)" in rows[0]
    assert any("Greeting" in row for row in rows)
    assert viewer.list_widget.currentRow() == 0     # DATA selected first
    assert "41 20 64 61 74 61" in viewer.text_edit.toPlainText()     # "A data"
    greeting_row = next(i for i in range(viewer.list_widget.count())
                        if "Greeting" in viewer.list_widget.item(i).text())
    viewer.list_widget.setCurrentRow(greeting_row)
    h.settle()
    assert "05 48 65 6C 6C 6F" in viewer.text_edit.toPlainText()
    viewer.close()
    h.settle()


def test_content_viewer_corrupt_resource_fork(harness):
    v = _volume()
    bad = machfs.File()
    bad.type, bad.creator = b"APPL", b"TEST"
    bad.data = b""
    bad.rsrc = b"not a resource fork"
    v["BadRes"] = bad

    h = harness(disks=[v])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "BadRes"))
    h.settle()
    win.display_contents()
    h.settle()
    viewer = h.d.viewer_windows[-1]
    assert viewer.list_widget.count() == 0
    assert "(empty)" in viewer.text_edit.toPlainText()
    viewer.close()
    h.settle()


def test_content_viewer_empty_and_unreadable_fork(harness, monkeypatch):
    v = _volume(games=False)
    empty_file = machfs.File()
    empty_file.data = b""
    v["Empty"] = empty_file

    bad_file = machfs.File()
    bad_file.data = b"some data"
    v["Bad"] = bad_file

    h = harness(disks=[v])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()

    win.tree.setCurrentItem(_item(win, "Empty"))
    h.settle()
    win.display_contents()
    h.settle()
    assert "(empty)" in h.d.viewer_windows[-1].text_edit.toPlainText()
    h.d.viewer_windows[-1].close()
    h.settle()

    bad_item = win.entries["Bad"]
    monkeypatch.setattr(bad_item.__class__, "data", property(lambda self: (_ for _ in ()).throw(RuntimeError("Corrupt"))))

    win.tree.setCurrentItem(_item(win, "Bad"))
    h.settle()
    win.display_contents()
    h.settle()
    assert "(unreadable data fork)" in h.d.viewer_windows[-1].text_edit.toPlainText()
    h.d.viewer_windows[-1].close()
    h.settle()





def test_item_icons(harness):
    v = machfs.Volume()
    # 1. Item with custom icon (marked 0x0400)
    marked = machfs.File()
    marked.data, marked.flags = b"Text.", 0x0400
    marked.rsrc = bytearray(build_fork([Resource(b"ICN#", 128, bytes([0xFF]) * 256)]))
    v["Marked"] = marked
    # 2. Item with unreadable resources
    bad = machfs.File()
    bad.data, bad.flags = b"Bad.", 0x0400
    bad.rsrc = b"corrupt"
    v["Bad"] = bad
    # 3. Item with generic icon (folder)
    v["Folder"] = machfs.Folder()
    h = harness(disks=[v])
    win = h.d.open_filer(v)
    h.settle()
    
    # Assertions
    assert not _item(win, "Marked").icon(0).isNull()
    assert not _item(win, "Bad").icon(0).isNull() # Should fall back to generic
    assert not _item(win, "Folder").icon(0).isNull()


def test_open_target_with_filer_flag(tmp_path):
    p = tmp_path / "App.bin"
    p.write_bytes(macbinary("App", b"data", FORK))
    # Default launch action: runs the app, target in targets
    args = parse_args([str(p)])
    targets, disks, filers, error = open_targets(args)
    assert error is None
    assert len(targets) == 1
    assert targets[0][0].name == "App"
    assert filers == []

    # With --filer flag on a plain file: opens its folder in a Filer window
    q = tmp_path / "Letter.txt"
    q.write_bytes(b"Hello.")
    args_filer = parse_args([str(q), "--filer"])
    targets_f, disks_f, filers_f, error_f = open_targets(args_filer)
    assert error_f is None
    assert targets_f == []
    assert len(filers_f) == 1
    assert isinstance(filers_f[0], HostFolder)
    assert filers_f[0].path == tmp_path


def test_filer_opens_container_contents(tmp_path):
    # MacBinary, BinHex and AppleSingle each decode to the file inside.
    mb = tmp_path / "App.bin"
    mb.write_bytes(macbinary("Inner", b"data", FORK))
    hqx = tmp_path / "Doc.hqx"
    hqx.write_bytes(b"From: a list\r\r" + binhex("HexDoc", b"hi", b"", b"TEXT", b"ttxt"))
    single = tmp_path / "Note.as"
    single.write_bytes(apple_single({1: b"data!", 2: FORK, 3: b"Real Name"}))
    args = parse_args([str(mb), str(hqx), str(single), "--filer"])
    targets, disks, filers, error = open_targets(args)
    assert error is None
    assert targets == []
    assert [type(v).__name__ for v in filers] == ["ContainerFolder"] * 3
    assert [v.name for v in filers] == ["App.bin", "Doc.hqx", "Note.as"]
    assert [[f.name for f in v.files()] for v in filers] == \
        [["Inner"], ["HexDoc"], ["Real Name"]]


def test_filer_reports_a_damaged_container(tmp_path):
    hqx = bytearray(binhex("Hex App", b"data", FORK))
    at = hqx.index(b":") + 40
    hqx[at] = ord("!") if hqx[at] != ord("!") else ord("#")
    p = tmp_path / "app.hqx"
    p.write_bytes(hqx)
    args = parse_args([str(p), "--filer"])
    targets, disks, filers, error = open_targets(args)
    assert targets is None and filers is None
    assert error and "BinHex" in error


def test_the_window_lists_a_containers_contents(harness, tmp_path):
    p = tmp_path / "App.bin"
    p.write_bytes(macbinary("Inner", b"data", FORK))
    args = parse_args([str(p), "--filer"])
    _, _, filers, error = open_targets(args)
    assert error is None
    h = harness(disks=[])
    win = h.d.open_filer(filers[0])
    h.settle()
    assert win.isVisible()
    assert win.windowTitle() == "App.bin"
    rows = _rows(win)
    assert [name for name, _ in rows] == ["Inner"]
    assert rows[0][1] == "application"
    assert win in h.d.filer_windows


def test_a_container_in_a_window_drills_into_its_contents(harness, tmp_path):
    core = macbinary("Core", b"payload", FORK)
    outer = tmp_path / "Outer.bin"
    outer.write_bytes(macbinary("Packet", core, FORK))
    args = parse_args([str(outer), "--filer"])
    _, _, filers, error = open_targets(args)
    assert error is None
    h = harness(disks=[])
    win = h.d.open_filer(filers[0])
    h.settle()
    assert _rows(win) == [("Packet", "application")]
    win.tree.setCurrentItem(_item(win, "Packet"))
    h.settle()
    assert win.selected_actions() == {"open", "info", "display_contents"}
    assert _file_menu_open_enabled(h) is True     # File > Open can drill into it
    win.open_selected()
    h.settle()
    assert len(h.d.filer_windows) == 2
    inner = h.d.filer_windows[1]
    assert inner.windowTitle() == "Packet"
    assert _rows(inner) == [("Core", "application")]
    assert not h.d._alerts


def test_a_damaged_nested_container_says_so_without_crashing(harness, tmp_path):
    cut = bytes(bytearray(macbinary("Core", b"payload", FORK))[:150])   # header, no forks
    outer = tmp_path / "Outer.bin"
    outer.write_bytes(macbinary("Packet", cut, FORK))
    args = parse_args([str(outer), "--filer"])
    _, _, filers, error = open_targets(args)
    assert error is None
    h = harness(disks=[])
    win = h.d.open_filer(filers[0])
    h.settle()
    win.tree.setCurrentItem(_item(win, "Packet"))
    h.settle()
    win.open_selected()
    h.settle()
    assert len(h.d.filer_windows) == 1          # no drill window
    assert h.d._alerts and "cut short" in h.d._alerts[0].text()


def test_an_unsupported_nested_item_does_not_drill(harness):
    zipped = MacFile("Packet", b"PK\x03\x04" + b"payload" * 4, FORK, b"TEXT", b"ttxt")
    h = harness(disks=[])
    win = h.d.open_filer(ContainerFolder(zipped, "Outer.bin"))
    h.settle()
    assert _rows(win) == [("Packet", "document")]
    win.tree.setCurrentItem(_item(win, "Packet"))
    h.settle()
    win.open_selected()
    h.settle()
    assert len(h.d.filer_windows) == 1          # it did not drill into the zip
    assert h.d._alerts                          # and it said why it could not open


def test_a_contained_application_launches(harness, tmp_path, monkeypatch):
    p = tmp_path / "App.bin"
    p.write_bytes(macbinary("Inner", b"payload", FORK))
    args = parse_args([str(p), "--filer"])
    _, _, filers, error = open_targets(args)
    assert error is None
    h = harness(disks=[])
    win = h.d.open_filer(filers[0])
    h.settle()
    launched = []
    monkeypatch.setattr(h.d, "launch",
                        lambda name, main, **kw: launched.append((name, kw)))
    win.tree.setCurrentItem(_item(win, "Inner"))
    h.settle()
    win.open_selected()
    h.settle()
    assert len(launched) == 1
    assert launched[0][0] == "Inner"
    assert launched[0][1]["app"].name == "Inner"


def test_a_multi_nested_application_launches(harness, tmp_path, monkeypatch):
    inner = macbinary("Core", b"payload", FORK)
    outer_bytes = macbinary("Packet", inner, FORK)
    outer = tmp_path / "Outer.bin"
    outer.write_bytes(outer_bytes)
    args = parse_args([str(outer), "--filer"])
    _, _, filers, error = open_targets(args)
    assert error is None
    h = harness(disks=[])
    win1 = h.d.open_filer(filers[0])
    h.settle()
    # Drill into Packet container
    win1.tree.setCurrentItem(_item(win1, "Packet"))
    h.settle()
    win1.open_selected()
    h.settle()
    assert len(h.d.filer_windows) == 2
    win2 = h.d.filer_windows[1]
    assert win2.windowTitle() == "Packet"
    assert _rows(win2) == [("Core", "application")]

    launched = []
    monkeypatch.setattr(h.d, "launch",
                        lambda name, main, **kw: launched.append((name, kw)))
    win2.tree.setCurrentItem(_item(win2, "Core"))
    h.settle()
    win2.open_selected()
    h.settle()
    assert len(launched) == 1
    assert launched[0][0] == "Core"
    assert launched[0][1]["app"].name == "Core"


# -- Special > Shutdown -----------------------------------------------------
def test_special_shutdown_closes_the_windows_before_the_qt_app(harness, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    special = h.d.filer_menus.menus[SPECIAL_MENU_ID]
    assert special.items[6].enabled              # Special > Shutdown is choosable
    at_quit = []
    monkeypatch.setattr(h.app, "quit", lambda: at_quit.append(win.isVisible()))
    h.choose(h.d.global_bar, "Special", 7)
    h.wait_until(lambda: h.d.shutting_down, what="the display to shut down")
    assert at_quit == [False]                    # the windows are shut, then Qt goes


def _file_menu_export_enabled(h) -> bool:
    for menu, _cell in h.d.global_bar.cells():
        if menu.title == "File":
            return menu.items[5].enabled
    raise AssertionError("the menu bar is showing no File menu")


def _save_dialog(monkeypatch, out):
    class _SaveDialog:
        @staticmethod
        def getSaveFileName(*_args, **_kwargs):
            return (str(out), "") if out is not None else ("", "")
    monkeypatch.setattr("macrt.ui.filer.QFileDialog", _SaveDialog)


def test_file_export_menu_item_enabled_state(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    assert _file_menu_export_enabled(h) is True


def test_file_export_catalog_from_volume(harness, tmp_path, monkeypatch):
    from disktracker import parse_dtc
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    out = tmp_path / "Browse.dtc"
    _save_dialog(monkeypatch, out)
    win.export_catalog()
    h.settle()
    items = parse_dtc(out.read_bytes())
    disk = items[0]
    assert disk.kind == "disk" and disk.name == "Browse"
    assert disk.items == len(items) - 1
    by_name = {i.name: i for i in items[1:]}
    assert by_name["Widget"].kind == "file" and by_name["Widget"].type == b"APPL"
    assert by_name["Letter"].kind == "file"
    games = by_name["Games"]
    assert games.kind == "folder" and games.items == 1
    assert games.descendants == 1 and games.size == by_name["Game"].size
    assert by_name["Game"].depth == games.depth + 1


def test_file_export_catalog_from_host_folder(harness, tmp_path, monkeypatch):
    from disktracker import parse_dtc
    folder = tmp_path / "host"
    folder.mkdir()
    (folder / "doc.txt").write_bytes(b"hello")
    sub = folder / "sub"
    sub.mkdir()
    (sub / "inner.txt").write_bytes(b"world!")

    h = harness(disks=[])
    win = h.d.open_filer(HostFolder(folder))
    h.settle()
    out = tmp_path / "host.dtc"
    _save_dialog(monkeypatch, out)
    win.export_catalog()
    h.settle()
    items = parse_dtc(out.read_bytes())
    assert items[0].kind == "disk" and items[0].name == "host"
    by_name = {i.name: i for i in items[1:]}
    assert by_name["doc.txt"].size == 5 and by_name["doc.txt"].created != 0
    sub_item = by_name["sub"]
    assert sub_item.kind == "folder" and sub_item.descendants == 1
    assert sub_item.size == 6 == by_name["inner.txt"].size
    assert by_name["inner.txt"].depth == sub_item.depth + 1


def test_file_export_catalog_disabled_for_disk_tracker_views(harness, tmp_path):
    from disktracker import build_dtc
    from disktracker.filer_adapter import DiskTrackerVolume
    alpha = machfs.Volume()
    alpha.name = "Alpha CD"
    f = machfs.File()
    f.data = b"alpha"
    alpha["a.txt"] = f
    img = tmp_path / "Alpha CD.hfs"
    img.write_bytes(alpha.write(1024 * 1024))
    cat = tmp_path / "catalog"
    cat.write_bytes(build_dtc([str(img)]))

    h = harness(disks=[])
    win = h.d.open_filer(DiskTrackerVolume(cat))
    h.settle()
    assert _file_menu_export_enabled(h) is False


def test_file_export_catalog_cancelled_dialog_writes_nothing(harness, tmp_path, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    h.settle()
    _save_dialog(monkeypatch, None)             # the dialog is cancelled
    win.export_catalog()
    h.settle()
    assert list(tmp_path.iterdir()) == []


def test_file_export_catalog_from_container(harness, tmp_path, monkeypatch):
    from disktracker import parse_dtc
    p = tmp_path / "App.bin"
    p.write_bytes(macbinary("Inner", b"payload", FORK))
    args = parse_args([str(p), "--filer"])
    _, _, filers, error = open_targets(args)
    assert error is None
    h = harness(disks=[])
    win = h.d.open_filer(filers[0])
    h.settle()
    assert _file_menu_export_enabled(h) is True
    out = tmp_path / "app.dtc"
    _save_dialog(monkeypatch, out)
    win.export_catalog()
    h.settle()
    items = parse_dtc(out.read_bytes())
    assert items[0].kind == "disk" and items[0].name == "App.bin"
    assert len(items) == 2
    assert items[1].name == "Inner" and items[1].type == b"APPL"


def test_shutdown_asks_each_running_application_to_quit(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    alpha = h.launch(Recorder("Alpha", at=(30, 60)))
    _front_the_filer(h, win)
    h.choose(h.d.global_bar, "Special", 7)
    h.wait_until(lambda: h.d.shutting_down, what="the display to shut down")
    assert alpha.events.killed                   # its quit was asked for
    h.wait_until(lambda: not alpha.thread.is_alive(), what="Alpha's thread to end")


def test_a_quit_that_raises_does_not_stop_the_shutdown(harness, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    alpha = h.launch(Recorder("Alpha", at=(30, 60)))
    beta = h.launch(Recorder("Beta", at=(30, 120)))
    _front_the_filer(h, win)

    def boom():
        raise RuntimeError("Alpha refuses to quit")

    alpha.quit = boom                            # the first application's quit fails
    order = []
    monkeypatch.setattr(h.app, "quit",
                        lambda: order.append(("app.quit", beta.events.killed)))
    h.choose(h.d.global_bar, "Special", 7)
    h.wait_until(lambda: h.d.shutting_down, what="the display to shut down")
    assert order == [("app.quit", True)]         # the rest still quit, root last
    alpha.events.kill()       # only its shutdown call raised: let it stop for teardown
    h.wait_until(lambda: not alpha.thread.is_alive() and not beta.thread.is_alive(),
                  what="both threads to end")


# -- Special > Restart ------------------------------------------------------
def test_special_restart_reruns_the_original_command_after_the_shutdown(
        harness, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_filer(h.d.config.disks[0])
    alpha = h.launch(Recorder("Alpha", at=(30, 60)))
    _front_the_filer(h, win)
    special = h.d.filer_menus.menus[SPECIAL_MENU_ID]
    assert special.items[5].enabled              # Special > Restart is choosable
    command = ["python3", "-m", "macrt", "Browse.dsk", "--filer"]
    monkeypatch.setattr(sys, "orig_argv", command)
    runs = []
    monkeypatch.setattr(os, "execvp", lambda prog, argv: runs.append((prog, argv)))
    h.choose(h.d.global_bar, "Special", 6)
    h.wait_until(lambda: h.d.shutting_down, what="the display to shut down")
    assert h.d.restarting
    assert runs == []                            # nothing relaunches yet
    finish(h.d, 0)
    assert runs == [("python3", command)]        # the original command, same parameters
    assert not alpha.thread.is_alive()           # after the applications have gone


def test_shutdown_leaves_the_command_alone(harness, monkeypatch):
    h = harness(disks=[_volume()])
    h.d.open_filer(h.d.config.disks[0])
    runs = []
    monkeypatch.setattr(os, "execvp", lambda prog, argv: runs.append(argv))
    h.choose(h.d.global_bar, "Special", 7)
    h.wait_until(lambda: h.d.shutting_down, what="the display to shut down")
    finish(h.d, 0)
    assert not h.d.restarting
    assert runs == []                            # only Restart runs anything again

"""The Finder window a disk image opens in when no --app names what to run."""

import machfs
import pytest
from PyQt6.QtTest import QTest

from conftest import LB, NO_MODS
from macrt.demo import open_targets, parse_args
from macrt.macfile import open_disks
from macrt.resfork import build_fork, Resource, resPurgeable
from test_files import FORK, macbinary


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


def _dblclick(win, name, settle):
    """A real double-click: click, then click again on the same spot."""
    c = win.tree.visualItemRect(_item(win, name)).center()
    vp = win.tree.viewport()
    QTest.mousePress(vp, LB, NO_MODS, c)
    QTest.mouseRelease(vp, LB, NO_MODS, c)
    settle(30)
    QTest.mouseDClick(vp, LB, NO_MODS, c)
    settle(150)


def test_the_window_lists_the_folder(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_finder(h.d.config.disks[0])
    h.settle()
    assert win.isVisible()
    assert _rows(win) == [("Games", "folder"), ("Letter", "document"),
                          ("Widget", "application")]
    assert win in h.d.finder_windows


def test_the_same_folder_is_one_window(harness):
    h = harness(disks=[_volume()])
    volume = h.d.config.disks[0]
    win = h.d.open_finder(volume)
    assert h.d.open_finder(volume) is win
    assert h.d.finder_windows == [win]


def test_double_click_launches_the_application(harness, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_finder(h.d.config.disks[0])
    h.settle()
    launched = []
    monkeypatch.setattr(h.d, "launch",
                        lambda name, main, **kw: launched.append((name, main, kw)))
    _dblclick(win, "Widget", h.settle)
    h.settle()
    assert [(n, kw["app"].name) for n, _, kw in launched] == [("Widget", "Widget")]
    assert win in h.d.finder_windows       # the window carries on


def test_a_document_opens_with_its_creator(harness, monkeypatch):
    h = harness(disks=[_volume()])
    win = h.d.open_finder(h.d.config.disks[0])
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
    win = h.d.open_finder(h.d.config.disks[0])
    h.settle()
    _dblclick(win, "Games", h.settle)
    h.settle()
    assert len(h.d.finder_windows) == 2
    child = h.d.finder_windows[1]
    assert child.path == ("Games",)
    assert [name for name, _ in _rows(child)] == ["Game"]
    assert child.frame().title == "Games"


def test_the_close_box_closes_the_window(harness):
    h = harness(disks=[_volume()])
    win = h.d.open_finder(h.d.config.disks[0])
    h.settle()
    o = win.mac_origin()
    box = win.box_rect(4)                   # wInGoAway
    assert box is not None
    h.click(o.h + box.x() + 5, o.v + box.y() + 5)
    h.wait_until(lambda: win not in h.d.finder_windows, what="the finder to close")
    assert h.d.shutting_down                # it was all that was up: macrt quits


def test_a_second_window_survives_the_first_closing(harness):
    h = harness(disks=[_volume()])
    volume = h.d.config.disks[0]
    win = h.d.open_finder(volume)
    child = h.d.open_finder(volume, ("Games",))
    h.settle()
    child.close()                           # closing its box goes through closeEvent
    h.wait_until(lambda: child not in h.d.finder_windows, what="the folder window to close")
    assert win in h.d.finder_windows
    assert not h.d.shutting_down

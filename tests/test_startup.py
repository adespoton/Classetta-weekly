"""The disk to start up from (the Start Manager's GetDefaultStartup and
SetDefaultStartup), and the hard disks' drivers' icons, which Startup
Disk lists the disks with."""

import struct

import pytest

from macrt.m68k import glue_files
from macrt.toolbox import sysres
from macrt.toolbox.files import FileError

from guest import Guest


@pytest.fixture
def g(qapp):
    return Guest()


def control(g, refnum: int, code: int) -> tuple[int, int]:
    """A Control call to the driver: its result, and csParam after."""
    pb = g.ptr(bytes(50))
    g.mem.write(pb + 24, struct.pack(">hh", refnum, code))
    try:
        glue_files._control(g, pb, False)
    except FileError as e:
        return e.code, 0
    return 0, g.mem.r32(pb + glue_files.csParam)


def test_the_default_startup_disk_is_the_boot_volume_s_until_another_is_set(g):
    boot = g.system.files.boot
    assert not boot.floppy and boot.driver == -33
    rec = g.ptr(b"\xff" * 4)
    g("GetDefaultStartup", rec)
    assert g.mem.read(rec, 4) == struct.pack(">hh", 0, -33)
    g.mem.write(rec, struct.pack(">hh", 0, -35))
    g("SetDefaultStartup", rec)
    g.mem.write(rec, bytes(4))
    g("GetDefaultStartup", rec)
    assert g.mem.read(rec, 4) == struct.pack(">hh", 0, -35)


def test_a_hard_disk_s_driver_gives_its_icon(g):
    refnum = g.system.files.boot.driver
    err, icon = control(g, refnum, glue_files.kDriveIcon)
    assert err == 0 and g.mem.read(icon, 256) == sysres.HARD_DISK_ICON
    assert control(g, refnum, glue_files.kMediaIcon) == (0, icon)     # the same one, kept
    mask = sysres.HARD_DISK_ICON[128:]
    assert all(b & ~m == 0 for b, m in zip(sysres.HARD_DISK_ICON, mask))
    assert control(g, refnum, 1)[0] == glue_files.controlErr
    assert control(g, -40, glue_files.kDriveIcon)[0] == glue_files.unitEmptyErr

"""The ADB Manager: the keyboard and the mouse in the device table, on a
Macintosh II (macrt.m68k.glue_adb)."""

import struct

import pytest

from macrt.m68k.glue_adb import KEYBOARD, MOUSE, NO_DEVICE
from macrt.m68k.glue_os import ADB_TRAPS, UNIMPLEMENTED, trap_address
from macrt.toolbox.memmgr import noErr

from guest import Guest


@pytest.fixture
def g(qapp):
    return Guest(model="ii")


def data_block(g, p) -> tuple:
    """An ADBDataBlock: devType, origADBAddr, dbServiceRtPtr, dbDataAreaAddr."""
    return struct.unpack(">BBII", g.mem.read(p, 10))


def test_the_table_has_the_keyboard_then_the_mouse(g):
    service = g.machine.adb_service
    assert g("CountADBs") == 2
    block = g.ptr(bytes(10))
    assert g("GetIndADB", block, 1) == KEYBOARD
    assert data_block(g, block) == (1, KEYBOARD, service, 0)
    assert g("GetIndADB", block, 2) == MOUSE
    assert data_block(g, block) == (1, MOUSE, service, 0)
    assert g.mem.r16(service) == 0x4E75                     # an RTS


def test_an_index_past_either_end_has_no_device(g):
    block = g.ptr(b"\xAA" * 10)
    for index in (0, 3, -1):
        assert g("GetIndADB", block, index) == NO_DEVICE
    assert g.mem.read(block, 10) == b"\xAA" * 10


def test_set_adb_info_replaces_a_device_s_service_routine_and_data_area(g):
    info = g.ptr(struct.pack(">II", 0x12340, 0x56780))
    assert g("SetADBInfo", info, MOUSE) == noErr
    block = g.ptr(bytes(10))
    assert g("GetADBInfo", block, MOUSE) == noErr
    assert data_block(g, block) == (1, MOUSE, 0x12340, 0x56780)
    assert g("GetADBInfo", block, KEYBOARD) == noErr
    assert data_block(g, block)[2:] == (g.machine.adb_service, 0)


def test_an_address_no_device_is_at_answers_minus_one(g):
    block = g.ptr(bytes(10))
    assert g("GetADBInfo", block, 7) == NO_DEVICE
    assert g("SetADBInfo", block, 7) == NO_DEVICE
    assert g("CountADBs") == 2


def test_a_plus_has_no_devices(qapp):
    assert Guest(model="plus")("CountADBs") == 0


def test_only_a_mac_ii_has_the_adb_manager(harness):
    """Falcon MC walks the table with GetIndADB; on a Plus,
    GetTrapAddress says the calls aren't there."""
    from test_m68k_apps import launch_hello
    for model, there in (("ii", True), ("plus", False)):
        proc, _ = launch_hello(harness(model=model))
        t = proc.runner
        with proc.system.lock:
            for word in ADB_TRAPS:
                assert (trap_address(t, word) != trap_address(t, UNIMPLEMENTED)) == there

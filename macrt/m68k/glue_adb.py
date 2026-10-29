"""
The ADB Manager (Inside Macintosh V, The Apple Desktop Bus): the device
table, on a Mac with the bus.  It has the keyboard and the mouse, at the
addresses IM V gives them, 2 and 3; the keyboard's device handler ID is
the Macintosh II keyboard's, 1, and the mouse's macrt's own, 1.  macrt's
keyboard and mouse come from the host rather than over a bus, so their
service routines, which a program can read and replace with SetADBInfo,
are an RTS that nothing calls.

Programs walk the table to find a device of their own: Falcon MC looks
from CountADBs down to 1 for one whose handler ID is $23, and goes on to
the game when there's none.  GetADBInfo and SetADBInfo answer -1 for an
address no device is at.  On a Plus the table is empty, and
GetTrapAddress says the calls aren't there (glue_os).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..toolbox.memmgr import noErr
from .dispatch import trap

KEYBOARD, MOUSE = 2, 3      # their ADB addresses
NO_DEVICE = -1              # GetIndADB's index, or an address, no entry has


@dataclass
class Device:
    handler_id: int
    orig_address: int
    address: int
    service: int            # the service routine's address
    data: int               # its data area's


def _table(t) -> list[Device]:
    system = t.system
    table = getattr(system, "adb_table", None)
    if table is None:
        table = system.adb_table = [] if not system.model.adb else [
            Device(1, KEYBOARD, KEYBOARD, t.machine.adb_service, 0),
            Device(1, MOUSE, MOUSE, t.machine.adb_service, 0)]
    return table


def _at(t, address: int) -> Device | None:
    return next((d for d in _table(t) if d.address == address & 0xFF), None)


def _info(t, info: int, device: Device):
    """An ADBDataBlock: devType, origADBAddr, dbServiceRtPtr, dbDataAreaAddr."""
    m = t.mem
    m.w8(info, device.handler_id)
    m.w8(info + 1, device.orig_address)
    m.w32(info + 2, device.service)
    m.w32(info + 6, device.data)


@trap
def CountADBs(t):
    return len(_table(t))


@trap
def GetIndADB(t, info, index):
    table = _table(t)
    if not 1 <= index <= len(table):
        return NO_DEVICE
    device = table[index - 1]
    _info(t, info, device)
    return device.address


@trap
def GetADBInfo(t, info, address):
    device = _at(t, address)
    if device is None:
        return NO_DEVICE
    _info(t, info, device)
    return noErr


@trap
def SetADBInfo(t, info, address):
    """An ADBSetInfoBlock: siServiceRtPtr, siDataAreaAddr."""
    device = _at(t, address)
    if device is None:
        return NO_DEVICE
    device.service = t.mem.r32(info)
    device.data = t.mem.r32(info + 4)
    return noErr

"""The SCSI Manager: a bus with nothing on it (macrt.m68k.glue_scsi)."""

import struct

from macrt.m68k import dispatch

from guest import Processor


def test_the_bus_is_won_but_no_device_answers(qapp):
    """Stack-based, the selector pushed last (IM V, The SCSI Manager):
    SCSIGet, SCSISelect(3), SCSIStat and SCSIComplete, each leaving the
    stack as it found it."""
    p = Processor()
    stat, message = p.ptr(b"\x12\x34"), p.ptr(b"\x56\x78")
    complete = (bytes.fromhex("554F" "4879") + struct.pack(">I", stat)
                + bytes.fromhex("4879") + struct.pack(">I", message)
                + bytes.fromhex("2F3C0000003C" "3F3C0004" "A815" "381F"))
    p.run(bytes.fromhex("554F" "3F3C0001" "A815" "3E1F"                  # SCSIGet
                        "554F" "3F3C0003" "3F3C0002" "A815" "3C1F"       # SCSISelect(3)
                        "554F" "3F3C000A" "A815" "3A1F")                 # SCSIStat
          + complete)                                                    # SCSIComplete(.., 60)
    assert [p.cpu.d(n) & 0xFFFF for n in (7, 6, 5, 4)] == [0, 2, 0, 2]   # scCommErr
    assert p.cpu.sp == p.stack_top and not p.missing
    assert p.mem.read(stat, 2) == b"\x12\x34" and p.mem.read(message, 2) == b"\x56\x78"


def test_trap_available_finds_the_scsi_manager():
    assert dispatch.implemented(dispatch.trap_key(0xA815))
    assert dispatch.trap_name(0xA815) == "SCSIDispatch"

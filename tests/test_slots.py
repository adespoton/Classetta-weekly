"""The Slot Manager, and the screen's card's declaration ROM it reads
(glue_slots)."""

import struct

import pytest

from macrt.m68k import glue_video
from macrt.m68k.glue_slots import TEST_PATTERN, _crc
from macrt.toolbox.gdevice import VIDEO_DRIVER, VIDEO_SLOT
from macrt.toolbox.memmgr import noErr

from guest import Guest

# The selectors
SReadByte, SReadWord, SReadLong, SGetCString, SGetBlock, SFindStruct = 0, 1, 2, 3, 5, 6
SReadStruct, SVersion, SetSRsrcState, InsertSRTRec, SGetSRsrc, SGetTypeSRsrc = 7, 8, 9, 10, 11, 12
SReadInfo, SReadPRAMRec, SPutPRAMRec, SReadFHeader = 0x10, 0x11, 0x12, 0x13
SNextSRsrc, SNextTypeSRsrc, SRsrcInfo, SCkCardStat = 0x14, 0x15, 0x16, 0x18
SReadDrvrName, SFindDevBase, SDeleteSRTRec = 0x19, 0x1B, 0x31
smEmptySlot, smsPointerNil, smSelOOBErr = -300, -335, -338
smNoMoresRsrcs, smBadsPtrErr, smRecNotFnd = -344, -346, -351
fAll, fOneSlot, fNext = 1, 2, 4
# sResource entries
sRsrcType, sRsrcName, sRsrcHWDevId = 1, 2, 8
mVidParams, mPageCnt, mDevType = 1, 3, 4
BOARD, VIDEO = 1, 0x80
CAT_DISPLAY, TYP_VIDEO, DR_SW_APPLE = 3, 1, 1


@pytest.fixture
def g(qapp):
    return Guest(model="ii")


class SpBlock:
    """A SpBlock in the guest's memory, its fields by name."""

    FIELDS = {"result": (0, 4), "sPointer": (4, 4), "size": (8, 4), "paramData": (24, 4),
              "refNum": (38, -2), "category": (40, 2), "cType": (42, 2), "drvrSW": (44, 2),
              "drvrHW": (46, 2), "tbMask": (48, 1), "slot": (49, 1), "id": (50, 1),
              "extDev": (51, 1), "hwDev": (52, 1)}

    def __init__(self, g, **fields):
        self.g = g
        self.p = g.ptr(bytes(56))
        self.set(**fields)

    def set(self, **fields):
        m = self.g.mem
        for name, value in fields.items():
            at, size = self.FIELDS[name]
            {1: m.w8, 2: m.w16, -2: m.w16, 4: m.w32}[size](self.p + at, value & 0xFFFFFFFF)
        return self

    def __getattr__(self, name):
        at, size = self.FIELDS[name]
        m = self.g.mem
        return {1: m.r8, 2: m.r16, -2: m.r16s, 4: m.r32}[size](self.p + at)

    def __call__(self, selector, **fields):
        self.set(**fields)
        return self.g("SlotManager", self.p, selector)


def video(g) -> SpBlock:
    """The screen's sResource, found as the CyberFlix demos find it: by
    its type, all but its DrHW."""
    sp = SpBlock(g, category=CAT_DISPLAY, cType=TYP_VIDEO, drvrSW=DR_SW_APPLE, tbMask=1)
    assert sp(SNextTypeSRsrc) == noErr
    return sp


def test_the_screens_video_sresource_is_found_by_its_type(g):
    sp = video(g)
    assert (sp.slot, sp.id, sp.extDev) == (VIDEO_SLOT, VIDEO, 0)
    assert sp.refNum == VIDEO_DRIVER
    assert (sp.category, sp.cType, sp.drvrSW, sp.drvrHW) == (CAT_DISPLAY, TYP_VIDEO,
                                                             DR_SW_APPLE, 0)
    assert sp.hwDev == 1
    assert sp(SNextTypeSRsrc) == smNoMoresRsrcs     # and there's no other
    # Not with another DrHW, unless spTBMask leaves it out.
    assert SpBlock(g, category=CAT_DISPLAY, cType=TYP_VIDEO, drvrSW=DR_SW_APPLE,
                   drvrHW=5)(SNextTypeSRsrc) == smNoMoresRsrcs


def test_the_card_has_its_board_sresource_and_the_screens(g):
    sp = SpBlock(g)
    found = []
    while sp(SNextSRsrc) == noErr:
        found.append((sp.slot, sp.id, sp.category))
    assert found == [(VIDEO_SLOT, BOARD, 1), (VIDEO_SLOT, VIDEO, CAT_DISPLAY)]
    sp.set(slot=VIDEO_SLOT, id=BOARD)
    assert sp(SRsrcInfo) == noErr and sp.category == 1 and sp.refNum == 0
    assert sp(SRsrcInfo, id=2) == smNoMoresRsrcs
    assert sp(SGetSRsrc, id=BOARD, paramData=0) == noErr and sp.id == BOARD
    assert sp(SGetSRsrc, paramData=fNext) == noErr and sp.id == VIDEO
    assert sp.paramData == 0                        # it's enabled


def test_an_sresources_entries_are_read(g):
    sp = video(g)
    sptr = sp.sPointer
    assert sp(SReadWord, id=sRsrcHWDevId) == noErr and sp.result == 1
    assert sp(SReadByte, sPointer=sptr) == noErr and sp.result == 1
    assert sp(SReadLong, sPointer=sptr, id=sRsrcType) == noErr
    assert sp.result == CAT_DISPLAY << 16 | TYP_VIDEO
    assert sp(SGetCString, sPointer=sptr, id=sRsrcName) == noErr
    assert g.mem.read(sp.result, 24) == b"Display_Video_Apple_TFB\0"
    assert sp(SReadByte, sPointer=sptr, id=3) == smNoMoresRsrcs     # no such entry
    assert sp(SReadByte, sPointer=0) == smsPointerNil
    assert sp(SReadByte, sPointer=0x1000) == smBadsPtrErr           # not on the card
    buf = g.ptr(bytes(8))
    assert sp(SFindStruct, sPointer=sptr, id=sRsrcType) == noErr
    assert sp(SReadStruct, size=8, result=buf) == noErr
    assert struct.unpack(">4H", g.mem.read(buf, 8)) == (CAT_DISPLAY, TYP_VIDEO, DR_SW_APPLE, 0)


def test_each_mode_has_its_video_parameters(g):
    system = g.system
    sp = video(g)
    sptr = sp.sPointer
    modes = glue_video.modes(system)
    assert modes and modes[0] == 0x80
    for mode in modes:
        depth = glue_video.DEPTHS[mode]
        assert sp(SFindStruct, sPointer=sptr, id=mode) == noErr
        mode_list = sp.sPointer
        assert sp(SReadWord, id=mPageCnt) == noErr and sp.result == 1
        assert sp(SReadWord, sPointer=mode_list, id=mDevType) == noErr
        assert sp.result == (2 if depth > 8 else 0)
        assert sp(SGetBlock, sPointer=mode_list, id=mVidParams) == noErr
        vp = g.mem.read(sp.result, 42)
        (base, row_bytes, top, left, bottom, right, version, _, _, hres, vres,
         pixel_type, pixel_size, cmp_count, cmp_size, _) = struct.unpack(">LH4hhhLLLhhhhL", vp)
        r = system.screen_bits.bounds
        assert (base, row_bytes) == (0, system.row_bytes_for(depth))
        assert (top, left, bottom, right) == (r.top, r.left, r.bottom, r.right)
        assert (version, hres, vres) == (1, 72 << 16, 72 << 16)
        assert (pixel_type, pixel_size) == ((16 if depth > 8 else 0), depth)
        assert cmp_count * cmp_size == (depth if depth <= 8 else 24 if depth == 32 else 15)
    assert sp(SFindStruct, sPointer=sptr, id=modes[-1] + 1) == smNoMoresRsrcs


def test_the_drivers_name_is_the_screens(g):
    name = g.ptr(bytes(256))
    sp = SpBlock(g, slot=VIDEO_SLOT, id=VIDEO, result=name)
    assert sp(SReadDrvrName) == noErr
    assert g.mem.read(name, 25) == b"\x18.Display_Video_Apple_TFB"
    assert sp(SReadDrvrName, id=2) == smNoMoresRsrcs


def test_the_cards_format_block_and_slot_information(g):
    card_rom = video(g) and g.system.slot_card
    fh = g.ptr(bytes(20))
    sp = SpBlock(g, slot=VIDEO_SLOT, result=fh)
    assert sp(SReadFHeader) == noErr
    dir_offset, length, crc, rev, fmt, pattern, _, lanes = struct.unpack(
        ">LLLBBLBB", g.mem.read(fh, 20))
    header = card_rom.rom + card_rom.length - 20
    assert header + (dir_offset - (1 << 24) if dir_offset & 0x800000 else dir_offset) == \
        card_rom.rom
    assert dir_offset >> 24 == 0
    assert length == card_rom.length
    assert (rev, fmt, pattern, lanes) == (1, 1, TEST_PATTERN, 0x0F)
    assert crc == _crc(g.mem.read(card_rom.rom, length), length - 12)
    info = g.ptr(bytes(16))
    assert sp(SReadInfo, result=info) == noErr
    dir_ptr, status_a, status_v, _, byte_lanes = struct.unpack(">LhhBB", g.mem.read(info, 10))
    assert (dir_ptr, status_a, status_v, byte_lanes) == (card_rom.rom, 0, 0, 0x0F)
    assert sp(SCkCardStat) == noErr
    assert sp(SCkCardStat, slot=VIDEO_SLOT + 1) == smEmptySlot
    assert sp(SReadInfo, slot=0) == smEmptySlot


def test_the_cards_device_base_is_the_screens(g):
    sp = SpBlock(g, slot=VIDEO_SLOT, id=VIDEO)
    assert sp(SFindDevBase) == noErr and sp.result == g.system.screen_bits.base
    assert sp(SFindDevBase, id=2) == smNoMoresRsrcs
    assert sp(SFindDevBase, slot=VIDEO_SLOT + 1) == smEmptySlot


def test_the_cards_parameter_ram(g):
    rec = g.ptr(bytes(8))
    sp = SpBlock(g, slot=VIDEO_SLOT, result=rec)
    assert sp(SReadPRAMRec) == noErr and g.mem.read(rec, 8) == bytes(8)
    mine = g.ptr(b"\x12\x34abcdef")
    assert sp(SPutPRAMRec, sPointer=mine) == noErr
    assert sp(SReadPRAMRec) == noErr and g.mem.read(rec, 8) == b"\0\0abcdef"   # not its ID


def test_a_disabled_sresource_is_found_only_when_asked_for(g):
    sp = SpBlock(g, slot=VIDEO_SLOT, id=VIDEO, paramData=1)
    assert sp(SetSRsrcState) == noErr
    kind = dict(category=CAT_DISPLAY, cType=TYP_VIDEO, drvrSW=DR_SW_APPLE, tbMask=1)
    assert SpBlock(g, **kind)(SNextTypeSRsrc) == smNoMoresRsrcs
    assert sp(SRsrcInfo) == smNoMoresRsrcs
    assert sp(SReadDrvrName, result=g.ptr(bytes(256))) == smNoMoresRsrcs
    every = SpBlock(g, paramData=fAll, **kind)
    assert every(SGetTypeSRsrc) == noErr and every.id == VIDEO and every.paramData == 1
    assert sp(SetSRsrcState, slot=VIDEO_SLOT, id=VIDEO, paramData=0) == noErr
    assert sp(SRsrcInfo) == noErr
    assert sp(SetSRsrcState, id=2) == smNoMoresRsrcs


def test_an_sresource_deleted_and_inserted_again(g):
    sp = SpBlock(g, slot=VIDEO_SLOT, id=VIDEO)
    assert sp(SDeleteSRTRec) == noErr
    assert sp(SRsrcInfo) == smNoMoresRsrcs
    assert sp(SDeleteSRTRec) == smRecNotFnd
    assert sp(InsertSRTRec, slot=VIDEO_SLOT, id=VIDEO, refNum=VIDEO_DRIVER, paramData=0) == noErr
    assert sp(SRsrcInfo) == noErr and sp.refNum == VIDEO_DRIVER
    assert sp(InsertSRTRec, slot=VIDEO_SLOT, id=2) == smNoMoresRsrcs    # none in the ROM


def test_the_slot_managers_version(g):
    sp = SpBlock(g, result=99, sPointer=99)
    assert sp(SVersion) == noErr and sp.result == 1 and sp.sPointer == 0
    assert sp(99) == smSelOOBErr


def test_the_rom_is_made_when_its_first_asked_for(g):
    assert getattr(g.system, "slot_card", None) is None
    free = g.system.sys_heap.free_bytes(False)
    video(g)
    assert g.system.sys_heap.free_bytes(False) < free
    assert g.system.sys_heap.contains(g.system.slot_card.rom)


def test_a_mac_plus_has_no_cards(qapp):
    """Nor sResources to find: Spaceship Warlock looks for the screen's,
    and goes on without it."""
    g = Guest()
    sp = SpBlock(g)
    assert sp(SNextTypeSRsrc) == smNoMoresRsrcs
    assert sp(SNextSRsrc) == smNoMoresRsrcs
    assert sp(SCkCardStat) == smEmptySlot
    assert sp(SReadByte) == smsPointerNil
    assert sp(SReadByte, sPointer=0x1000) == smBadsPtrErr
    assert sp(99) == smSelOOBErr
    assert getattr(g.system, "slot_card", None) is None

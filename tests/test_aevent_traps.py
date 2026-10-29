"""The Apple Event Manager's traps as a program calls them: descriptors,
lists and records, parameters and attributes, coercion handlers, sending
Apple events and taking them from the queue, and the dispatch tables."""

import struct

import pytest

from guest import Guest

from macrt.m68k import glue_aevents
from macrt.m68k.glue_aevents import (Composite, errAEAccessorNotFound, errAECoercionFail,
                                     errAEDescNotFound, errAEEventNotHandled,
                                     errAEHandlerNotFound, errAEIllegalIndex, errAENotAEDesc,
                                     errAENotAnObjSpec, errAENotAppleEvent, errAEWrongDataType,
                                     procNotFound, read_desc, state, write_desc)
from macrt.toolbox import constants as k
from macrt.toolbox.memmgr import memFullErr

NOT_A_HANDLE = 0x40                     # low memory, in no heap
NULL = b"null" + bytes(4)               # a null descriptor, as it is in memory
NO_REPLY, QUEUE_REPLY, WAIT_REPLY = 1, 2, 3
SELF = struct.pack(">II", 0, 2)         # kCurrentProcess
paramErr = -50


def code(c: bytes) -> int:
    return int.from_bytes(c, "big")


@pytest.fixture
def g(qapp):
    return Guest()


def desc(g, dtype=b"null", data=b"") -> int:
    p = g.ptr(bytes(8))
    assert write_desc(g, p, dtype, data) == 0
    return p


def bad_desc(g) -> int:
    """A descriptor whose handle is in no heap."""
    p = g.ptr(bytes(8))
    g.mem.w32(p, code(b"TEXT"))
    g.mem.w32(p + 4, NOT_A_HANDLE)
    return p


def new_list(g, is_record=False) -> int:
    p = g.ptr(bytes(8))
    assert g("AECreateList", 0, 0, is_record, p) == 0
    return p


def items(g, p) -> list:
    return Composite.parse(read_desc(g, p)[1]).items


def new_event(g, cls=b"misc", eid=b"dosc", address=None, return_id=-1, transaction_id=0):
    p = g.ptr(bytes(8))
    target = desc(g, b"psn ", SELF) if address is None else address
    assert g("AECreateAppleEvent", code(cls), code(eid), target, return_id, transaction_id, p) == 0
    return p


def outs(g, n: int, size: int = 4):
    return [g.ptr(b"\xff" * size) for _ in range(n)]


def test_descriptors(g, monkeypatch):
    """A descriptor's data is in a handle of its own: it's made, copied,
    coerced and disposed of with it."""
    hello = g.ptr(b"hello")
    p, copy = g.ptr(bytes(8)), g.ptr(bytes(8))
    assert g("AECreateDesc", code(b"TEXT"), hello, 5, p) == 0
    assert read_desc(g, p) == (b"TEXT", b"hello")
    assert g("AEDuplicateDesc", p, copy) == 0
    assert read_desc(g, copy) == (b"TEXT", b"hello")
    assert g.mem.r32(copy + 4) != g.mem.r32(p + 4)
    h = g.mem.r32(copy + 4)
    assert g("AEDisposeDesc", copy) == 0
    assert g.mem.read(copy, 8) == NULL and not g.heap.is_handle(h)
    for ptr, size in ((0, 5), (hello, -1)):                 # no data
        assert g("AECreateDesc", code(b"TEXT"), ptr, size, copy) == 0
        assert read_desc(g, copy) == (b"TEXT", b"")
    assert g("AECreateDesc", code(b"null"), 0, 0, copy) == 0
    assert g.mem.read(copy, 8) == NULL                      # no handle at all
    assert g("AECreateDesc", code(b"null"), hello, 5, copy) == 0
    assert read_desc(g, copy) == (b"null", b"hello")
    g.mem.w32(copy + 4, g.heap.new_empty_handle())
    assert read_desc(g, copy) == (b"null", b"")
    # A handle in no heap isn't a descriptor's; it's let be when disposed of.
    bad = bad_desc(g)
    assert g("AEDuplicateDesc", bad, copy) == errAENotAEDesc
    assert g("AECoerceDesc", bad, code(b"TEXT"), copy) == errAENotAEDesc
    assert g("AEDisposeDesc", bad) == 0 and g.mem.read(bad, 8) == NULL
    # Coercions.
    assert g("AECoercePtr", code(b"long"), g.ptr(struct.pack(">l", 42)), 4, code(b"TEXT"),
             copy) == 0
    assert read_desc(g, copy) == (b"TEXT", b"42")
    assert g("AECoercePtr", code(b"TEXT"), 0, 3, code(b"TEXT"), copy) == 0
    assert read_desc(g, copy) == (b"TEXT", b"")
    assert g("AECoercePtr", code(b"TEXT"), hello, 5, code(b"long"), copy) == errAECoercionFail
    assert g("AECoerceDesc", desc(g, b"TEXT", b" 7"), code(b"shor"), copy) == 0
    assert read_desc(g, copy) == (b"shor", b"\0\7")
    assert g("AECoerceDesc", p, code(b"long"), copy) == errAECoercionFail
    # With no memory for its handle, a descriptor is a null one.
    monkeypatch.setattr(g.heap, "new_handle", lambda *args, **kwargs: 0)
    assert g("AECreateDesc", code(b"TEXT"), hello, 5, copy) == memFullErr
    assert g.mem.read(copy, 8) == NULL
    assert g("AECreateDesc", code(b"null"), 0, 0, copy) == 0


def test_a_lists_items(g, monkeypatch):
    """Items are put at the end (index 0, or one past the last) or in
    place of one, and taken by index, coerced to the type asked for."""
    lst = new_list(g)
    assert read_desc(g, lst)[0] == b"list"
    count = g.ptr(bytes(4))
    assert g("AECountItems", lst, count) == 0 and g.mem.r32(count) == 0
    one = g.ptr(struct.pack(">l", 1))
    assert g("AEPutPtr", lst, 0, code(b"long"), one, 4) == 0
    assert g("AEPutPtr", lst, 2, code(b"TEXT"), g.ptr(b"two"), 3) == 0
    assert g("AEPutDesc", lst, 3, desc(g, b"TEXT", b"three")) == 0
    assert g("AEPutPtr", lst, 3, code(b"TEXT"), g.ptr(b"3"), 1) == 0        # replaced
    assert g("AEPutPtr", lst, 0, code(b"TEXT"), 0, 9) == 0                   # NIL: no data
    for index in (6, -1):
        assert g("AEPutPtr", lst, index, code(b"long"), one, 4) == errAEIllegalIndex
    assert g("AEPutDesc", lst, 0, bad_desc(g)) == errAENotAEDesc
    assert items(g, lst) == [[bytes(4), b"long", struct.pack(">l", 1)],
                             [bytes(4), b"TEXT", b"two"], [bytes(4), b"TEXT", b"3"],
                             [bytes(4), b"TEXT", b""]]
    assert g("AECountItems", lst, count) == 0 and g.mem.r32(count) == 4

    key, dtype, actual = outs(g, 3)
    data = g.ptr(b"\xff" * 8)
    assert g("AEGetNthPtr", lst, 1, code(b"TEXT"), key, dtype, data, 8, actual) == 0
    assert (g.mem.r32(key), g.mem.read(dtype, 4), g.mem.read(data, 2), g.mem.r32(actual)) \
        == (0, b"TEXT", b"1\xff", 1)
    assert g("AEGetNthPtr", lst, 2, code(b"****"), key, dtype, data, 2, actual) == 0
    assert (g.mem.read(data, 3), g.mem.r32(actual)) == (b"tw\xff", 3)      # what there's room for
    for room, data_p in ((0, data), (8, 0)):
        assert g("AEGetNthPtr", lst, 3, code(b"****"), key, dtype, data_p, room, actual) == 0
        assert (g.mem.read(data, 3), g.mem.r32(actual)) == (b"tw\xff", 1)
    for index in (0, 5):
        assert g("AEGetNthPtr", lst, index, code(b"****"), key, dtype, data, 8,
                 actual) == errAEIllegalIndex
    assert g("AEGetNthPtr", lst, 2, code(b"long"), key, dtype, data, 8,
             actual) == errAECoercionFail

    result = g.ptr(bytes(8))
    g.mem.w32(key, 0xFFFFFFFF)
    assert g("AEGetNthDesc", lst, 1, code(b"TEXT"), key, result) == 0
    assert read_desc(g, result) == (b"TEXT", b"1") and g.mem.r32(key) == 0
    assert g("AEGetNthDesc", lst, 5, code(b"****"), key, result) == errAEIllegalIndex
    assert g("AESizeOfNthItem", lst, 2, dtype, actual) == 0
    assert (g.mem.read(dtype, 4), g.mem.r32(actual)) == (b"TEXT", 3)
    assert g("AESizeOfNthItem", lst, 1, dtype, actual) == 0
    assert (g.mem.read(dtype, 4), g.mem.r32(actual)) == (b"long", 4)
    assert g("AESizeOfNthItem", lst, 0, dtype, actual) == errAEIllegalIndex

    assert g("AEDeleteItem", lst, 1) == 0
    assert [e[2] for e in items(g, lst)] == [b"two", b"3", b""]
    assert g("AEDeleteItem", lst, 3) == 0
    for index in (0, 3):
        assert g("AEDeleteItem", lst, index) == errAEIllegalIndex
    assert [e[2] for e in items(g, lst)] == [b"two", b"3"]

    # A record's items have keywords.
    rec = new_list(g, is_record=True)
    assert read_desc(g, rec)[0] == b"reco"
    assert g("AEPutParamPtr", rec, code(b"name"), code(b"TEXT"), g.ptr(b"x"), 1) == 0
    assert g("AEGetNthPtr", rec, 1, code(b"****"), key, dtype, data, 8, actual) == 0
    assert g.mem.read(key, 4) == b"name"
    assert g("AEGetNthDesc", rec, 1, code(b"****"), key, result) == 0
    assert g.mem.read(key, 4) == b"name"

    # What isn't a list.
    text, cut_short = desc(g, b"TEXT", b"words"), desc(g, b"list", b"AEls\0\0")
    for p, err in ((text, errAEWrongDataType), (cut_short, errAEWrongDataType),
                   (bad_desc(g), errAENotAEDesc), (0, errAENotAEDesc)):
        assert g("AECountItems", p, count) == err
        assert g("AEGetNthPtr", p, 1, code(b"****"), key, dtype, data, 8, actual) == err
        assert g("AEGetNthDesc", p, 1, code(b"****"), key, result) == err
        assert g("AESizeOfNthItem", p, 1, dtype, actual) == err
        assert g("AEPutPtr", p, 0, code(b"long"), one, 4) == err
        assert g("AEDeleteItem", p, 1) == err

    # With no memory for the list to grow, it's as it was.
    monkeypatch.setattr(g.heap, "set_handle_size", lambda h, size: False)
    assert g("AEPutPtr", lst, 0, code(b"long"), one, 4) == memFullErr
    assert [e[2] for e in items(g, lst)] == [b"two", b"3"]


def test_parameters_and_attributes(g):
    """A record's items, and an Apple event's, are its parameters, by
    keyword; an Apple event's attributes are kept apart from them."""
    rec = new_list(g, is_record=True)
    assert g("AEPutParamPtr", rec, code(b"size"), code(b"long"),
             g.ptr(struct.pack(">l", 12)), 4) == 0
    assert g("AEPutParamDesc", rec, code(b"name"), desc(g, b"TEXT", b"Fred")) == 0
    assert g("AEPutParamPtr", rec, code(b"size"), code(b"shor"), g.ptr(b"\0\5"), 2) == 0
    assert g("AEPutParamPtr", rec, code(b"none"), code(b"TEXT"), 0, 4) == 0
    assert g("AEPutParamDesc", rec, code(b"name"), bad_desc(g)) == errAENotAEDesc
    assert items(g, rec) == [[b"size", b"shor", b"\0\5"], [b"name", b"TEXT", b"Fred"],
                             [b"none", b"TEXT", b""]]
    dtype, size = outs(g, 2)
    data, result = g.ptr(bytes(8)), g.ptr(bytes(8))
    assert g("AEGetParamPtr", rec, code(b"size"), code(b"long"), dtype, data, 8, size) == 0
    assert (g.mem.read(dtype, 4), g.mem.read(data, 4), g.mem.r32(size)) \
        == (b"long", struct.pack(">l", 5), 4)
    assert g("AEGetParamPtr", rec, code(b"name"), code(b"****"), dtype, data, -1, size) == 0
    assert (g.mem.read(data, 4), g.mem.r32(size)) == (struct.pack(">l", 5), 4)   # no room
    assert g("AEGetParamPtr", rec, code(b"what"), code(b"****"), dtype, data, 8,
             size) == errAEDescNotFound
    assert g("AEGetParamPtr", rec, code(b"name"), code(b"long"), dtype, data, 8,
             size) == errAECoercionFail
    assert g("AEGetParamDesc", rec, code(b"name"), code(b"****"), result) == 0
    assert read_desc(g, result) == (b"TEXT", b"Fred")
    assert g("AEGetParamDesc", rec, code(b"what"), code(b"****"), result) == errAEDescNotFound
    assert g("AESizeOfParam", rec, code(b"name"), dtype, size) == 0
    assert (g.mem.read(dtype, 4), g.mem.r32(size)) == (b"TEXT", 4)
    assert g("AESizeOfParam", rec, code(b"what"), dtype, size) == errAEDescNotFound
    assert g("AEDeleteParam", rec, code(b"size")) == 0
    assert g("AEDeleteParam", rec, code(b"size")) == errAEDescNotFound
    assert [e[0] for e in items(g, rec)] == [b"name", b"none"]

    # A list has no parameters, and only an Apple event has attributes.
    lst = new_list(g)
    for p, err in ((lst, errAEWrongDataType), (bad_desc(g), errAENotAEDesc)):
        assert g("AEPutParamPtr", p, code(b"name"), code(b"TEXT"), data, 1) == err
        assert g("AEGetParamPtr", p, code(b"name"), code(b"****"), dtype, data, 8, size) == err
        assert g("AEDeleteParam", p, code(b"name")) == err
    for p in (rec, lst):
        assert g("AEPutAttributePtr", p, code(b"name"), code(b"TEXT"), data,
                 1) == errAEWrongDataType
        assert g("AEGetAttributeDesc", p, code(b"name"), code(b"****"),
                 result) == errAEWrongDataType

    ev = new_event(g, transaction_id=5)
    assert g("AEPutParamPtr", ev, code(b"----"), code(b"TEXT"), g.ptr(b"doc"), 3) == 0
    assert g("AEPutAttributePtr", ev, code(b"mine"), code(b"TEXT"), g.ptr(b"x"), 1) == 0
    assert g("AEPutAttributePtr", ev, code(b"what"), code(b"TEXT"), 0, 1) == 0
    assert g("AEPutAttributeDesc", ev, code(b"evid"), desc(g, b"type", b"quit")) == 0
    assert g("AEPutAttributeDesc", ev, code(b"evid"), bad_desc(g)) == errAENotAEDesc
    c = Composite.parse(read_desc(g, ev)[1])
    assert c.items == [[b"----", b"TEXT", b"doc"]]
    assert [e[0] for e in c.attrs] == [b"evcl", b"evid", b"addr", b"rtid", b"tran",
                                       b"mine", b"what"]
    assert g("AEGetAttributePtr", ev, code(b"evcl"), code(b"****"), dtype, data, 8, size) == 0
    assert (g.mem.read(dtype, 4), g.mem.read(data, 4)) == (b"type", b"misc")
    assert g("AEGetAttributeDesc", ev, code(b"evid"), code(b"****"), result) == 0
    assert read_desc(g, result) == (b"type", b"quit")
    assert g("AEGetAttributeDesc", ev, code(b"tran"), code(b"****"), result) == 0
    assert read_desc(g, result) == (b"long", struct.pack(">l", 5))
    assert g("AESizeOfAttribute", ev, code(b"addr"), dtype, size) == 0
    assert (g.mem.read(dtype, 4), g.mem.r32(size)) == (b"psn ", 8)
    assert g("AESizeOfAttribute", ev, code(b"----"), dtype, size) == errAEDescNotFound
    assert g("AEGetAttributeDesc", ev, code(b"----"), code(b"****"), result) == errAEDescNotFound
    assert g("AEGetParamDesc", ev, code(b"evcl"), code(b"****"), result) == errAEDescNotFound
    count = g.ptr(bytes(4))
    assert g("AECountItems", ev, count) == 0 and g.mem.r32(count) == 1


def test_making_an_apple_event(g):
    """Its class, ID and address, and a return ID of its own unless it's
    given one."""
    def attrs(ev):
        return {e[0]: e[1:] for e in Composite.parse(read_desc(g, ev)[1]).attrs}
    first = attrs(new_event(g, b"aevt", b"odoc"))
    assert first == {b"evcl": [b"type", b"aevt"], b"evid": [b"type", b"odoc"],
                     b"addr": [b"psn ", SELF], b"rtid": first[b"rtid"],
                     b"tran": [b"long", bytes(4)]}
    assert first[b"rtid"][0] == b"shor"
    then = struct.unpack(">h", first[b"rtid"][1])[0] + 1
    assert attrs(new_event(g))[b"rtid"] == [b"shor", struct.pack(">h", then)]
    assert attrs(new_event(g, return_id=77))[b"rtid"] == [b"shor", struct.pack(">h", 77)]
    assert attrs(new_event(g, address=0))[b"addr"] == [b"null", b""]
    assert g("AECreateAppleEvent", code(b"aevt"), code(b"odoc"), bad_desc(g), -1, 0,
             g.ptr(bytes(8))) == errAENotAEDesc


def test_coercion_handlers(g, monkeypatch):
    """The application's handlers before the system's, and in each table
    one for the type before one for any type: called with a descriptor or
    with a pointer and a size, as they were installed."""
    seen = []

    def by_desc(from_p, to, refcon, result):
        seen.append(("desc", read_desc(g, from_p), to, refcon))
        return write_desc(g, result, b"TEXT", b"<" + read_desc(g, from_p)[1] + b">")

    def by_ptr(dtype, data_p, size, to, refcon, result):
        seen.append(("ptr", dtype, g.mem.read(data_p, size), to, refcon))
        return write_desc(g, result, b"long", struct.pack(">l", size))

    g.procs.update({0x1000: by_desc, 0x2000: by_ptr, 0x3000: lambda *args: paramErr})
    for from_type, to, proc, refcon, is_desc, is_sys in [
            (b"CUST", b"TEXT", 0x1000, 11, True, False),
            (b"****", b"long", 0x2000, 22, False, False),
            (b"CUST", b"long", 0x3000, 33, False, True),
            (b"OTHR", b"shor", 0x3000, 44, False, True),
            (b"****", b"shor", 0x2000, 55, False, True)]:
        assert g("AEInstallCoercionHandler", code(from_type), code(to), proc, refcon, is_desc,
                 is_sys) == 0
    ab, result = g.ptr(b"ab"), g.ptr(bytes(8))
    g("AECoercePtr", code(b"CUST"), ab, 2, code(b"TEXT"), result)
    before = len(g.heap.blocks())
    assert g("AECoercePtr", code(b"CUST"), ab, 2, code(b"TEXT"), result) == 0
    assert read_desc(g, result) == (b"TEXT", b"<ab>")
    assert len(g.heap.blocks()) == before + 1               # the result's, and nothing else
    assert seen[-1] == ("desc", (b"CUST", b"ab"), code(b"TEXT"), 11)
    assert g("AECoerceDesc", desc(g, b"CUST", b"ab"), code(b"long"), result) == 0
    assert read_desc(g, result) == (b"long", struct.pack(">l", 2))
    assert seen[-1] == ("ptr", code(b"CUST"), b"ab", code(b"long"), 22)
    assert g("AECoercePtr", code(b"BLAH"), g.ptr(b"xyz"), 3, code(b"shor"), result) == 0
    assert read_desc(g, result) == (b"long", struct.pack(">l", 3))
    assert seen[-1][-1] == 55
    calls = len(g.calls)
    assert g("AECoercePtr", code(b"OTHR"), ab, 2, code(b"shor"), result) == errAECoercionFail
    (addr, args), = g.calls[calls:]
    assert addr == 0x3000 and [args[i] for i in (0, 2, 3, 4)] \
        == [("l", code(b"OTHR")), ("l", 2), ("l", code(b"shor")), ("l", 44)]
    assert g("AECoercePtr", code(b"OTHR"), ab, 2, code(b"bool"), result) == errAECoercionFail

    proc, refcon = outs(g, 2)
    is_desc = g.ptr(b"\xff\xff")
    assert g("AEGetCoercionHandler", code(b"CUST"), code(b"TEXT"), proc, refcon, is_desc,
             False) == 0
    assert (g.mem.r32(proc), g.mem.r32(refcon), g.mem.read(is_desc, 2)) == (0x1000, 11, b"\1\xff")
    assert g("AEGetCoercionHandler", code(b"****"), code(b"long"), proc, refcon, is_desc,
             False) == 0
    assert (g.mem.r32(proc), g.mem.r32(refcon), g.mem.read(is_desc, 2)) == (0x2000, 22, b"\0\xff")
    assert g("AEGetCoercionHandler", code(b"CUST"), code(b"long"), proc, refcon, is_desc,
             False) == errAEHandlerNotFound
    assert g("AEGetCoercionHandler", code(b"CUST"), code(b"long"), proc, refcon, is_desc,
             True) == 0
    assert (g.mem.r32(proc), g.mem.r32(refcon)) == (0x3000, 33)
    assert g("AERemoveCoercionHandler", code(b"CUST"), code(b"TEXT"), 0x2000,
             False) == errAEHandlerNotFound
    assert g("AERemoveCoercionHandler", code(b"CUST"), code(b"TEXT"), 0x1000, False) == 0
    assert g("AERemoveCoercionHandler", code(b"CUST"), code(b"TEXT"), 0x1000,
             False) == errAEHandlerNotFound
    assert g("AECoercePtr", code(b"CUST"), ab, 2, code(b"TEXT"), result) == errAECoercionFail
    assert g("AERemoveCoercionHandler", code(b"****"), code(b"long"), 0, False) == 0  # any proc
    assert g("AECoercePtr", code(b"CUST"), ab, 2, code(b"long"), result) == errAECoercionFail
    assert g.calls[-1][0] == 0x3000 and g.calls[-1][1][4] == ("l", 33)    # the system's now
    assert g("AERemoveCoercionHandler", code(b"CUST"), code(b"long"), 0x3000, True) == 0
    assert g("AEGetCoercionHandler", code(b"CUST"), code(b"long"), proc, refcon, is_desc,
             True) == errAEHandlerNotFound

    # With no memory to call it with, a handler isn't called.
    calls = len(g.calls)
    monkeypatch.setattr(g.heap, "new_ptr", lambda *args, **kwargs: 0)
    assert g("AECoercePtr", code(b"BLAH"), ab, 2, code(b"shor"), result) == errAECoercionFail
    assert len(g.calls) == calls


def test_the_handler_tables(g):
    """Event handlers, special handlers and object accessors, each the
    application's or the system's, are looked up and removed by what they
    were installed for; removing one takes the procedure it's for, or
    NIL for any."""
    proc, refcon = outs(g, 2)
    odoc = code(b"aevt"), code(b"odoc")
    assert g("AEInstallEventHandler", *odoc, 0x1000, 7, False) == 0
    assert g("AEGetEventHandler", *odoc, proc, refcon, False) == 0
    assert (g.mem.r32(proc), g.mem.r32(refcon)) == (0x1000, 7)
    assert g("AEGetEventHandler", *odoc, 0, 0, False) == 0
    assert g("AEGetEventHandler", *odoc, proc, refcon, True) == errAEHandlerNotFound
    assert g("AEGetEventHandler", code(b"aevt"), code(b"quit"), proc, refcon,
             False) == errAEHandlerNotFound
    assert g("AERemoveEventHandler", *odoc, 0x2000, False) == errAEHandlerNotFound
    assert g("AERemoveEventHandler", *odoc, 0x1000, True) == errAEHandlerNotFound
    assert g("AERemoveEventHandler", *odoc, 0x1000, False) == 0
    assert g("AEGetEventHandler", *odoc, proc, refcon, False) == errAEHandlerNotFound
    assert g("AEInstallEventHandler", *odoc, 0x1000, 7, False) == 0
    assert g("AERemoveEventHandler", *odoc, 0, False) == 0

    assert g("AEInstallSpecialHandler", code(b"blck"), 0x3000, True) == 0
    assert g("AEGetSpecialHandler", code(b"blck"), proc, True) == 0
    assert g.mem.r32(proc) == 0x3000
    assert g("AEGetSpecialHandler", code(b"blck"), proc, False) == errAEHandlerNotFound
    assert g("AERemoveSpecialHandler", code(b"blck"), 0x3001, True) == errAEHandlerNotFound
    assert g("AERemoveSpecialHandler", code(b"blck"), 0x3000, True) == 0
    assert g("AERemoveSpecialHandler", code(b"blck"), 0, True) == errAEHandlerNotFound

    window = code(b"cwin"), code(b"null")
    assert g("AEInstallObjectAccessor", *window, 0x4000, 9, False) == 0
    assert g("AEGetObjectAccessor", *window, proc, refcon, False) == 0
    assert (g.mem.r32(proc), g.mem.r32(refcon)) == (0x4000, 9)
    assert g("AEGetObjectAccessor", *window, proc, refcon, True) == errAEHandlerNotFound
    assert g("AERemoveObjectAccessor", *window, 0x4001, False) == errAEHandlerNotFound
    assert g("AERemoveObjectAccessor", *window, 0x4000, False) == 0
    assert g("AEGetObjectAccessor", *window, proc, refcon, False) == errAEHandlerNotFound
    assert g("AEInstallObjectAccessor", *window, 0x4000, 9, True) == 0
    assert g("AERemoveObjectAccessor", *window, 0x4000, True) == 0
    assert g("AEGetObjectAccessor", *window, proc, refcon, True) == errAEHandlerNotFound


def install(g, cls, eid, refcon, is_sys=False, proc=0x1000):
    assert g("AEInstallEventHandler", code(cls), code(eid), proc, refcon, is_sys) == 0


def test_sending_an_apple_event_to_itself(g):
    """The application's handler for it is called at once; if it doesn't
    handle it, the system's.  A reply, if the sender waits for one, has
    the handler's error in it."""
    seen, errs, answers = [], [], []

    def handler(event_p, reply_p, refcon):
        ev = Composite.parse(read_desc(g, event_p)[1])
        seen.append((refcon, ev.find(b"esrc", True)[2], read_desc(g, reply_p)[0]))
        if answers:
            write_desc(g, reply_p, b"TEXT", answers.pop())
        return errs.pop(0) if errs else 0

    g.procs[0x1000] = handler
    install(g, b"misc", b"dosc", 1)
    ev, reply = new_event(g), g.ptr(bytes(8))
    assert g("AESend", ev, reply, WAIT_REPLY, 0, 0, 0, 0) == 0
    assert seen == [(1, struct.pack(">h", 2), b"aevt")]       # from the same process
    answer = Composite.parse(read_desc(g, reply)[1])
    assert [answer.find(b"evcl", True)[2], answer.find(b"evid", True)[2]] == [b"aevt", b"ansr"]
    assert answer.items == []
    assert read_desc(g, ev)[0] == b"aevt"                       # the sender's is its own
    errs.append(paramErr)
    assert g("AESend", ev, reply, WAIT_REPLY, 0, 0, 0, 0) == 0
    answer = Composite.parse(read_desc(g, reply)[1])
    assert answer.find(b"errn") == [b"errn", b"shor", struct.pack(">h", paramErr)]
    errs.append(errAEEventNotHandled)
    assert g("AESend", ev, reply, WAIT_REPLY, 0, 0, 0, 0) == errAEEventNotHandled

    # Without waiting for a reply, there's none.
    for mode in (NO_REPLY, QUEUE_REPLY):
        g.mem.write(reply, b"junkjunk")
        errs.append(paramErr)
        assert g("AESend", ev, reply, mode, 0, 0, 0, 0) == 0
        assert g.mem.read(reply, 8) == NULL and seen[-1][2] == b"null"
    before = len(g.heap.blocks())
    answers.append(b"answered anyway")
    assert g("AESend", ev, reply, NO_REPLY, 0, 0, 0, 0) == 0
    assert g.mem.read(reply, 8) == NULL and not answers
    assert len(g.heap.blocks()) == before       # its copy, and the reply it was given, disposed of
    assert g("AESend", ev, 0, WAIT_REPLY, 0, 0, 0, 0) == 0
    assert seen[-1][2] == b"null"

    # Only the application itself is sent to.
    serial = struct.pack(">II", 0, g.process.serial_number)
    for dtype, data in ((b"psn ", serial), (b"sign", b"TEST")):
        assert g("AESend", new_event(g, address=desc(g, dtype, data)), reply, NO_REPLY,
                 0, 0, 0, 0) == 0
    calls = len(g.calls)
    for dtype, data in ((b"psn ", struct.pack(">II", 0, 99)), (b"psn ", bytes(4)),
                        (b"sign", b"OTHR"), (b"TEXT", b"TEST")):
        assert g("AESend", new_event(g, address=desc(g, dtype, data)), reply, NO_REPLY,
                 0, 0, 0, 0) == procNotFound
    anonymous = desc(g, b"aevt", Composite(b"aevt").flatten())
    assert g("AESend", anonymous, reply, NO_REPLY, 0, 0, 0, 0) == procNotFound
    assert len(g.calls) == calls
    assert g("AESend", new_list(g, True), reply, NO_REPLY, 0, 0, 0, 0) == errAEWrongDataType
    assert g("AESend", bad_desc(g), reply, NO_REPLY, 0, 0, 0, 0) == errAENotAEDesc


def test_which_handler_handles_it(g):
    """The application's for the class and ID, for the class, for the ID,
    then for any; then, if that doesn't handle it, the system's."""
    refcons = []

    def handler(event_p, reply_p, refcon):
        refcons.append(refcon)
        return errAEEventNotHandled if refcon in not_handled else 0

    g.procs[0x1000] = handler
    not_handled = {1, 6}
    for cls, eid, refcon in ((b"misc", b"dosc", 1), (b"misc", b"****", 2), (b"****", b"dosc", 3)):
        install(g, cls, eid, refcon)
    install(g, b"misc", b"dosc", 6, is_sys=True)
    install(g, b"****", b"****", 7, is_sys=True)
    ev = new_event(g)
    assert g("AESend", ev, 0, NO_REPLY, 0, 0, 0, 0) == errAEEventNotHandled
    assert refcons == [1, 6]
    not_handled.clear()
    for cls, eid, then in ((b"misc", b"dosc", 2), (b"misc", b"****", 3), (b"****", b"dosc", 6)):
        assert g("AERemoveEventHandler", code(cls), code(eid), 0, False) == 0
        refcons.clear()
        assert g("AESend", ev, 0, NO_REPLY, 0, 0, 0, 0) == 0
        assert refcons == [then]
    install(g, b"****", b"****", 5)
    refcons.clear()
    assert g("AESend", ev, 0, NO_REPLY, 0, 0, 0, 0) == 0
    assert refcons == [5]


def test_the_current_event_and_suspending_it(g):
    """The event being handled is the current one.  One its handler
    suspends isn't disposed of until it's resumed, and handled then by
    the standard dispatch, by a dispatcher of the application's, or not
    at all."""
    current, saved = g.ptr(b"junkjunk"), []
    assert g("AEGetTheCurrentEvent", current) == 0 and g.mem.read(current, 8) == NULL
    assert g("AESetTheCurrentEvent", current) == 0

    def handler(event_p, reply_p, refcon):
        g("AEGetTheCurrentEvent", current)
        assert g.mem.read(current, 8) == g.mem.read(event_p, 8)
        if not saved:
            assert g("AESuspendTheCurrentEvent", event_p) == 0
            saved.append((g.ptr(g.mem.read(event_p, 8)), g.ptr(g.mem.read(reply_p, 8))))
        return 0

    g.procs[0x1000] = handler
    install(g, b"misc", b"dosc", 1)
    ev, reply = new_event(g), g.ptr(bytes(8))
    for dispatcher, called in ((-1, [(0x1000, 1)]), (0x2000, [(0x2000, 9)]), (0, [])):
        saved.clear()
        assert g("AESend", ev, reply, WAIT_REPLY, 0, 0, 0, 0) == 0
        event_p, reply_p = saved[0]
        assert read_desc(g, event_p)[0] == b"aevt" and read_desc(g, reply_p)[0] == b"aevt"
        h = g.mem.r32(event_p + 4)
        calls = len(g.calls)
        assert g("AEResumeTheCurrentEvent", event_p, reply_p, dispatcher, 9) == 0
        assert [(addr, args[2][1]) for addr, args in g.calls[calls:]] == called
        if called:
            assert g.calls[-1][1][:2] == (("p", event_p), ("p", reply_p))
        assert g.mem.read(event_p, 8) == NULL and g.mem.read(reply_p, 8) == NULL
        assert not g.heap.is_handle(h) and not state(g).suspended
    g("AEGetTheCurrentEvent", current)
    assert g.mem.read(current, 8) == NULL
    # Resumed by the standard dispatch, what isn't an Apple event is let be.
    calls = len(g.calls)
    text = desc(g, b"TEXT", b"no")
    assert g("AEResumeTheCurrentEvent", text, desc(g), -1, 0) == 0
    assert len(g.calls) == calls and g.mem.read(text, 8) == NULL


def test_the_current_event_while_handling_another(g):
    """An event sent while another is being handled is the current one
    until its handler returns."""
    current, seen = g.ptr(bytes(8)), []

    def is_current(event_p):
        g("AEGetTheCurrentEvent", current)
        seen.append(g.mem.read(current, 8) == g.mem.read(event_p, 8))

    def outer(event_p, reply_p, refcon):
        assert g("AESend", new_event(g, eid=b"nest"), 0, WAIT_REPLY, 0, 0, 0, 0) == 0
        return is_current(event_p)

    g.procs.update({0x1000: outer, 0x2000: lambda event_p, reply_p, refcon: is_current(event_p)})
    install(g, b"misc", b"dosc", 1)
    install(g, b"misc", b"nest", 2, proc=0x2000)
    assert g("AESend", new_event(g), 0, WAIT_REPLY, 0, 0, 0, 0) == 0
    assert seen == [True, True]


def queued(cls: bytes, eid: bytes) -> Composite:
    return Composite(b"aevt", attrs=[[b"evcl", b"type", cls], [b"evid", b"type", eid]])


def test_apple_events_from_the_queue(g, monkeypatch):
    """A high-level event in the queue stands for an Apple event, which
    AEProcessAppleEvent takes to its handler; GetSpecificHighLevelEvent
    shows the filter each one there until it finds the one it wants."""
    refcons = []
    g.procs[0x1000] = lambda event_p, reply_p, refcon: refcons.append(refcon)
    install(g, b"aevt", b"odoc", 1)
    install(g, b"aevt", b"quit", 2)
    glue_aevents.post(g, queued(b"aevt", b"odoc"))
    glue_aevents.post(g, queued(b"aevt", b"quit"))
    odoc, quit = (ev for _, ev in state(g).pending)
    lengths = [len(data) for data, _ in state(g).pending]

    seen = []

    def wanted(eid):
        def filter_proc(context, msg, sender):
            seen.append((context, g.mem.r16(msg), g.mem.r16(msg + 8), g.mem.read(msg + 10, 4),
                         g.mem.read(msg + 18, 4), g.mem.r32(msg + 32), sender - msg))
            return g.mem.read(msg + 18, 4) == eid
        return filter_proc

    err = g.ptr(b"\xff\xff")
    g.procs[0x2000] = wanted(b"quit")
    assert g("GetSpecificHighLevelEvent", 0x2000, 0x5000, err) is True
    assert g.mem.r16(err) == 0
    assert seen == [(0x5000, 36, k.kHighLevelEvent, b"aevt", eid, n, 36)
                    for eid, n in zip((b"odoc", b"quit"), lengths)]
    seen.clear()
    g.procs[0x2000] = wanted(b"none")
    g.mem.w16(err, 0xFFFF)
    assert g("GetSpecificHighLevelEvent", 0x2000, 0, err) is False
    assert g.mem.r16(err) == 0 and len(seen) == 2

    record = g.ptr(bytes(16))
    g.write_event(record, quit)
    assert g("AEProcessAppleEvent", record) == 0
    assert refcons == [2] and [ev for _, ev in state(g).pending] == [odoc]
    mask = k.event_mask(k.kHighLevelEvent)
    assert g.process.events.peek(mask, lambda: None) == (True, odoc)
    assert g("AEProcessAppleEvent", record) == errAENotAppleEvent       # no longer queued
    g.write_event(record, odoc)
    g.mem.w16(record, k.mouseDown)                  # the queued event's, but not high-level
    assert g("AEProcessAppleEvent", record) == errAENotAppleEvent
    assert refcons == [2]
    g.write_event(record, odoc)
    assert g("AEProcessAppleEvent", record) == 0
    assert refcons == [2, 1] and not state(g).pending
    assert not g.process.events.peek(mask, lambda: None)[0]

    # With no memory to hand them over in.
    glue_aevents.post(g, queued(b"aevt", b"odoc"))
    with monkeypatch.context() as m:
        m.setattr(g.heap, "new_handle", lambda *args, **kwargs: 0)
        assert g("AEProcessAppleEvent", record) == memFullErr
    glue_aevents.post(g, queued(b"aevt", b"odoc"))
    monkeypatch.setattr(g.heap, "new_ptr", lambda *args, **kwargs: 0)
    assert g("AEProcessAppleEvent", record) == memFullErr
    glue_aevents.post(g, queued(b"aevt", b"odoc"))
    assert g("GetSpecificHighLevelEvent", 0x2000, 0, err) is False
    assert g.mem.r16(err) == memFullErr & 0xFFFF
    assert refcons == [2, 1]


def test_interacting_with_the_user(g):
    level = g.ptr(b"\xff\xff")
    assert g("AEGetInteractionAllowed", level) == 0
    assert g.mem.read(level, 2) == b"\1\xff"            # kAEInteractWithLocal
    assert g("AESetInteractionAllowed", 2) == 0
    assert g("AEGetInteractionAllowed", level) == 0 and g.mem.read(level, 2) == b"\2\xff"
    assert g("AEGetInteractionAllowed", 0) == 0
    assert g("AEInteractWithUser", 60, 0, 0) == 0
    assert g("AEResetTimer", desc(g)) == 0


def test_calling_an_object_accessor(g):
    """The application's accessor before the system's, and in each table
    one for the class and container before one for the class, for the
    container, then for any."""
    g.procs[0x1000] = lambda desired, container_p, container_class, form, key_p, token_p, \
        refcon: write_desc(g, token_p, b"WIND", bytes([refcon]))
    container, key, token = desc(g), desc(g, b"long", b"\0\0\0\1"), g.ptr(bytes(8))
    args = code(b"cwin"), container, code(b"null"), code(b"indx"), key, token
    assert g("AECallObjectAccessor", *args) == errAEAccessorNotFound
    for cls, container_type, refcon, is_sys in ((b"cwin", b"null", 2, True),
                                                (b"****", b"****", 1, False),
                                                (b"****", b"null", 4, False),
                                                (b"cwin", b"****", 3, False),
                                                (b"cwin", b"null", 5, False)):
        assert g("AEInstallObjectAccessor", code(cls), code(container_type), 0x1000, refcon,
                 is_sys) == 0
        assert g("AECallObjectAccessor", *args) == 0
        assert read_desc(g, token) == (b"WIND", bytes([refcon]))
    assert g.calls[-1] == (0x1000, (("l", code(b"cwin")), ("p", container),
                                    ("l", code(b"null")), ("l", code(b"indx")), ("p", key),
                                    ("p", token), ("l", 5)))
    assert g("AECallObjectAccessor", code(b"cwin"), bad_desc(g), code(b"null"), code(b"indx"),
             key, token) == errAENotAEDesc
    # With no token disposer of the application's, a token is disposed of
    # as any descriptor is.
    h = g.mem.r32(token + 4)
    assert g("AEDisposeToken", token) == 0
    assert g.mem.read(token, 8) == NULL and not g.heap.is_handle(h)


def spec(want=b"cwin", form=b"indx", key=(b"long", b"\0\0\0\1"), container=None,
         leave_out=b"") -> tuple:
    items = [[b"want", b"type", want], [b"form", b"enum", form], [b"seld", *key]]
    if container is not None:
        items.append([b"from", *container])
    return b"obj ", Composite(b"reco", [e for e in items if e[0] != leave_out]).flatten()


def test_what_isnt_an_object_specifier(g, monkeypatch):
    tokens = []

    def accessor(desired, container_p, container_class, form, key_p, token_p, refcon):
        tokens.append(g.mem.r32(container_p + 4))
        return write_desc(g, token_p, b"TOKN", b"t")

    g.procs[0x1000] = accessor
    assert g("AEInstallObjectAccessor", code(b"cwor"), code(b"TOKN"), 0x1000, 0, False) == 0
    token = g.ptr(bytes(8))
    as_list = Composite(b"list", Composite.parse(spec()[1]).items).flatten()
    for dtype, data in [(b"obj ", as_list), spec(leave_out=b"want"),
                        spec(leave_out=b"form"), spec(leave_out=b"seld"), spec(want=b"win"),
                        spec(form=b"index"), spec(container=(b"TEXT", b"window 1")),
                        spec(container=spec(leave_out=b"want")),
                        spec(container=(b"obj ", b"AErc"))]:
        assert g("AEResolve", desc(g, dtype, data), 0, token) == errAENotAnObjSpec, data
    assert g.calls == []
    # Its container can't be resolved: there's no accessor for a window,
    # and so none is called for the word in it.
    assert g("AEInstallObjectAccessor", code(b"cwor"), code(b"null"), 0x1000, 0, False) == 0
    assert g("AEResolve", desc(g, *spec(b"cwor", container=spec())), 0,
             token) == errAEAccessorNotFound
    assert g.calls == []
    for spec_p in (0, bad_desc(g)):
        assert g("AEResolve", spec_p, 0, token) == errAENotAEDesc
    # With no disposer, the container's token is disposed of.
    assert g("AEInstallObjectAccessor", code(b"cwin"), code(b"null"), 0x1000, 0, False) == 0
    assert g("AEInstallObjectAccessor", code(b"cwor"), code(b"TOKN"), 0x1000, 0, False) == 0
    assert g("AEResolve", desc(g, *spec(b"cwor", container=spec())), 0, token) == 0
    assert read_desc(g, token) == (b"TOKN", b"t")
    assert tokens[0] == 0 and tokens[1] and not g.heap.is_handle(tokens[1])
    window = desc(g, *spec())
    monkeypatch.setattr(g.heap, "new_ptr", lambda *args, **kwargs: 0)
    assert g("AEResolve", window, 0, token) == memFullErr


def test_a_private_handler_table_that_isnt_one(g, monkeypatch):
    key, hdlr = g.ptr(b"aevtodoc"), g.ptr(bytes(8))
    for table in (NOT_A_HANDLE, g.ptr(bytes(16))):          # in no heap; a pointer
        assert g("_AE_hdlr_lookup", table, 0, key, hdlr) == errAEHandlerNotFound
        assert g("_AE_hdlr_install", table, 0, key, hdlr) == errAEHandlerNotFound
        assert g("_AE_hdlr_delete", table, 0, key) == errAEHandlerNotFound
    table_p = g.ptr(bytes(4))
    assert g("_AE_hdlr_table_alloc", 4, 0, 0, 0, table_p) == 0
    monkeypatch.setattr(g.heap, "set_handle_size", lambda h, size: False)
    assert g("_AE_hdlr_install", g.mem.r32(table_p), 0, key, hdlr) == memFullErr
    monkeypatch.setattr(g.heap, "new_handle", lambda *args, **kwargs: 0)
    assert g("_AE_hdlr_table_alloc", 4, 0, 0, 0, table_p) == memFullErr

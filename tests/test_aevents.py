"""The Apple Event Manager's descriptor data and its own coercions."""

import struct

from guest import Guest

from macrt.m68k import dispatch
from macrt.m68k.glue_aevents import (AE_VERSION, Composite, coerce, errAEAccessorNotFound,
                                     errAEEventNotHandled, errAEHandlerNotFound,
                                     errAENotAnObjSpec, read_desc, state, write_desc)
from macrt.toolbox.files import paramErr


class Glue:
    """Enough of a Runner for coercions the Apple Event Manager does
    itself: there are no handlers to call."""
    class Process:
        pass

    def __init__(self):
        self.process = self.Process()


def test_a_composites_data_survives_a_round_trip():
    c = Composite(b"aevt")
    c.put(b"evcl", b"type", b"aevt", attr=True)
    c.put(b"----", b"TEXT", b"odd")                 # padded to an even length
    c.put(b"rslt", b"long", struct.pack(">l", 7))
    c.put(b"----", b"TEXT", b"replaced")
    back = Composite.parse(c.flatten())
    assert back == c
    assert back.find(b"----") == [b"----", b"TEXT", b"replaced"]
    assert back.find(b"evcl") is None
    assert back.find(b"evcl", attr=True)[2] == b"aevt"
    assert Composite.parse(b"TEXT") is None
    assert Composite.parse(c.flatten()[:-3]) is None        # cut short


def test_numbers_and_text_coerce_to_each_other():
    t = Glue()
    assert coerce(t, b"shor", struct.pack(">h", -2), b"long") == (b"long", struct.pack(">l", -2))
    assert coerce(t, b"TEXT", b" -12 ", b"shor") == (b"shor", struct.pack(">h", -12))
    assert coerce(t, b"long", struct.pack(">l", 99), b"TEXT") == (b"TEXT", b"99")
    assert coerce(t, b"true", b"", b"bool") == (b"bool", b"\x01")
    assert coerce(t, b"long", struct.pack(">l", 1), b"bool") == (b"bool", b"\x01")
    assert coerce(t, b"enum", b"yes ", b"type") == (b"type", b"yes ")
    for dtype, data, to in [(b"long", struct.pack(">l", 70000), b"shor"),     # too big
                            (b"long", struct.pack(">l", 2), b"bool"),
                            (b"TEXT", b"--12", b"long"), (b"TEXT", b"1_2", b"long"),
                            (b"TEXT", b"twelve", b"long"), (b"long", bytes(4), b"type"),
                            (b"TEXT", b"7" * 5000, b"long")]:           # too long to read
        assert coerce(t, dtype, data, to) is None, (dtype, data, to)


def test_records_take_any_type_and_items_become_lists():
    t = Glue()
    record = Composite(b"reco", [[b"want", b"type", b"cwin"]]).flatten()
    assert coerce(t, b"reco", record, b"obj ") == (b"obj ", record)
    assert coerce(t, b"obj ", record, b"reco") == (b"reco", record)
    assert coerce(t, b"reco", record, b"list") is None
    assert coerce(t, b"long", b"\0\0\0\5", b"****") == (b"long", b"\0\0\0\5")
    dtype, data = coerce(t, b"long", b"\0\0\0\5", b"list")
    assert dtype == b"list"
    assert Composite.parse(data).items == [[bytes(4), b"long", b"\0\0\0\5"]]


def test_a_private_handler_table(qapp):
    """System 7.5's Find File keeps handlers of its own in a table it makes
    with the Apple Event Manager's private calls."""
    g = Guest()
    table_p = g.ptr(bytes(4))
    assert g("_AE_hdlr_table_alloc", 4, 0, 0, 0, table_p) == 0
    table = g.mem.r32(table_p)
    key, other = g.ptr(b"aevtodoc"), g.ptr(b"aevtquit")
    out = g.ptr(bytes(8))
    assert g("_AE_hdlr_lookup", table, 0, key, out) == errAEHandlerNotFound
    assert g("_AE_hdlr_install", table, 0, key, g.ptr(struct.pack(">II", 0x1000, 7))) == 0
    assert g("_AE_hdlr_install", table, 0, other, g.ptr(struct.pack(">II", 0x2000, 8))) == 0
    assert g("_AE_hdlr_install", table, 0, key, g.ptr(struct.pack(">II", 0x3000, 9))) == 0
    assert g("_AE_hdlr_lookup", table, 0, key, out) == 0
    assert g.mem.read(out, 8) == struct.pack(">II", 0x3000, 9)     # the newer one
    assert g("_AE_hdlr_delete", table, 0, key) == 0
    assert g("_AE_hdlr_delete", table, 0, key) == errAEHandlerNotFound
    assert g("_AE_hdlr_lookup", table, 0, other, out) == 0
    assert g.mem.read(out, 8) == struct.pack(">II", 0x2000, 8)
    assert g("_AE_hdlr_install", 0, 0, key, out) == errAEHandlerNotFound


def test_object_callbacks_are_kept(qapp):
    g = Guest()
    procs = tuple(range(0x1000, 0x1007))
    assert g("AESetObjectCallbacks", *procs) == 0
    assert state(g).object_callbacks == procs


def test_every_pack8_signature_takes_what_its_selector_says():
    """The selector's high byte counts the words of arguments: a wrong
    signature leaves the stack unbalanced when a call is skipped, as
    AEManagerInfo's, without its keyword, did Netscape Navigator 2.02's."""
    sigs = [s for s in dispatch.SIGNATURES.values() if s.dispatcher == "Pack8"]
    assert sigs
    for sig in sigs:
        assert sig.stack_bytes == (sig.selector >> 8) * 2, sig.name


def test_ae_manager_info_gives_its_version(qapp):
    g = Guest()
    out = g.ptr(bytes(4))
    assert g("AEManagerInfo", int.from_bytes(b"vers", "big"), out) == 0
    assert g.mem.r32(out) == AE_VERSION
    g.mem.w32(out, 7)
    assert g("AEManagerInfo", int.from_bytes(b"recr", "big"), out) == 0
    assert g.mem.r32(out) == 0                  # nothing is recording
    assert g("AEManagerInfo", int.from_bytes(b"what", "big"), out) == paramErr


def code(c: bytes) -> int:
    return int.from_bytes(c, "big")


def spec(want: bytes, form: bytes, key: tuple, container: tuple = (b"null", b"")) -> tuple:
    """An object specifier: the object of class want that key picks out
    by form in container."""
    items = [[b"want", b"type", want], [b"from", *container], [b"form", b"enum", form],
             [b"seld", *key]]
    return b"obj ", Composite(b"reco", items).flatten()


def test_resolving_an_object_in_an_object_in_the_application(qapp):
    """Netscape Navigator 2.02's Open Location event names its window; the
    accessors the application installed find it, the outermost container
    first, and the tokens of containers are given back to it."""
    g = Guest()
    seen, disposed = [], []

    def window(desired, container_p, container_class, form, key_p, token_p, refcon):
        seen.append(("window", read_desc(g, container_p), container_class, form,
                     read_desc(g, key_p), refcon))
        return write_desc(g, token_p, b"WIND", b"w" + read_desc(g, key_p)[1][-1:])

    def element(desired, container_p, container_class, form, key_p, token_p, refcon):
        seen.append(("element", read_desc(g, container_p), container_class, form,
                     read_desc(g, key_p), refcon))
        data = read_desc(g, container_p)[1] + read_desc(g, key_p)[1]
        return write_desc(g, token_p, b"ELEM", data)

    g.procs[0x1000], g.procs[0x2000] = window, element
    g.procs[0x3000] = lambda token_p: disposed.append(read_desc(g, token_p))
    assert g("AEInstallObjectAccessor", code(b"cwin"), code(b"null"), 0x1000, 5, False) == 0
    assert g("AEInstallObjectAccessor", code(b"****"), code(b"WIND"), 0x2000, 6, True) == 0
    assert g("AESetObjectCallbacks", 0, 0, 0x3000, 0, 0, 0, 0) == 0
    win = spec(b"cwin", b"indx", (b"long", b"\0\0\0\1"))
    word = spec(b"cwor", b"name", (b"TEXT", b"hi"), win)
    spec_p, token_p = g.ptr(bytes(8)), g.ptr(bytes(8))
    write_desc(g, spec_p, *word)
    assert g("AEResolve", spec_p, 0, token_p) == 0
    assert read_desc(g, token_p) == (b"ELEM", b"w\1hi")
    assert seen == [("window", (b"null", b""), code(b"null"), code(b"indx"),
                     (b"long", b"\0\0\0\1"), 5),
                    ("element", (b"WIND", b"w\1"), code(b"cwin"), code(b"name"),
                     (b"TEXT", b"hi"), 6)]
    assert disposed == [(b"WIND", b"w\1")]
    assert g("AEDisposeToken", token_p) == 0
    assert disposed[-1] == (b"ELEM", b"w\1hi")


def test_what_can_not_be_resolved(qapp):
    g = Guest()
    spec_p, token_p = g.ptr(bytes(8)), g.ptr(bytes(8))
    write_desc(g, spec_p, *spec(b"cwin", b"indx", (b"long", b"\0\0\0\1")))
    assert g("AEResolve", spec_p, 0, token_p) == errAEAccessorNotFound
    assert read_desc(g, token_p) == (b"null", b"")
    write_desc(g, spec_p, b"TEXT", b"window 1")
    assert g("AEResolve", spec_p, 0, token_p) == errAENotAnObjSpec
    g.procs[0x1000] = lambda *args: 0
    assert g("AEInstallObjectAccessor", code(b"****"), code(b"****"), 0x1000, 0, False) == 0
    write_desc(g, spec_p, *spec(b"cwin", b"test", (b"long", bytes(4))))
    assert g("AEResolve", spec_p, 0, token_p) == errAEEventNotHandled
    assert g.calls == []

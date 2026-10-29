"""The Edition Manager's traps as a program calls them, past what
test_editions follows: containers whose data isn't macrt's, section
records and aliases that can't be used, edition openers' and I/O
routines' errors, running out of memory, going to a publisher that has
no section registered, and the dialogs' starting folders, previews,
hooks and Cancel buttons (Inside Macintosh: Interapplication
Communication, the Edition Manager)."""

import struct
from concurrent.futures import Future
from contextlib import nullcontext
from types import SimpleNamespace

from PyQt6.QtGui import QColor
from test_dialogs import NoDisplay
from test_editions import (app, code, container, edition, events, new_section, open_edition,
                           publish, read, record, section)

from macrt.m68k import glue_aevents as ae
from macrt.m68k import glue_editions as ed
from macrt.m68k import glue_stdfile as sf
from macrt.m68k.glue_files import put_spec
from macrt.toolbox import aliases as al
from macrt.toolbox import files as fm
from macrt.toolbox.memmgr import memFullErr
from macrt.ui import editiondlg, stdfile

BLACK, WHITE = QColor(0, 0, 0).rgb(), QColor(255, 255, 255).rgb()


def spec_of(t, name, parid=fm.ROOT) -> int:
    """An FSSpec for a document."""
    p = t.ptr(bytes(70))
    put_spec(t, p, t.system.files.boot.vref, parid, name)
    return p


def picture(height, width) -> bytes:
    """A version 1 picture that paints its frame black."""
    return (struct.pack(">H4h", 22, 0, 0, height, width) + b"\x11\x01"
            + b"\x31" + struct.pack(">4h", 0, 0, height, width) + b"\xFF")


def failing(monkeypatch, heap, name, after=0) -> list:
    """The heap's call fails once it has succeeded after times: what the
    calls that succeeded made."""
    real, made = getattr(heap, name), []

    def call(*args, **kwargs):
        if len(made) >= after:
            return False if name == "set_handle_size" else 0
        made.append(real(*args, **kwargs))
        return made[-1]
    monkeypatch.setattr(heap, name, call)
    return made


def own_io(t, rules: list) -> list:
    """The application's own opener, whose I/O routine passes each call
    on to the standard one's unless one of rules, (verb, format, pb),
    answers it: the calls, (verb, format)."""
    m = t.mem
    io_procs, calls = {}, []

    def opener(verb, pb):
        err = t("CallEditionOpenerProc", verb, pb, ed.STANDARD_OPENER)
        if not err and verb in (ed.eoOpen, ed.eoOpenNew):
            io_procs[m.r32(pb + ed.eoIoRefNum)] = m.r32(pb + ed.eoIoProc)
            m.w32(pb + ed.eoIoProc, 0x2100)
        return err

    def io(verb, pb):
        fmt = m.read(pb + ed.ioFormat, 4)
        calls.append((verb, fmt))
        for rule in rules:
            got = rule(verb, fmt, pb)
            if got is not None:
                return got
        return t("CallFormatIOProc", verb, pb, io_procs[m.r32(pb + ed.ioRefNum)])
    t.procs[0x2000], t.procs[0x2100] = opener, io
    assert t("SetEditionOpenerProc", 0x2000) == fm.noErr
    return calls


def refusing(verb, fmt, err):
    """A rule for own_io: err for one verb on one format."""
    return lambda v, f, pb: err if (v, f) == (verb, fmt) else None


# =========================================================================
# Containers, sections and their aliases
# =========================================================================
def test_a_data_fork_that_isnt_an_edition_of_macrts(qapp):
    one = ed.pack([[b"TEXT", b"Hi"]])
    assert ed.parse(one) == [[b"TEXT", b"Hi"]] and ed.parse(b"") == []
    for data in (one[:7],                                   # shorter than its header
                 b"NOPE" + one[4:],                         # not its magic
                 one[:4] + b"\0\2" + one[6:],               # nor its version
                 one[:ed.HEADER.size + ed.ENTRY.size - 1],  # its entry cut short
                 one[:-1]):                                 # an entry past the end
        assert ed.parse(data) is None
    # an edition in another format has the formats its type says
    t = app()
    m = t.mem
    spec, node = edition(t)
    t.system.files.set_fork(node, False, b"Dear Mac,")
    node.type = b"edtt"
    pb = t.ptr(bytes(ed.OPENER_PB))
    put_spec(t, pb + ed.eoInfo + ed.eiContainer, node.volume.vref, node.parid, node.name)
    for mask, err in ((ed.kTEXTformatMask, fm.noErr), (ed.kPICTformatMask, ed.noTypeErr)):
        m.w8(pb + ed.eoFormatsMask, mask)
        assert t("CallEditionOpenerProc", ed.eoCanSubscribe, pb, ed.STANDARD_OPENER) == err
    # but none the standard opener can read
    _, sub = new_section(t, spec, ed.stSubscriber)
    ref = open_edition(t, sub)
    assert t("EditionHasFormat", ref, code(b"TEXT"), 0) == ed.noTypeErr
    assert t("CloseEdition", ref, 0) == fm.noErr


def test_section_records_and_aliases_that_cant_be_used(qapp):
    t = app()
    m = t.mem
    rp, updated = t.ptr(bytes(4)), t.ptr(bytes(1))
    for h in (0, 0x40, t.handle(bytes(ed.SECTION_RECORD))):    # NIL, no handle, version 0
        assert t("OpenEdition", h, rp) == fm.permErr
        assert t("RegisterSection", 0, h, updated) == ed.badSectionErr
        assert t("AssociateSection", h, 0) == fm.paramErr
    spec, node = edition(t)
    _, sub = new_section(t, spec, ed.stSubscriber)
    assert t("RegisterSection", 0, sub, updated) == fm.noErr      # it is already
    assert m.r8(updated) == 0
    assert t("UnRegisterSection", sub) == fm.noErr
    p = record(t, sub)
    alias = m.r32(p + ed.srAlias)
    m.w32(p + ed.srAlias, t.handle(b"not an alias"))
    assert t("RegisterSection", 0, sub, updated) == fm.paramErr
    assert t("AssociateSection", sub, 0) == fm.paramErr
    m.w32(p + ed.srAlias, alias)

    # the container renamed: registering again finds it, and says the alias changed
    files = t.process.files
    files.rename(node.volume.vref, fm.ROOT, "Edition", "Renamed")
    assert t("RegisterSection", 0, sub, updated) == fm.noErr
    assert m.r8(updated) == 1
    assert al.Alias.parse(t.contents(alias)).name == "Renamed"
    assert t("UnRegisterSection", sub) == fm.noErr
    assert t("RegisterSection", 0, sub, updated) == fm.noErr and m.r8(updated) == 0

    # AssociateSection: the alias, made relative to the section's document
    doc = files.create(node.volume.vref, fm.ROOT, "Report")
    doc_spec = spec_of(t, "Report")
    assert t("AssociateSection", sub, doc_spec) == fm.noErr
    assert al.Alias.parse(t.contents(alias)).levels_from == 1
    assert al.resolve(t.system.files, al.Alias.parse(t.contents(alias)), doc).node is node
    assert t("UnRegisterSection", sub) == fm.noErr
    assert t("AssociateSection", sub, doc_spec) == fm.noErr        # found through its alias
    files.delete(node.volume.vref, fm.ROOT, "Renamed")
    assert t("AssociateSection", sub, doc_spec) == fm.fnfErr       # gone


def test_a_container_where_none_can_be(qapp):
    t = app()
    m = t.mem
    err, sub = new_section(t, container(t, "Lost", parid=9999), ed.stSubscriber)
    assert err == ed.containerNotFoundWrn
    assert m.r32(record(t, sub) + ed.srControlBlock) == 0
    assert t("UnRegisterSection", sub) == fm.noErr
    # a publisher's container isn't made in a folder that isn't there
    err, pub = new_section(t, container(t, "Lost", parid=9999), ed.stPublisher)
    assert err == fm.noErr
    assert m.r32(record(t, pub) + ed.srControlBlock) == 0
    # nor on a volume that can't be written
    boot = t.system.files.boot
    boot.locked = True
    try:
        err, pub = new_section(t, container(t, "New Edition"), ed.stPublisher)
    finally:
        boot.locked = False
    assert err == fm.noErr
    assert m.r32(record(t, pub) + ed.srControlBlock) == 0
    assert ed._lookup(t, boot.vref, fm.ROOT, "New Edition") is None
    assert events(t) == []

    # the last container used, gone, is still the one given
    assert new_section(t, container(t, "New Edition"), ed.stPublisher)[0] == fm.noErr
    spec = t.ptr(bytes(ed.CONTAINER_SPEC))
    assert t("GetLastEditionContainerUsed", spec) == fm.noErr
    t.process.files.delete(boot.vref, fm.ROOT, "New Edition")
    m.fill(spec, ed.CONTAINER_SPEC)
    assert t("GetLastEditionContainerUsed", spec) == fm.fnfErr
    assert (m.r32(spec + 2), m.r_pstr(spec + 6)) == (fm.ROOT, b"New Edition")


def test_a_part_of_a_container_is_not_used(qapp):
    t = app()
    spec, _ = edition(t)
    t.mem.w32(spec + ed.ecThePart, 1)
    assert new_section(t, spec, ed.stPublisher) == (ed.badSubPartErr, 0)
    assert t("GetStandardFormats", spec, 0, 0, 0, 0) == ed.badSubPartErr
    assert t("GoToPublisherSection", spec) == ed.badSubPartErr
    gone = container(t, "Gone")
    assert t("GetStandardFormats", gone, 0, 0, 0, 0) == fm.fnfErr
    assert t("GoToPublisherSection", gone) == fm.fnfErr


def test_which_publisher_wrote_an_edition(qapp):
    """Its 'alis' format names the publisher's document and section; one
    a program has written itself needn't be an alias at all."""
    t = app()
    files = t.system.files
    spec, node = edition(t)
    t.process.files.create(node.volume.vref, fm.ROOT, "Report")
    doc_spec = spec_of(t, "Report")
    for data, err in ((b"junk" + struct.pack(">l", 1), fm.noErr),
                      (b"j", fm.noErr),
                      (al.Alias(name="Elsewhere").pack() + struct.pack(">l", 1),
                       ed.notThePublisherWrn)):         # a document that can't be found
        files.set_fork(node, False, ed.pack([[ed.ALIS, data]]))
        got, pub = new_section(t, spec, ed.stPublisher, sid=1, document=doc_spec)
        assert got == err
        assert t("UnRegisterSection", pub) == fm.noErr
    # with no document, the section ID is enough
    files.set_fork(node, False, ed.pack([[ed.ALIS, data]]))
    assert new_section(t, spec, ed.stPublisher, sid=1)[0] == fm.noErr


def test_a_publishers_document_not_saved_yet(qapp):
    """The 'alis' format names where the document will be."""
    t = app()
    spec, node = edition(t)
    boot = t.system.files.boot.name
    for doc_spec, path in ((spec_of(t, "Untitled"), boot + ":Untitled"),
                           (spec_of(t, "Untitled", parid=9999), None)):     # nor its folder
        _, pub = new_section(t, spec, ed.stPublisher, sid=3, document=doc_spec)
        assert publish(t, pub, [(b"TEXT", b"Draft")], document=doc_spec) == fm.noErr
        alias, sid = ed._edition_alias(bytes(dict(ed.parse(bytes(node.fork(False))))[ed.ALIS]))
        assert (alias.name, alias.path, sid) == ("Untitled", path, 3)
        assert t("UnRegisterSection", pub) == fm.noErr


def test_a_quitting_applications_editions_are_closed(qapp):
    a = app()
    b = app(sharing=a)
    spec, node = edition(a)
    _, pub = new_section(a, spec, ed.stPublisher)
    assert publish(a, pub, [(b"TEXT", b"News")]) == fm.noErr
    _, sub = new_section(b, container(b, "Edition"), ed.stSubscriber)
    reading = open_edition(b, sub)
    _, theirs = new_section(b, container(b, "Edition"), ed.stPublisher)
    rp = b.ptr(bytes(4))
    assert b("OpenNewEdition", theirs, code(b"MACR"), 0, rp) == fm.noErr
    writing = b.mem.r32(rp)
    st = ed._state(a)
    assert set(st.opens) == {reading, writing} and len(st.std) == 2
    assert st.controls[node].writer is st.opens[writing]
    b.process.events.kill()
    st = ed._state(a)
    assert st.opens == {} and st.std == {} and st.controls[node].writer is None
    assert not a.system.sys_heap.is_handle(reading)
    assert not a.system.sys_heap.is_handle(writing)
    assert publish(a, pub, [(b"TEXT", b"More news")]) == fm.noErr


# =========================================================================
# Openers and I/O routines
# =========================================================================
def test_what_the_standard_opener_and_io_routine_refuse(qapp):
    t = app()
    m = t.mem
    spec, node = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert publish(t, pub, [(b"TEXT", b"News")]) == fm.noErr
    pb = t.ptr(bytes(ed.OPENER_PB))

    def opener(verb):
        return t("CallEditionOpenerProc", verb, pb, ed.STANDARD_OPENER)
    m.w32(pb + ed.eoIoRefNum, 999)
    assert opener(ed.eoClose) == fm.rfNumErr                # not one it opened
    assert opener(ed.eoCloseNew) == fm.rfNumErr
    assert opener(9) == fm.paramErr                         # no such verb
    put_spec(t, pb + ed.eoInfo + ed.eiContainer, node.volume.vref, node.parid, "Gone")
    assert opener(ed.eoOpen) == fm.fnfErr
    rp = t.ptr(bytes(4))
    for locked in (node, node.volume):      # a container, or a volume, that can't be written
        locked.locked = True
        try:
            assert t("OpenNewEdition", pub, code(b"MACR"), 0, rp) == fm.fLckdErr
        finally:
            locked.locked = False
    assert m.r32(rp) == 0 and ed._state(t).std == {}

    # the I/O routine, called as an application's own routine would call it
    _, sub = new_section(t, spec, ed.stSubscriber)
    ref = open_edition(t, sub)
    io = t.ptr(bytes(ed.FORMAT_PB))

    def call(verb):
        return t("CallFormatIOProc", verb, io, ed.STANDARD_IO)
    m.w32(io + ed.ioRefNum, 999)
    assert call(ed.ioHasFormat) == fm.rfNumErr
    m.w32(io + ed.ioRefNum, ed._state(t).opens[ref].io_refnum)
    m.write(io + ed.ioFormat, b"PICT")
    assert call(ed.ioReadFormat) == ed.noTypeErr            # not in the edition
    assert call(ed.ioNewFormat) == fm.wrPermErr             # one being read
    assert call(ed.ioWriteFormat) == fm.wrPermErr
    assert call(9) == fm.paramErr
    for routine in (0, 0x2001):                 # no routine, or one at an odd address
        assert t("CallFormatIOProc", ed.ioHasFormat, io, routine) == fm.paramErr
    assert t("CloseEdition", ref, 0) == fm.noErr
    assert t("OpenNewEdition", pub, code(b"MACR"), 0, rp) == fm.noErr
    new = m.r32(rp)
    m.w32(io + ed.ioRefNum, ed._state(t).opens[new].io_refnum)
    assert call(ed.ioWriteFormat) == ed.noTypeErr           # a format it hasn't made
    assert t("CloseEdition", new, 0) == fm.noErr


def test_edition_reference_numbers_that_arent_open(qapp):
    t = app()
    mark = t.ptr(bytes(4))
    for ref in (0, 0x40, t.handle(bytes(4))):
        assert t("EditionHasFormat", ref, code(b"TEXT"), 0) == fm.rfNumErr
        assert t("GetEditionFormatMark", ref, code(b"TEXT"), mark) == fm.rfNumErr
        assert t("SetEditionFormatMark", ref, code(b"TEXT"), 0) == fm.rfNumErr
        assert t("CloseEdition", ref, 1) == fm.rfNumErr
    spec, _ = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert publish(t, pub, [(b"TEXT", b"News")]) == fm.noErr
    _, sub = new_section(t, spec, ed.stSubscriber)
    ref = open_edition(t, sub)
    assert t("SetEditionFormatMark", ref, code(b"PICT"), 2) == ed.noTypeErr
    assert t("SetEditionFormatMark", ref, code(b"TEXT"), 2) == fm.noErr
    assert read(t, ref, b"TEXT", 8) == (fm.noErr, b"ws")
    assert t("CloseEdition", ref, 0) == fm.noErr


def test_an_io_routines_errors(qapp):
    t = app()
    m = t.mem
    rules = []
    calls = own_io(t, rules)
    t.process.files.create(t.system.files.boot.vref, fm.ROOT, "Report")
    doc_spec = spec_of(t, "Report")
    spec, node = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher, document=doc_spec)

    # a format it won't make: the publisher's alias, or one a mark is set in
    no_alias = refusing(ed.ioNewFormat, ed.ALIS, fm.dskFulErr)
    rules.append(no_alias)
    rp = t.ptr(bytes(4))
    assert t("OpenNewEdition", pub, code(b"MACR"), doc_spec, rp) == fm.dskFulErr
    assert m.r32(rp) == 0 and m.r32(record(t, pub) + ed.srRefNum) == 0
    st = ed._state(t)
    assert st.opens == {} and st.std == {} and st.controls[node].writer is None
    assert t("OpenNewEdition", pub, code(b"MACR"), 0, rp) == fm.noErr     # without it
    ref = m.r32(rp)
    rules.append(refusing(ed.ioNewFormat, b"PICT", fm.ioErr))
    assert t("SetEditionFormatMark", ref, code(b"PICT"), 0) == fm.ioErr
    assert t("CloseEdition", ref, 0) == fm.noErr
    rules.clear()
    assert publish(t, pub, [(b"TEXT", b"Figures")], document=doc_spec) == fm.noErr

    # GetStandardFormats reads what it can, as the I/O routine gives it
    preview, alias, formats = t.handle(b""), t.handle(b""), t.handle(b"")

    def standard_formats():
        del calls[:]
        return t("GetStandardFormats", spec, 0, preview, alias, formats)

    def unknown_length(verb, fmt, pb):
        if (verb, fmt) != (ed.ioHasFormat, b"TEXT"):
            return None
        err = t("CallFormatIOProc", verb, pb, ed.STANDARD_IO)
        m.w32(pb + ed.ioBuffLen, ed.kFormatLengthUnknown & 0xFFFFFFFF)
        return err
    rules.append(unknown_length)
    assert standard_formats() == fm.noErr
    assert t.contents(preview) == b"Figures"    # read until a chunk came back short
    assert calls.count((ed.ioReadFormat, b"TEXT")) == 1
    rules[:] = [refusing(ed.ioReadFormat, b"TEXT", fm.ioErr)]      # a read that fails
    m.fill(t.system.heap_of(alias).deref(alias), 1)
    assert standard_formats() == fm.ioErr
    assert t.contents(alias)[-4:] == struct.pack(">l", 1)          # the others are read
    assert t.contents(formats).startswith(b"alis")

    def nothing_read(verb, fmt, pb):            # no more, though nothing's wrong
        if verb != ed.ioReadFormat:
            return None
        m.w32(pb + ed.ioBuffLen, 0)
        return fm.noErr
    rules[:] = [nothing_read]
    assert standard_formats() == fm.noErr
    assert (t.contents(preview), t.contents(alias), t.contents(formats)) == (b"", b"", b"")
    t.procs[0x2000] = lambda verb, pb: fm.permErr      # an opener that can't open it
    assert standard_formats() == fm.permErr


def test_closing_an_edition_whose_container_has_gone(qapp):
    t = app()
    m = t.mem
    spec, node = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert t("UnRegisterSection", pub) == fm.noErr

    def opener(verb, pb):                       # one that keeps the edition elsewhere
        if verb == ed.eoCloseNew:
            m.w8(pb + ed.eoSuccess, 0)
        return t("CallEditionOpenerProc", verb, pb, ed.STANDARD_OPENER)
    t.procs[0x2000] = opener
    assert t("SetEditionOpenerProc", 0x2000) == fm.noErr
    rp = t.ptr(bytes(4))
    assert t("OpenNewEdition", pub, code(b"MACR"), 0, rp) == fm.noErr
    t.process.files.delete(node.volume.vref, fm.ROOT, "Edition")
    assert t("CloseEdition", m.r32(rp), 1) == fm.noErr
    assert ed._state(t).commits == {} and ed._state(t).opens == {}


# =========================================================================
# Memory
# =========================================================================
def test_out_of_memory(qapp, monkeypatch):
    t = app()
    m = t.mem
    spec, node = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert publish(t, pub, [(b"TEXT", b"News")]) == fm.noErr
    _, sub = new_section(t, spec, ed.stSubscriber)
    assert t("UnRegisterSection", pub) == fm.noErr
    hp, rp, doc_spec = t.ptr(bytes(4)), t.ptr(bytes(4)), spec_of(t, "Report")
    preview, alias, formats = t.handle(b""), t.handle(b""), t.handle(b"")
    blocks = t.heap.blocks()

    # NewSection: no room for the section's alias, or its container's control block
    made = failing(monkeypatch, t.heap, "new_handle", after=1)
    assert t("NewSection", spec, 0, ed.stPublisher, 1, 0, hp) == memFullErr
    assert len(made) == 1 and not t.heap.is_handle(made[0])
    monkeypatch.undo()
    assert t.heap.blocks() == blocks
    ed._state(t).controls.clear()               # as if no section had the container
    failing(monkeypatch, t.system.sys_heap, "new_handle")
    assert t("NewSection", spec, 0, ed.stPublisher, 1, 0, hp) == memFullErr
    assert m.r32(hp) == 0 and t.heap.blocks() == blocks
    # nor for an edition's reference number, or the handle to read an alias into
    assert t("OpenEdition", sub, rp) == memFullErr
    assert m.r32(rp) == 0 and ed._state(t).std == {} and ed._state(t).opens == {}
    assert t("GoToPublisherSection", spec) == memFullErr
    monkeypatch.undo()

    # no room to write the publisher's alias, or to read formats into
    _, pub = new_section(t, spec, ed.stPublisher)
    failing(monkeypatch, t.heap, "new_ptr")
    assert t("OpenNewEdition", pub, code(b"MACR"), doc_spec, rp) == memFullErr
    assert m.r32(rp) == 0 and ed._state(t).opens == {}
    assert t("GetStandardFormats", spec, 0, preview, alias, formats) == memFullErr
    monkeypatch.undo()
    failing(monkeypatch, t.heap, "set_handle_size")
    assert t("GetStandardFormats", spec, 0, preview, 0, formats) == memFullErr
    monkeypatch.undo()
    assert t("GetStandardFormats", spec, 0, preview, 0, formats) == fm.noErr
    assert t.contents(preview) == b"News"


# =========================================================================
# Going to a publisher
# =========================================================================
def test_going_to_a_publisher_that_has_no_section_registered(qapp):
    """The publisher's document is opened in the application that made
    it, if it's running, and its section scrolled to when the application
    registers it."""
    a = app()
    b = app(sharing=a)
    boot = a.system.files.boot
    doc = a.process.files.create(boot.vref, fm.ROOT, "Report")
    doc.creator = a.process.app.creator
    doc_spec = spec_of(a, "Report")
    spec, node = edition(a)
    _, pub = new_section(a, spec, ed.stPublisher, sid=5, document=doc_spec)
    assert publish(a, pub, [(b"TEXT", b"Figures")], document=doc_spec) == fm.noErr
    assert a("UnRegisterSection", pub) == fm.noErr
    ae.state(a).pending.clear()
    there = container(b, "Edition")
    blocks = a.system.sys_heap.blocks()
    assert b("GoToPublisherSection", there) == fm.fnfErr        # nothing's running
    assert a.system.sys_heap.blocks() == blocks
    b.tb._d = SimpleNamespace(launch_order=[a.process, b.process])
    assert b("GoToPublisherSection", there) == fm.noErr
    report = [[ae.NO_KEY, ae.typeFSS, ae.fss(boot.vref, fm.ROOT, "Report")]]
    assert events(a) == [(ae.kCoreEventClass, ae.kAEOpenDocuments,
                          ae.Composite(ae.typeAEList, report).flatten())]
    assert events(b) == []
    ae.state(a).pending.clear()
    # the document opened, its section is registered
    assert a("RegisterSection", doc_spec, pub, a.ptr(bytes(1))) == fm.noErr
    assert events(a) == [(b"sect", b"scrl", section(pub))]
    assert ed._state(a).scrolls == []
    assert a("UnRegisterSection", pub) == fm.noErr
    ae.state(a).pending.clear()
    a.process.files.delete(boot.vref, fm.ROOT, "Report")
    assert b("GoToPublisherSection", there) == fm.fnfErr        # the document's gone

    # an edition with no publisher's alias is opened itself
    _, plain = edition(a, "Plain")
    _, pub2 = new_section(a, container(a, "Plain"), ed.stPublisher)
    assert publish(a, pub2, [(b"TEXT", b"Plain")]) == fm.noErr
    assert a("UnRegisterSection", pub2) == fm.noErr
    assert b("GoToPublisherSection", container(b, "Plain")) == fm.fnfErr    # MACR's
    plain.creator = a.process.app.creator
    assert b("GoToPublisherSection", container(b, "Plain")) == fm.noErr
    plain_list = [[ae.NO_KEY, ae.typeFSS, ae.fss(boot.vref, fm.ROOT, "Plain")]]
    assert events(a) == [(ae.kCoreEventClass, ae.kAEOpenDocuments,
                          ae.Composite(ae.typeAEList, plain_list).flatten())]
    assert ed._state(a).scrolls == []
    ae.state(a).pending.clear()
    # an application that doesn't take Apple events isn't sent one
    c = app(sharing=a, aware=False)
    b.tb._d.launch_order.insert(0, c.process)
    assert b("GoToPublisherSection", container(b, "Plain")) == fm.noErr
    assert events(a) == [] and events(c) == []
    # nor is one when the publisher's alias names a volume that isn't there
    elsewhere = al.Alias(name="Elsewhere").pack() + struct.pack(">l", 1)
    a.system.files.set_fork(plain, False, ed.pack([[ed.ALIS, elsewhere], [b"TEXT", b"Plain"]]))
    assert b("GoToPublisherSection", container(b, "Plain")) == fm.fnfErr


# =========================================================================
# The dialogs
# =========================================================================
class Host(NoDisplay):
    """The display, with Standard File's or the options dialog up: the
    user takes the steps given, one each time the dialog waits."""

    def __init__(self, *steps, typed=""):
        self.steps = list(steps)
        self.typed = typed                  # the name in the dialog's field
        self.shown = []                     # what each dialog was opened with
        self.launch_order = []
        self.bridge = SimpleNamespace(call=self.call, post=lambda fn, *args: fn(*args),
                                      closed=False)

    def call(self, fn, *args, serve=None, killed=None):
        if fn is stdfile.open_dialog:
            self.shown.append(args)
            return self, self._next()
        if fn is editiondlg.open_options:
            self.shown.append(args)
            return self, (self._next(),)
        return fn(*args)

    def _next(self) -> Future:
        fut = Future()
        fut.set_result(self.steps.pop(0))
        return fut

    # The dialog's own
    def show_place(self, place, extras):
        return (self._next(),)

    def resume(self, *args):
        return (self._next(),)

    def state(self):
        return -1, self.typed, {}


def asking(t, *steps, typed="") -> Host:
    t.yielding = nullcontext
    t.tb._d = Host(*steps, typed=typed)
    return t.tb._d


def publisher_reply(t, parid=fm.ROOT, preview=0, fmt=b"PICT") -> int:
    reply = t.ptr(bytes(122))
    put_spec(t, reply + ed.npContainer, t.system.files.boot.vref, parid, "")
    t.mem.w32(reply + ed.npPreview, preview)
    t.mem.write(reply + ed.npPreviewFormat, fmt)
    return reply


def test_the_new_publisher_dialog_shows_the_preview(qapp):
    t = app()
    previews = []
    for data, fmt in ((picture(10, 20), b"PICT"),       # scaled to fit, keeping its shape
                      (picture(10, 20), ed.PRVW),       # one made to fill it
                      (picture(0, 0), b"PICT")):        # an empty frame
        host = asking(t, ("cancel",))
        assert t("NewPublisherDialog", publisher_reply(t, preview=t.handle(data), fmt=fmt)) == (
            fm.noErr)
        img = host.shown[0][8]
        assert (img.width(), img.height()) == (ed.kPreviewWidth, ed.kPreviewHeight)
        previews.append((img.pixel(60, 60), img.pixel(60, 20)))
    assert previews == [(BLACK, WHITE), (BLACK, BLACK), (WHITE, WHITE)]
    host = asking(t, ("cancel",))
    assert t("NewPublisherDialog", publisher_reply(t, preview=0x40)) == fm.noErr   # no handle
    assert host.shown[0][8] is None


def test_publishing_where_the_reply_says_or_in_an_edition_already_there(qapp):
    t = app()
    m = t.mem
    _, node = edition(t)
    boot = node.volume.vref
    folder = t.process.files.create(boot, fm.ROOT, "Folder", directory=True)
    vol, _, dirid = t.process.files.get_vol()
    for parid, typed, saved, name, replacing in (
            (9999, "edition", (vol.vref, dirid), b"edition", 0),   # where Standard File starts
            (folder.cnid, "News", (boot, folder.cnid), b"News", 0),
            (fm.ROOT, "edition", (boot, fm.ROOT), b"Edition", 1)):    # the edition's own name
        reply = publisher_reply(t, parid)
        asking(t, ("save", typed, False))
        assert t("NewPublisherDialog", reply) == fm.noErr
        assert (m.r8(reply + ed.npCanceled), m.r8(reply + ed.npReplacing)) == (0, replacing)
        assert (m.r16s(reply + ed.npContainer), m.r32(reply + ed.npContainer + 2)) == saved
        assert m.r_pstr(reply + ed.npContainer + 6) == name
    assert vol is not node.volume


def test_the_expanded_dialogs_hooks(qapp):
    t = app()
    m = t.mem
    spec, _ = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert publish(t, pub, [(b"TEXT", b"Sunny")]) == fm.noErr
    _, chart = edition(t, "Chart")
    seen = []
    t.procs[0x3000] = lambda offset, item, w, data: seen.append((offset, item, data)) or item

    asking(t, ("save", "News", False), typed="News")
    reply = publisher_reply(t)
    assert t("NewPublisherExpDialog", reply, 0x00500050, 0, 0x3000, 0, 0x1234) == fm.noErr
    assert m.r8(reply + ed.npCanceled) == 0 and m.r_pstr(reply + ed.npContainer + 6) == b"News"
    n = sf.NEW[True]
    assert seen == [(n.count, sf.sfHookFirstCall, 0x1234), (n.count, n.ok, 0x1234),
                    (n.count, sf.sfHookLastCall, 0x1234)]

    del seen[:]
    host = asking(t, ("open", 0))
    reply = t.ptr(bytes(2 + ed.CONTAINER_SPEC))
    m.w8(reply + ed.nsFormatsMask, ed.kTEXTformatMask)
    put_spec(t, reply + ed.nsContainer, t.system.files.boot.vref, fm.ROOT, "")
    assert t("NewSubscriberExpDialog", reply, 0x00500050, 0, 0x3000, 0, 0) == fm.noErr
    names = [item.name for item in host.shown[0][5].items if item.kind != "folder"]
    assert names == ["Edition"]                                 # not the empty Chart
    assert m.r8(reply + ed.nsCanceled) == 0 and m.r_pstr(reply + ed.nsContainer + 6) == b"Edition"
    n = sf.NEW[False]
    assert [item for _, item, _ in seen] == [sf.sfHookFirstCall, n.ok, sf.sfHookLastCall]


def test_the_options_dialogs_cancel_and_what_it_cant_show(qapp, monkeypatch):
    t = app()
    m = t.mem
    spec, node = edition(t)
    _, sub = new_section(t, spec, ed.stSubscriber)
    reply = t.ptr(bytes(10))
    m.w32(reply + ed.soSectionH, sub)
    host = asking(t, ("mode", True), ("button", "cancel"))
    assert t("SectionOptionsDialog", reply) == fm.noErr
    assert (m.r8(reply + ed.soCanceled), m.r8(reply + ed.soChanged)) == (1, 0)
    assert m.r16(record(t, sub) + ed.srMode) == ed.sumAutomatic   # though the user changed it
    assert host.shown[0][1:] == (False, "Edition", ed._date(node.mddate), False)
    m.w32(reply + ed.soSectionH, 0)
    assert t("SectionOptionsDialog", reply) == fm.paramErr
    assert m.r8(reply + ed.soCanceled) == 1
    m.w32(reply + ed.soSectionH, sub)
    failing(monkeypatch, t.heap, "new_handle")          # no room for its own items
    assert t("SectionOptionsExpDialog", reply, 0, 0, 0x3000, 0, 0) == memFullErr
    assert m.r8(reply + ed.soCanceled) == 1

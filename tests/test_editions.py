"""The Edition Manager (Pack11): publishers writing editions, subscribers
reading them, the section events between them, edition openers and the
dialogs."""

import struct

from builders import size_res
from guest import Processor
from test_filemgr import BUF, DONE, LONG, R, Asm, _dialog, _idle, _launch, host_app, ostype

from macrt.m68k import glue_aevents as ae
from macrt.m68k import glue_editions as ed
from macrt.m68k.glue_files import put_spec
from macrt.m68k.glue_os import Gestalt
from macrt.resfork import Resource
from macrt.toolbox import aliases as al
from macrt.toolbox import files as fm

AWARE = Resource(b"SIZE", -1, size_res(0x60000, 0x40000, flags=ae.isHighLevelEventAware))


def app(sharing=None, aware=True):
    """An application (on sharing's machine), with room on its stack for
    the Edition Manager's parameter blocks."""
    t = Processor([AWARE] if aware else [], sharing)
    t.stack_top = t.ptr(bytes(0x4000)) + 0x4000
    t.cpu.sp = t.stack_top
    return t


def code(b: bytes) -> int:
    return int.from_bytes(b, "big")


def container(t, name, parid=fm.ROOT):
    p = t.ptr(bytes(ed.CONTAINER_SPEC))
    put_spec(t, p, t.system.files.boot.vref, parid, name)
    return p


def edition(t, name="Edition"):
    """A new, empty edition container on the boot volume: its spec and file."""
    spec = container(t, name)
    assert t("CreateEditionContainerFile", spec, code(b"MACR"), 0) == fm.noErr
    return spec, t.process.files.lookup(t.system.files.boot.vref, fm.ROOT, name)


def new_section(t, spec, kind, sid=1, mode=ed.sumAutomatic, document=0):
    hp = t.ptr(bytes(4))
    err = t("NewSection", spec, document, kind, sid, mode, hp)
    return err, t.mem.r32(hp)


def record(t, h):
    return t.system.heap_of(h).deref(h)


def publish(t, h, formats, document=0):
    """Write an edition of formats, [(type, data)], and close it."""
    rp = t.ptr(bytes(4))
    assert t("OpenNewEdition", h, code(b"MACR"), document, rp) == fm.noErr
    ref = t.mem.r32(rp)
    for fmt, data in formats:
        assert t("WriteEdition", ref, code(fmt), t.ptr(data), len(data)) == fm.noErr
    return t("CloseEdition", ref, 1)


def open_edition(t, h):
    rp = t.ptr(bytes(4))
    assert t("OpenEdition", h, rp) == fm.noErr
    return t.mem.r32(rp)


def read(t, ref, fmt, n):
    """ReadEdition's result and what it read."""
    buf, size = t.ptr(bytes(max(n, 1))), t.ptr(struct.pack(">l", n))
    err = t("ReadEdition", ref, code(fmt), buf, size)
    return err, t.mem.read(buf, t.mem.r32(size))


def events(t):
    """The Apple events waiting for t: (class, ID, direct object)."""
    out = []
    for flat, _ in ae.state(t).pending:
        c = ae.Composite.parse(flat)
        direct = c.find(ae.keyDirectObject)
        out.append((*ae._ids(c), direct[2] if direct else None))
    return out


def section(h):
    return struct.pack(">I", h)


def test_gestalt_says_the_edition_manager_is_there(qapp):
    assert Gestalt(Processor(), code(b"edtn")) == (fm.noErr, 1)


def test_a_publisher_writes_an_edition_and_a_subscriber_reads_it(qapp):
    t = app()
    m = t.mem
    spec, node = edition(t)
    assert (node.type, node.creator, bytes(node.fork(False))) == (b"edtu", b"MACR", b"")
    assert t("InitEditionPackVersion", 1) == fm.noErr

    err, pub = new_section(t, spec, ed.stPublisher, sid=7)
    assert err == fm.noErr
    p = record(t, pub)
    assert (m.r8(p + ed.srVersion), m.r8(p + ed.srKind), m.r32s(p + ed.srSectionID)) == (
        1, ed.stPublisher, 7)
    assert m.r32(p + ed.srMdDate) and m.r32(p + ed.srControlBlock)
    assert t("IsRegisteredSection", pub) == fm.noErr

    rp = t.ptr(bytes(4))
    assert t("OpenNewEdition", pub, code(b"MACR"), 0, rp) == fm.noErr
    ref = m.r32(rp)
    assert m.r32(p + ed.srRefNum) == ref
    text = t.ptr(b"Hello, world")
    assert t("WriteEdition", ref, code(b"TEXT"), text, 5) == fm.noErr
    assert t("WriteEdition", ref, code(b"TEXT"), text + 5, 7) == fm.noErr
    mark = t.ptr(bytes(4))
    assert t("GetEditionFormatMark", ref, code(b"TEXT"), mark) == fm.noErr and m.r32(mark) == 12
    assert t("GetEditionFormatMark", ref, code(b"PICT"), mark) == ed.noTypeErr
    picture = bytes(range(20))
    assert t("WriteEdition", ref, code(b"PICT"), t.ptr(picture), 20) == fm.noErr
    assert bytes(node.fork(False)) == b""           # until it's closed
    assert t("CloseEdition", ref, 1) == fm.noErr
    assert m.r32(p + ed.srRefNum) == 0
    assert ed.parse(bytes(node.fork(False))) == [[b"TEXT", b"Hello, world"], [b"PICT", picture]]
    assert (node.type, node.creator) == (b"edtt", b"MACR")
    assert node.mddate == m.r32(p + ed.srMdDate)

    err, sub = new_section(t, spec, ed.stSubscriber, sid=8)
    assert err == fm.noErr
    q = record(t, sub)
    assert m.r32(q + ed.srControlBlock) == m.r32(p + ed.srControlBlock)
    assert m.r32(q + ed.srMdDate) == 0
    ref = open_edition(t, sub)
    size = t.ptr(bytes(4))
    assert t("EditionHasFormat", ref, code(b"TEXT"), size) == fm.noErr and m.r32(size) == 12
    assert t("EditionHasFormat", ref, code(b"snd "), size) == ed.noTypeErr
    assert t("EditionHasFormat", ref, code(b"fmts"), size) == fm.noErr and m.r32(size) == 16
    assert read(t, ref, b"fmts", 16) == (fm.noErr, b"TEXT\0\0\0\x0cPICT\0\0\0\x14")
    assert read(t, ref, b"TEXT", 5) == (fm.noErr, b"Hello")
    assert t("GetEditionFormatMark", ref, code(b"TEXT"), mark) == fm.noErr and m.r32(mark) == 5
    assert read(t, ref, b"TEXT", 32) == (fm.noErr, b", world")     # all there is
    assert read(t, ref, b"TEXT", 32) == (ed.eofErr, b"")
    assert t("SetEditionFormatMark", ref, code(b"TEXT"), 7) == fm.noErr
    assert read(t, ref, b"TEXT", 32) == (fm.noErr, b"world")
    assert read(t, ref, b"PICT", 32) == (fm.noErr, picture)
    assert read(t, ref, b"snd ", 32)[0] == ed.noTypeErr
    assert t("WriteEdition", ref, code(b"TEXT"), text, 5) == fm.rfNumErr
    assert t("CloseEdition", ref, 1) == fm.noErr
    assert m.r32(q + ed.srMdDate) == node.mddate      # it has this edition now

    info = t.ptr(bytes(ed.EDITION_INFO))
    assert t("GetEditionInfo", sub, info) == fm.noErr
    assert m.read(info + ed.eiFdCreator, 8) == b"MACRedtt"
    assert m.r32(info + ed.eiMdDate) == node.mddate
    assert m.r_pstr(info + ed.eiContainer + 6) == b"Edition"


def test_a_subscriber_cannot_write_nor_a_publisher_read(qapp):
    t = app()
    spec, _ = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    _, sub = new_section(t, spec, ed.stSubscriber)
    rp = t.ptr(bytes(4))
    assert t("OpenNewEdition", sub, code(b"MACR"), 0, rp) == fm.wrPermErr
    assert t("OpenEdition", pub, rp) == fm.permErr
    assert t("OpenNewEdition", pub, code(b"MACR"), 0, rp) == fm.noErr
    ref = t.mem.r32(rp)
    assert read(t, ref, b"TEXT", 4)[0] == fm.rfNumErr
    assert t("WriteEdition", ref, code(b"fmts"), t.ptr(bytes(8)), 8) == fm.paramErr
    assert t("CloseEdition", ref, 0) == fm.noErr
    assert t("CloseEdition", ref, 0) == fm.rfNumErr


def test_an_edition_not_written_successfully_is_not_kept(qapp):
    t = app()
    spec, node = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert publish(t, pub, [(b"TEXT", b"First")]) == fm.noErr
    date = node.mddate
    rp = t.ptr(bytes(4))
    assert t("OpenNewEdition", pub, code(b"MACR"), 0, rp) == fm.noErr
    ref = t.mem.r32(rp)
    assert t("WriteEdition", ref, code(b"TEXT"), t.ptr(b"Second"), 6) == fm.noErr
    assert t("CloseEdition", ref, 0) == fm.noErr
    assert ed.parse(bytes(node.fork(False))) == [[b"TEXT", b"First"]]
    assert node.mddate == date


def test_a_subscriber_reading_the_old_edition_is_told_a_new_one_is_written(qapp):
    t = app()
    spec, _ = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert publish(t, pub, [(b"TEXT", b"Old news")]) == fm.noErr
    _, sub = new_section(t, spec, ed.stSubscriber)
    ref = open_edition(t, sub)
    assert read(t, ref, b"TEXT", 3) == (fm.noErr, b"Old")
    rp = t.ptr(bytes(4))
    assert t("OpenNewEdition", pub, code(b"MACR"), 0, rp) == fm.noErr
    new = t.mem.r32(rp)
    assert t("WriteEdition", new, code(b"TEXT"), t.ptr(b"New news"), 8) == fm.noErr
    assert read(t, ref, b"TEXT", 4) == (fm.noErr, b" new")      # the old edition, still
    assert t("CloseEdition", new, 1) == fm.noErr
    assert read(t, ref, b"TEXT", 4)[0] == ed.abortErr
    q = record(t, sub)
    assert t("CloseEdition", ref, 0) == fm.noErr
    assert t.mem.r32(q + ed.srMdDate) == 0


def test_section_events_go_to_the_applications_that_take_them(qapp):
    a = app()
    b = app(sharing=a)
    spec, node = edition(a)
    _, pub = new_section(a, spec, ed.stPublisher, sid=3)
    assert events(a) == []
    _, sub = new_section(b, container(b, "Edition"), ed.stSubscriber)
    _, manual = new_section(b, container(b, "Edition"), ed.stSubscriber, mode=ed.sumManual)
    # the edition is newer than what the automatic subscriber has
    assert events(b) == [(b"sect", b"read", section(sub))]
    ae.state(b).pending.clear()
    assert publish(a, pub, [(b"TEXT", b"News")]) == fm.noErr
    assert events(a) == []
    assert events(b) == [(b"sect", b"read", section(sub))]
    ae.state(b).pending.clear()
    ref = open_edition(b, sub)
    assert read(b, ref, b"TEXT", 10) == (fm.noErr, b"News")
    assert b("CloseEdition", ref, 1) == fm.noErr
    # GoToPublisherSection scrolls the publisher's application to it
    assert b("GoToPublisherSection", container(b, "Edition")) == fm.noErr
    assert events(a) == [(b"sect", b"scrl", section(pub))]
    assert b("UnRegisterSection", manual) == fm.noErr
    # an application that doesn't take high-level events gets none
    c = app(sharing=a, aware=False)
    _, sub2 = new_section(c, container(c, "Edition"), ed.stSubscriber)
    assert c("IsRegisteredSection", sub2) == fm.noErr
    assert publish(a, pub, [(b"TEXT", b"More news")]) == fm.noErr
    assert events(c) == []
    assert events(b) == []                  # it has the edition with this date already
    p = record(a, pub)
    a.mem.w32(p + ed.srMdDate, a.mem.r32(p + ed.srMdDate) + 1)    # the publisher's changed
    assert publish(a, pub, [(b"TEXT", b"Latest news")]) == fm.noErr
    assert events(c) == []
    assert events(b) == [(b"sect", b"read", section(sub))]


def test_a_quitting_applications_sections_are_forgotten(qapp):
    a = app()
    b = app(sharing=a)
    spec, node = edition(a)
    _, pub = new_section(b, container(b, "Edition"), ed.stPublisher)
    assert a("DeleteEditionContainerFile", spec) == fm.fBsyErr
    b.process.events.kill()
    assert a("DeleteEditionContainerFile", spec) == fm.noErr
    assert ed._lookup(a, node.volume.vref, fm.ROOT, "Edition") is None


def test_unregistering_and_registering_again(qapp):
    t = app()
    m = t.mem
    spec, _ = edition(t)
    _, sub = new_section(t, spec, ed.stSubscriber)
    q = record(t, sub)
    ref = open_edition(t, sub)
    assert t("UnRegisterSection", sub) == fm.fBsyErr        # an edition is open
    assert t("CloseEdition", ref, 0) == fm.noErr
    assert t("UnRegisterSection", sub) == fm.noErr
    assert t("IsRegisteredSection", sub) == ed.notRegisteredSectionErr
    assert t("UnRegisterSection", sub) == ed.notRegisteredSectionErr
    assert m.r32(q + ed.srControlBlock) == 0
    updated = t.ptr(b"\xff")
    assert t("RegisterSection", 0, sub, updated) == fm.noErr
    assert m.r8(updated) == 0
    assert t("IsRegisteredSection", sub) == fm.noErr
    assert m.r32(q + ed.srControlBlock) != 0
    assert t("RegisterSection", 0, t.handle(bytes(8)), updated) == ed.badSectionErr


def test_a_publishers_missing_container_is_made_again(qapp):
    t = app()
    spec = container(t, "New Edition")
    err, pub = new_section(t, spec, ed.stPublisher)
    assert err == fm.noErr
    node = t.process.files.lookup(t.system.files.boot.vref, fm.ROOT, "New Edition")
    assert (node.type, node.creator) == (b"edtu", b"TEST")
    assert events(t) == [(b"sect", b"writ", section(pub))]


def test_a_subscribers_missing_container_is_a_warning(qapp):
    t = app()
    err, sub = new_section(t, container(t, "Gone"), ed.stSubscriber)
    assert err == ed.containerNotFoundWrn
    assert t("IsRegisteredSection", sub) == fm.noErr
    assert t.mem.r32(record(t, sub) + ed.srControlBlock) == 0
    assert t("OpenEdition", sub, t.ptr(bytes(4))) == fm.fnfErr
    assert t("GetEditionInfo", sub, t.ptr(bytes(ed.EDITION_INFO))) == fm.fnfErr
    assert new_section(t, container(t, "Gone"), 5)[0] == ed.badSectionErr


def test_a_container_with_a_publisher_cannot_be_deleted(qapp):
    t = app()
    spec, node = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert t("DeleteEditionContainerFile", spec) == fm.fBsyErr
    assert t("UnRegisterSection", pub) == fm.noErr
    assert t("DeleteEditionContainerFile", spec) == fm.noErr
    assert t("DeleteEditionContainerFile", spec) == fm.fnfErr


def test_two_publishers_of_one_edition(qapp):
    t = app()
    spec, _ = edition(t)
    assert new_section(t, spec, ed.stPublisher, sid=1)[0] == fm.noErr
    err, second = new_section(t, spec, ed.stPublisher, sid=2)
    assert err == ed.multiplePublisherWrn
    err, third = new_section(t, container(t, "Edition"), ed.stPublisher, sid=3)
    assert err == ed.multiplePublisherWrn
    rp = t.ptr(bytes(4))
    assert t("OpenNewEdition", second, code(b"MACR"), 0, rp) == fm.noErr
    assert t("OpenNewEdition", third, code(b"MACR"), 0, t.ptr(bytes(4))) == fm.fLckdErr
    assert t("CloseEdition", t.mem.r32(rp), 0) == fm.noErr


def test_the_publisher_that_wrote_an_edition_is_known_by_its_document(qapp):
    t = app()
    files, boot = t.process.files, t.system.files.boot
    doc = files.create(boot.vref, fm.ROOT, "Report")
    doc_spec = t.ptr(bytes(70))
    put_spec(t, doc_spec, boot.vref, fm.ROOT, "Report")
    spec, node = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher, sid=5, document=doc_spec)
    assert publish(t, pub, [(b"TEXT", b"Figures")], document=doc_spec) == fm.noErr
    assert [f for f, _ in ed.parse(bytes(node.fork(False)))] == [b"alis", b"TEXT"]
    assert t("UnRegisterSection", pub) == fm.noErr
    # the same section again is the publisher; another isn't
    assert t("RegisterSection", doc_spec, pub, t.ptr(bytes(1))) == fm.noErr
    assert t("UnRegisterSection", pub) == fm.noErr
    assert new_section(t, spec, ed.stPublisher, sid=6, document=doc_spec)[0] == (
        ed.notThePublisherWrn)

    # GetStandardFormats: the preview, the publisher's alias and the formats
    preview_format = t.ptr(bytes(4))
    preview, alias, formats = t.handle(b""), t.handle(b""), t.handle(b"")
    assert t("GetStandardFormats", spec, preview_format, preview, alias, formats) == fm.noErr
    assert (t.mem.read(preview_format, 4), t.contents(preview)) == (b"TEXT", b"Figures")
    data = t.contents(alias)
    assert struct.unpack(">l", data[-4:])[0] == 5
    assert al.resolve(t.system.files, al.Alias.parse(data[:-4]), node).node is doc
    assert t.contents(formats) == b"alis" + struct.pack(">l", len(data)) + b"TEXT\0\0\0\x07"
    _, plain = edition(t, "Plain")
    _, pub2 = new_section(t, container(t, "Plain"), ed.stPublisher)
    assert publish(t, pub2, [(b"PICT", bytes(12))]) == fm.noErr
    assert t("GetStandardFormats", container(t, "Plain"), preview_format, preview, alias,
             0) == ed.noTypeErr
    assert t.mem.read(preview_format, 4) == b"PICT"


def test_the_last_container_used(qapp):
    t = app()
    spec = t.ptr(bytes(ed.CONTAINER_SPEC))
    assert t("GetLastEditionContainerUsed", spec) == fm.fnfErr
    assert t.mem.r_pstr(spec + 6) == b""
    made, _ = edition(t)
    new_section(t, made, ed.stSubscriber)
    assert t("GetLastEditionContainerUsed", spec) == fm.noErr
    assert t.mem.read(spec, 70) == t.mem.read(made, 70)


def test_an_applications_own_edition_opener_and_io_routine(qapp):
    t = app()
    m = t.mem
    got = t.ptr(bytes(4))
    assert t("GetEditionOpenerProc", got) == fm.noErr
    standard = m.r32(got)
    assert standard & 1                             # the standard one isn't 68k code
    verbs, ios = [], []

    def opener(verb, pb):
        verbs.append(verb)
        err = t("CallEditionOpenerProc", verb, pb, standard)
        if not err and verb in (ed.eoOpen, ed.eoOpenNew):
            io_procs[m.r32(pb + ed.eoIoRefNum)] = m.r32(pb + ed.eoIoProc)
            m.w32(pb + ed.eoIoProc, 0x2100)
        return err

    def io(verb, pb):
        ios.append(verb)
        return t("CallFormatIOProc", verb, pb, io_procs[m.r32(pb + ed.ioRefNum)])
    io_procs = {}
    t.procs[0x2000], t.procs[0x2100] = opener, io
    assert t("SetEditionOpenerProc", 0x2000) == fm.noErr
    assert t("GetEditionOpenerProc", got) == fm.noErr and m.r32(got) == 0x2000

    spec, _ = edition(t)
    _, pub = new_section(t, spec, ed.stPublisher)
    assert publish(t, pub, [(b"TEXT", b"Mine")]) == fm.noErr
    assert verbs == [ed.eoOpenNew, ed.eoCloseNew]
    assert ios == [ed.ioNewFormat, ed.ioWriteFormat]
    _, sub = new_section(t, spec, ed.stSubscriber)
    ref = open_edition(t, sub)
    assert read(t, ref, b"TEXT", 10) == (fm.noErr, b"Mine")
    assert t("CloseEdition", ref, 1) == fm.noErr
    assert verbs[2:] == [ed.eoOpen, ed.eoClose]
    assert ios[2:] == [ed.ioHasFormat, ed.ioReadFormat]
    assert t("CallEditionOpenerProc", ed.eoOpen, t.ptr(bytes(ed.OPENER_PB)), 0) == fm.paramErr

    assert t("SetEditionOpenerProc", 0) == fm.noErr
    assert t("GetEditionOpenerProc", got) == fm.noErr and m.r32(got) == standard


def test_the_standard_opener_says_which_editions_a_subscriber_can_read(qapp):
    t = app()
    m = t.mem
    _, node = edition(t)
    _, pub = new_section(t, container(t, "Edition"), ed.stPublisher)
    assert publish(t, pub, [(b"PICT", bytes(12))]) == fm.noErr
    pb = t.ptr(bytes(ed.OPENER_PB))
    put_spec(t, pb + ed.eoInfo + ed.eiContainer, node.volume.vref, node.parid, node.name)
    for mask, err in ((ed.kPICTformatMask, fm.noErr), (ed.kTEXTformatMask, ed.noTypeErr),
                      (ed.kPICTformatMask | ed.kTEXTformatMask, fm.noErr)):
        m.w8(pb + ed.eoFormatsMask, mask)
        assert t("CallEditionOpenerProc", ed.eoCanSubscribe, pb, ed.STANDARD_OPENER) == err
    other = t.process.files.create(node.volume.vref, fm.ROOT, "Letter")
    other.type = b"TEXT"
    put_spec(t, pb + ed.eoInfo + ed.eiContainer, node.volume.vref, fm.ROOT, "Letter")
    assert t("CallEditionOpenerProc", ed.eoCanSubscribe, pb, ed.STANDARD_OPENER) == ed.noTypeErr


def test_the_dialogs_without_a_display_are_cancelled(qapp):
    t = app()
    reply = t.ptr(bytes(122))
    assert t("NewPublisherDialog", reply) == fm.noErr
    assert t.mem.r8(reply + ed.npCanceled) == 1
    t.mem.w8(reply + ed.npUsePart, 1)
    assert t("NewPublisherDialog", reply) == ed.badSubPartErr
    reply = t.ptr(bytes(112))
    assert t("NewSubscriberDialog", reply) == fm.noErr
    assert t.mem.r8(reply + ed.nsCanceled) == 1
    spec, _ = edition(t)
    _, sub = new_section(t, spec, ed.stSubscriber)
    reply = t.ptr(bytes(10))
    t.mem.w32(reply + ed.soSectionH, sub)
    assert t("SectionOptionsDialog", reply) == fm.noErr
    assert (t.mem.r8(reply + ed.soCanceled), t.mem.read(reply + ed.soAction, 4)) == (1, b"    ")


# =========================================================================
# The dialogs, with the display up
# =========================================================================
PACK11 = 0xA82D


def _options(h):
    h.wait_until(lambda: h.d.edition_dialogs and h.d.edition_dialogs[-1].isVisible(),
                 timeout=5, what="the options dialog")
    return h.d.edition_dialogs[-1]


def test_publishing_from_the_new_publisher_dialog(harness, tmp_path):
    reply, options = BUF(0), BUF(3)             # a NewPublisherReply; a SectionOptionsReply
    a = Asm()
    a.lea_pc("text", 0)                         # the preview: PtrToHand(text, 12)
    a.w(0x700C)                                 # MOVEQ #12,D0
    a.w(0xA9E3)
    a.store_a(0, reply + ed.npPreview)
    a.w(0x2B7C)                                 # MOVE.L #'TEXT',previewFormat
    a.long(ostype(b"TEXT"))
    a.w(reply + ed.npPreviewFormat)
    a.result()                                  # NewPublisherDialog(reply)
    a.pea(reply)
    a.call(PACK11, d0=0x0236)
    a.pop_w(R(0))
    a.mark(DONE, 1)
    a.result()                                  # CreateEditionContainerFile(container, 'MACR', 0)
    a.pea(reply + ed.npContainer)
    a.push_l(ostype(b"MACR"))
    a.push_w(0)
    a.call(PACK11, d0=0x050E)
    a.pop_w(R(1))
    # NewSection(container, nil, stPublisher, 1, pumOnSave, sectionH)
    a.result()
    a.pea(reply + ed.npContainer)
    a.push_l(0)
    a.push_w(ed.stPublisher << 8)
    a.push_l(1)
    a.push_w(ed.sumAutomatic)
    a.pea(LONG)
    a.call(PACK11, d0=0x0A02)
    a.pop_w(R(2))
    a.copy_l(LONG, options + ed.soSectionH)     # SectionOptionsDialog(reply)
    a.result()
    a.pea(options)
    a.call(PACK11, d0=0x023A)
    a.pop_w(R(3))
    a.mark(DONE, 2)
    _idle(a)
    a.label("text")
    a.code += b"Hello, world"
    app = host_app(tmp_path, a)
    h = harness()
    proc, mem, a5 = _launch(h, app)

    dlg = _dialog(h)
    assert dlg.put and dlg.prompt.text() == "Name of new edition:"
    assert dlg.ok.text() == "Publish"
    assert not dlg.preview.pixmap().isNull()
    dlg.save_as("News Edition")
    h.wait_until(lambda: mem.r16(a5 + DONE) == 1, what="the publisher's reply")
    r = a5 + reply
    assert (mem.r16s(a5 + R(0)), mem.r8(r + ed.npCanceled), mem.r8(r + ed.npReplacing)) == (
        0, 0, 0)
    assert mem.r_pstr(r + ed.npContainer + 6) == b"News Edition"

    opts = _options(h)
    node = proc.files.lookup(0, 0, "News Edition")
    assert (node.type, node.creator) == (b"edtu", b"MACR")
    assert (mem.r16s(a5 + R(1)), mem.r16s(a5 + R(2))) == (0, 0)
    assert opts.edition.text() == "Publisher to: “News Edition”"
    assert opts.automatic.text() == "On Save" and opts.automatic.isChecked()
    assert opts.open_publisher.isHidden()
    opts.choose_mode(True)
    h.wait_until(lambda: opts._future is not None, what="the dialog to wait again")
    assert opts.manual.isChecked()
    opts.press("now")
    h.wait_until(lambda: mem.r16(a5 + DONE) == 2, what="the options reply")
    o = a5 + options
    assert (mem.r8(o + ed.soCanceled), mem.r8(o + ed.soChanged)) == (0, 1)
    assert mem.read(o + ed.soAction, 4) == b"writ"
    sec = mem.r32(a5 + LONG)
    assert mem.r16(proc.system.heap_of(sec).deref(sec) + ed.srMode) == ed.sumManual
    h.wait_until(lambda: not h.d.edition_dialogs, what="the dialog to go")
    assert proc.runner.unimplemented_calls == {}


def test_the_new_subscriber_dialog_lists_the_editions_it_can_read(harness, tmp_path):
    for name, ftype, formats in (("Weather", b"edtt", [[b"TEXT", b"Sunny"]]),
                                 ("Chart", b"edtp", [[b"PICT", bytes(12)]])):
        (tmp_path / name).write_bytes(ed.pack(formats))
        info = ftype + b"MACR" + bytes(24)
        (tmp_path / f"._{name}").write_bytes(fm._apple_double_bytes({9: info}))
    (tmp_path / "Letter").write_bytes(b"Dear Mac,")
    (tmp_path / "._Letter").write_bytes(fm._apple_double_bytes({9: b"TEXTttxt" + bytes(24)}))
    (tmp_path / "Folder").mkdir()
    reply = BUF(0)
    a = Asm()
    a.w(0x1B7C, ed.kTEXTformatMask, reply + ed.nsFormatsMask)    # MOVE.B #mask,d16(A5)
    a.result()                                  # NewSubscriberDialog(reply)
    a.pea(reply)
    a.call(PACK11, d0=0x0232)
    a.pop_w(R(0))
    a.mark(DONE, 1)
    _idle(a)
    app = host_app(tmp_path, a)
    h = harness()
    proc, mem, a5 = _launch(h, app)

    dlg = _dialog(h)
    assert not dlg.put and dlg.ok.text() == "Subscribe"
    assert dlg.names() == ["Folder", "Weather"]     # editions with TEXT, and folders
    assert dlg.preview.isHidden()
    dlg.choose("Weather")
    h.wait_until(lambda: mem.r16(a5 + DONE) == 1, what="the subscriber's reply")
    r = a5 + reply
    weather = proc.files.lookup(0, 0, "Weather")
    assert (mem.r16s(a5 + R(0)), mem.r8(r + ed.nsCanceled)) == (0, 0)
    assert (mem.r16s(r + ed.nsContainer), mem.r32(r + ed.nsContainer + 2)) == (
        weather.volume.vref, weather.parid)
    assert mem.r_pstr(r + ed.nsContainer + 6) == b"Weather"
    assert proc.runner.unimplemented_calls == {}


def test_an_expanded_options_dialogs_hook_sees_each_step(harness, tmp_path):
    reply, spec, log = BUF(0), BUF(1), BUF(4)
    a = Asm()
    a.w(0x2B7C)                                 # the container: "Gone", which isn't there
    a.long(0x04476F6E)
    a.w(spec + 6)
    a.w(0x1B7C, ord("e"), spec + 10)
    a.result()                                  # NewSection(spec, nil, stSubscriber, 1,
    a.pea(spec)                                 # sumManual, sectionH)
    a.push_l(0)
    a.push_w(ed.stSubscriber << 8)
    a.push_l(1)
    a.push_w(ed.sumManual)
    a.pea(LONG)
    a.call(PACK11, d0=0x0A02)
    a.pop_w(R(0))
    a.copy_l(LONG, reply + ed.soSectionH)
    a.result()                                  # SectionOptionsExpDialog(reply, where, 0,
    a.pea(reply)                                # hook, nil, log)
    a.push_l(0x00500050)
    a.push_w(0)
    a.lea_pc("hook", 0)
    a.push_a(0)
    a.push_l(0)
    a.pea(log)
    a.call(PACK11, d0=0x0B3C)
    a.pop_w(R(1))
    a.mark(DONE, 1)
    _idle(a)
    a.label("hook")                             # (itemOffset, item, dialog, data): item
    a.w(0x206F, 4)                              # MOVEA.L 4(SP),A0: the log
    a.w(0x30AF, 14)                             # MOVE.W 14(SP),(A0): the offset
    a.w(0x3028, 2)                              # MOVE.W 2(A0),D0: items so far
    a.w(0x5268, 2)                              # ADDQ.W #1,2(A0)
    a.w(0xD040)                                 # ADD.W D0,D0
    a.w(0x31AF, 12, 0x0004)                     # MOVE.W 12(SP),4(A0,D0.W)
    a.w(0x3F6F, 12, 16)                         # MOVE.W 12(SP),16(SP)
    a.w(0x225F)                                 # MOVEA.L (SP)+,A1
    a.w(0x4FEF, 12)                             # LEA 12(SP),SP
    a.w(0x4ED1)                                 # JMP (A1)
    app = host_app(tmp_path, a)
    h = harness()
    proc, mem, a5 = _launch(h, app)

    opts = _options(h)
    assert mem.r16s(a5 + R(0)) == ed.containerNotFoundWrn
    assert opts.edition.text() == "Subscriber to: “Gone”"
    assert opts.latest.text() == "Latest Edition: None"
    assert opts.automatic.text() == "Automatically" and opts.manual.isChecked()
    assert not opts.open_publisher.isHidden()
    opts.choose_mode(False)
    h.wait_until(lambda: opts._future is not None, what="the dialog to wait again")
    assert opts.automatic.isChecked()
    opts.press("goto")
    h.wait_until(lambda: mem.r16(a5 + DONE) == 1, what="the options reply")
    o = a5 + reply
    assert mem.r16s(a5 + R(1)) == fm.noErr
    assert (mem.r8(o + ed.soCanceled), mem.r8(o + ed.soChanged)) == (0, 1)
    assert mem.read(o + ed.soAction, 4) == b"goto"
    n = mem.r16(a5 + log + 2)
    assert mem.r16s(a5 + log) == 2                  # OK and Cancel
    assert [mem.r16s(a5 + log + 4 + 2 * i) for i in range(n)] == [
        -1, ed.emHookAutoUpdateMode, ed.emHookGoToPublisher, -2]
    sec = mem.r32(a5 + LONG)
    assert mem.r16(proc.system.heap_of(sec).deref(sec) + ed.srMode) == ed.sumAutomatic
    h.wait_until(lambda: not h.d.edition_dialogs, what="the dialog to go")
    assert proc.runner.unimplemented_calls == {}

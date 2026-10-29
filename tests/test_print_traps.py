"""The Printing Manager's traps as a program calls them: its small calls,
print records it has to fix or can't use, what goes wrong while printing,
the .Print driver's control calls, printing the screen, and the Page
Setup and Print dialogs (Inside Macintosh II, the Printing Manager)."""

import struct
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from guest import Guest
from test_printing import answer, black, page, pdf_pages, start
from test_desk import byte, window
from test_dialogs import NoDisplay

from macrt.m68k import glue_print
from macrt.toolbox import lowmem
from macrt.toolbox import printing as pr
from macrt.toolbox.events import ProcessKilled
from macrt.toolbox.quickdraw import GrafPort
from macrt.toolbox.types import Rect
from macrt.toolbox.windows import WindowRecord
from macrt.ui import printdlg

ROW_BYTES, ROWS = 4, 8


def job_of(g, h) -> tuple[int, int, int]:
    """A record's first and last pages and copies."""
    return struct.unpack_from(">hhh", g.contents(h), pr.prJob)


def put(g, h, rec: bytes) -> None:
    g.mem.write(g.heap.deref(h), rec)


# =========================================================================
# The small calls
# =========================================================================
def test_the_printing_managers_small_calls(qapp):
    g = Guest()
    g("PrOpen")
    g("PrSetError", pr.iPrAbort)
    assert g("PrError") == pr.iPrAbort
    g("PrClose")
    assert g("PrError") == 0
    g("PrSetError", pr.iPrAbort)
    g("PrDrvrOpen")
    assert g("PrError") == 0
    assert g("PrDrvrVers") == pr.DRIVER_VERSION
    dce = g("PrDrvrDCE")
    assert g("PrDrvrDCE") == dce                       # made the first time only
    assert g.mem.r16s(g.heap.deref(dce) + glue_print.dCtlRefNum) == pr.PRINT_DRIVER
    param = g.ptr(bytes(4))
    assert glue_print.driver_status(g, 1, param) and g.mem.r32(param) == dce
    assert not glue_print.driver_status(g, 2, param)
    h = g.heap.new_handle(pr.PRINT_SIZE)
    assert g("PrStlInit", h) == g("PrJobInit", h) == 0  # the dialogs are the host's
    data = g.ptr(bytes(16))
    g("PrGeneral", data)
    assert g.mem.r16(data + 2) == pr.opNotImpl
    status = g.ptr(b"\xFF" * pr.STATUS_SIZE)
    g("PrSetError", pr.iPrAbort)
    g("PrPicFile", h, 0, 0, 0, status)
    assert g.mem.read(status, pr.STATUS_SIZE) == bytes(pr.STATUS_SIZE)
    assert g("PrError") == 0
    g.mem.write(0, b"\xA5" * pr.STATUS_SIZE)
    g("PrPicFile", h, 0, 0, 0, 0)                     # no status record to fill in
    assert g.mem.read(0, pr.STATUS_SIZE) == b"\xA5" * pr.STATUS_SIZE


# =========================================================================
# Print records
# =========================================================================
def test_records_that_need_fixing_or_cant_be_used(qapp):
    g = Guest()
    small = g.heap.new_handle(20)
    g("PrintDefault", small)                        # grown to hold a record
    assert g.contents(small) == pr.default_record()
    h = g.heap.new_handle(pr.PRINT_SIZE)
    rec = bytearray(pr.default_record())
    struct.pack_into(">hhh", rec, pr.prJob, 2, 3, 4)
    # Another printer's version or device, and paper that isn't one of
    # macrt's: made a default record, the job with it.
    for fmt, at, *values in ((">h", pr.iPrVersion, 1), (">H", pr.prStl, 0x0301),
                             (">4h", pr.rPaper, 0, 0, 100, 100)):
        bad = bytearray(rec)
        struct.pack_into(fmt, bad, at, *values)
        put(g, h, bytes(bad))
        assert g("PrValidate", h)
        assert g.contents(h) == pr.default_record()
    # A purged record has nothing to read and nowhere to write.
    gone = g.heap.new_empty_handle()
    assert g("PrValidate", gone) and g.heap.is_empty(gone)
    # Nor has NIL, whatever address 0 holds.
    block = g.ptr(bytes(pr.PRINT_SIZE))
    g.mem.w32(0, block)
    g("PrintDefault", 0)
    assert g("PrValidate", 0) and g.mem.read(block, pr.PRINT_SIZE) == bytes(pr.PRINT_SIZE)


def test_merging_a_job_into_another_record(qapp):
    g = Guest()
    src, dst = g.heap.new_handle(pr.PRINT_SIZE), g.heap.new_handle(pr.PRINT_SIZE)
    rec = bytearray(pr.default_record())
    struct.pack_into(">hhh", rec, pr.prJob, 2, 3, 4)
    put(g, src, bytes(rec))
    wide = pr.Setup(pr.PAPERS[2], wide=True)
    put(g, dst, pr.default_record(wide))
    g("PrJobMerge", src, dst)
    assert pr.setup_of(g.contents(dst)) == wide and job_of(g, dst) == (2, 3, 4)
    small = g.heap.new_handle(20)                   # too small to have a job
    g.mem.write(g.heap.deref(small), b"\x00\x09" * 10)
    g("PrJobMerge", small, dst)
    assert pr.setup_of(g.contents(dst)) == wide and job_of(g, dst) == (2, 3, 4)
    g("PrJobMerge", 0, dst)                         # NIL has no job, nor low memory
    assert pr.setup_of(g.contents(dst)) == wide and job_of(g, dst) == (2, 3, 4)


def test_print_dialog_main_asks_with_the_print_dialog(qapp, tmp_path, monkeypatch):
    path = tmp_path / "Main.pdf"
    answer(monkeypatch, ("ok", 4, 5, 3, path))
    g = Guest()
    h = g.heap.new_handle(pr.PRINT_SIZE)
    g("PrintDefault", h)
    assert g("PrDlgMain", h, 0)
    assert job_of(g, h) == (4, 5, 3) and glue_print._state(g).path == path


# =========================================================================
# Printing a document
# =========================================================================
def test_a_pdf_is_named_for_the_front_visible_window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = Guest(desk_top=20)
    for title, visible in (("Memo: Q3", True), ("", True), ("Hidden", False)):
        w = WindowRecord.new(g.system, g.process, g.heap, 0, Rect(60, 40, 200, 300), title,
                             visible, 0, False, 0)
        w.next_window = g.process.windows.head
        g.process.windows.head = w.addr
    h = g.heap.new_handle(pr.PRINT_SIZE)
    g("PrintDefault", h)
    port = g("PrOpenDoc", h, 0, 0)                  # with no Print dialog first
    page(g, port)
    g("PrCloseDoc", port)
    assert pdf_pages(tmp_path / "Memo- Q3.pdf") == [(612, 792)]


def test_what_goes_wrong_while_printing(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = Guest()
    g("PrOpenPage", 0, 0)                           # no document
    assert g("PrError") == pr.iPrAbort
    g("PrClosePage", 0)
    h = g.heap.new_handle(pr.PRINT_SIZE)
    g("PrintDefault", h)
    first = g("PrOpenDoc", h, 0, 0)
    assert g.mem.r8(first + pr.fOurPtr)
    storage = g.ptr(bytes(pr.PRPORT_SIZE))
    port = g("PrOpenDoc", h, storage, 0)            # the first one's port is closed
    assert port == storage and not g.mem.r8(port + pr.fOurPtr)
    assert g.system.port_at(first) is None and not g.heap.is_ptr(first)
    g("PrOpenPage", first, 0)
    assert g("PrError") == pr.iPrAbort
    other = g.mem.r32(lowmem.WMgrPort)              # a port, but not the printing one
    assert g.system.port_at(other) is not None
    g("PrSetError", 0)
    g("PrOpenPage", other, 0)
    assert g("PrError") == pr.iPrAbort
    heap = g.process.heap
    with monkeypatch.context() as m:
        new_handle = heap.new_handle
        m.setattr(heap, "new_handle",
                  lambda size, clear=False: 0 if size == 10 else new_handle(size, clear))
        g("PrOpenPage", port, 0)                    # no room for its picture
        assert g("PrError") == pr.iMemFullErr
    g("FrameRect", g.rect_ptr((10, 10, 100, 200)))
    g("PrClosePage", port)                          # and so no page
    assert glue_print._state(g).job.pages == []
    page(g, port)
    g.mem.write(0, b"\xA5" * GrafPort.SIZE)
    frame = g.rect_ptr((10, 10, 100, 200))
    with monkeypatch.context() as m:
        m.setattr(heap, "new_ptr", lambda size, clear=False: 0)
        g("PrOpenPage", port, 0)
        g("FrameRect", frame)
        g("PrClosePage", port)                      # no room to draw it in: a blank page
        assert g("PrOpenDoc", h, 0, 0) == 0 and g("PrError") == pr.iMemFullErr
    assert g.mem.read(0, GrafPort.SIZE) == b"\xA5" * GrafPort.SIZE    # not drawn at 0
    pages = glue_print._state(g).job.pages
    assert len(pages) == 2 and black(pages[0], 28, 86) and not black(pages[1], 28, 86)
    storage, port = port, g("PrOpenDoc", h, storage, 0)
    g("PrCloseDoc", port)                           # nothing printed: no PDF
    assert g("PrError") == 0 and list(tmp_path.iterdir()) == []
    assert g.heap.is_ptr(storage)                   # the program's, not ours to dispose of
    # Ended with another port, the document leaves its own open, but no
    # page starts on it.
    port = g("PrOpenDoc", h, 0, 0)
    g("PrCloseDoc", 0)
    assert g.system.port_at(port) is not None
    g("PrOpenPage", port, 0)
    assert g("PrError") == pr.iPrAbort


def test_a_pdf_that_cant_be_written(qapp, tmp_path, monkeypatch):
    answer(monkeypatch, ("ok", 0, 0, 1, tmp_path / "Gone" / "Doc.pdf"))
    g = Guest()
    h, port = start(g)
    page(g, port)
    g("PrCloseDoc", port)
    assert g("PrError") == pr.iPrSavPFil and glue_print._state(g).printed == []


# =========================================================================
# The driver's control calls
# =========================================================================
def _bitmap(g, base=None) -> int:
    """Four black rows, then four white."""
    if base is None:
        base = g.ptr(b"\xFF" * ROW_BYTES * 4 + bytes(ROW_BYTES * 4))
    return g.ptr(struct.pack(">IH4h", base, ROW_BYTES, 0, 0, ROWS, 32))


def test_line_feeds_and_bitmaps_down_the_page(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = Guest()
    st = glue_print._state(g)
    bm, r = _bitmap(g), g.rect_ptr((0, 0, ROWS, 32))

    def ctl(which, p1, p2=0, p3=0):
        g("PrSetError", pr.iPrAbort)
        g("PrCtlCall", which, p1, p2, p3)
        assert g("PrError") == 0

    ctl(glue_print.iPrBitsCtl, bm, g.rect_ptr((0, 0, 0, 32)))    # nothing to print
    ctl(glue_print.iPrBitsCtl, _bitmap(g, base=0), r)            # no pixels to print
    assert st.raw is None                               # and so no page
    ctl(glue_print.iPrBitsCtl, bm, r)
    ctl(glue_print.iPrDevCtl, 0x0003FFFF)               # a sixth of an inch a line
    ctl(glue_print.iPrDevCtl, glue_print.lPrLineFeed | 59)
    assert st.raw_v == ROWS + 59 * 12
    first = st.raw_page
    ctl(glue_print.iPrBitsCtl, bm, r)                   # which won't fit: a new page
    assert st.raw_page is not first and st.raw_v == ROWS
    ctl(glue_print.iPrDevCtl, glue_print.lPrLineFeed)   # no count is one line
    ctl(glue_print.iPrDevCtl, 0x0003FFFE)               # an eighth of an inch
    ctl(glue_print.iPrDevCtl, glue_print.lPrLineFeed | 2)
    assert st.raw_v == ROWS + 12 + 2 * 9
    ctl(glue_print.iPrBitsCtl, bm, r)
    img = st.raw_page
    assert black(img, 18, 36) and black(img, 18, 36 + 30 + 8) and black(img, 18, 36 + 30 + 11)
    assert not black(img, 18, 36 + 8) and not black(img, 18, 36 + 30 + 4)
    ctl(glue_print.iPrDevCtl, glue_print.lPrReset)      # the end of the job, page and all
    assert st.raw is None and pdf_pages(tmp_path / "Test App.pdf") == [(612, 792)] * 2
    g("PrDrvrClose")                                    # with nothing left to print
    assert st.printed == [tmp_path / "Test App.pdf"]
    # A bitmap taller than the page, on a page of its own, is printed on
    # it as far as it goes; closing the driver ends the job.
    tall = g.ptr(struct.pack(">IH4h", g.ptr(bytes(ROW_BYTES * 730)), ROW_BYTES, 0, 0, 730, 32))
    ctl(glue_print.iPrBitsCtl, tall, g.rect_ptr((0, 0, 730, 32)))
    assert st.raw_v == 730
    g("PrDrvrClose")
    assert pdf_pages(tmp_path / "Test App 2.pdf") == [(612, 792)]


def test_printing_the_screen_or_the_front_window(qapp, monkeypatch):
    """Command-Shift-4's two: the whole screen, or the front window's
    content, each a page of its own, a pixel a point at the margins."""
    jobs = []
    monkeypatch.setattr(glue_print, "_write", lambda t, st, job: jobs.append(job))
    g = Guest(desk_top=20)
    g.tb.qd.repaint = lambda port: None             # no host windows to show it
    w = window(g, Rect(100, 100, 200, 300))         # black
    screen = g.system.screen_bits.bounds

    def printed(which, r: Rect) -> bool:
        """Whether the page printed shows r of the screen, as far as the
        page goes."""
        g("PrCtlCall", glue_print.iPrEvtCtl, which, 0, 0)
        img = jobs[-1].pages[0]
        right = min(r.right, r.left + pr.Setup().page.width)
        return all(black(img, 18 + h - r.left, 36 + v - r.top)
                   == bool(byte(g, h, v) >> (7 - h % 8) & 1)
                   for v in range(r.top, r.bottom, 7) for h in range(r.left, right, 5))

    assert printed(glue_print.lPrEvtAll, screen)
    assert printed(glue_print.lPrEvtTop, w.content)
    assert black(jobs[-1].pages[0], 18 + 199, 36 + 99)
    assert not black(jobs[-1].pages[0], 18 + 200, 36 + 50)      # the page past it
    w.visible = False
    g.system.screen.moved()
    assert printed(glue_print.lPrEvtTop, screen)                # with no window, the screen
    assert [len(job.pages) for job in jobs] == [1, 1, 1]


# =========================================================================
# The dialogs
# =========================================================================
class Host(NoDisplay):
    """A display whose user answers a printing dialog as soon as it's up."""
    host_window = None

    def __init__(self, user):
        self.user = user
        self.print_dialogs = []
        self.shown = []
        self.bridge = SimpleNamespace(call=self.call, post=lambda fn, *args: fn(*args),
                                      closed=False)

    def call(self, fn, *args, serve=None, killed=None):
        got = fn(*args)
        if fn in (printdlg.open_setup, printdlg.open_print):
            self.shown.append(got[0])
            self.user(got[0])
        return got


def _asking(g, user) -> Host:
    g.yielding = nullcontext
    g.tb._d = Host(user)
    return g.tb._d


def test_page_setup_and_print_as_the_user_answers_them(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    g = Guest()
    h = g.heap.new_handle(pr.PRINT_SIZE)
    g("PrintDefault", h)
    assert not g("PrStlDialog", h)                  # with no display, no dialog

    def wide_a4(dlg):
        assert dlg.windowTitle() == "Test App" and dlg.isVisible() and d.print_dialogs == [dlg]
        dlg.paper.setCurrentIndex(2)
        dlg.wide.setChecked(True)
        dlg.ok.click()
    d = _asking(g, wide_a4)
    assert g("PrStlDialog", h)
    assert pr.setup_of(g.contents(h)) == pr.Setup(pr.PAPERS[2], wide=True)
    assert d.print_dialogs == [] and not d.shown[0].isVisible()

    out = tmp_path / "Out.pdf"

    def some_pages(dlg):
        assert dlg.path.text() == str(tmp_path / "Test App.pdf")
        dlg.path.setText(str(out))
        dlg.first.setValue(3)                       # which chooses some pages
        dlg.last.setValue(2)
        dlg.copies.setValue(2)
        dlg.ok.click()
    d.user = some_pages
    assert g("PrJobDialog", h)
    assert job_of(g, h) == (2, 3, 2) and glue_print._state(g).path == out

    def cancel(dlg):
        if isinstance(dlg, printdlg.PageSetupDialog):   # it shows the record's setup
            assert dlg.setup() == pr.Setup(pr.PAPERS[2], wide=True)
        dlg.cancel_button.click()
    d.user = cancel
    assert not g("PrJobDialog", h) and not g("PrStlDialog", h)
    assert job_of(g, h) == (2, 3, 2) and d.print_dialogs == []


def test_a_dialog_up_when_the_application_is_stopped(qapp):
    g = Guest()
    h = g.heap.new_handle(pr.PRINT_SIZE)
    g("PrintDefault", h)
    d = _asking(g, lambda dlg: setattr(d.bridge, "closed", True))     # macrt quits
    with pytest.raises(ProcessKilled):
        g("PrJobDialog", h)
    d.bridge.closed = False
    d.user = lambda dlg: g.process.events.kill()        # or the application is stopped
    with pytest.raises(ProcessKilled):
        g("PrStlDialog", h)
    assert d.print_dialogs == [] and len(d.shown) == 2
    assert g.contents(h) == pr.default_record()


def test_the_print_dialog_waits_for_somewhere_to_print(qapp, tmp_path, monkeypatch):
    dlg = printdlg.PrintDialog(None, tmp_path / "Doc.pdf")
    assert dlg.windowTitle() == "Print" and dlg.ok.text() == "Print"
    (fut,) = dlg.future()
    dlg.path.setText("  ")
    dlg.ok.click()
    assert not fut.done()
    chosen = []
    monkeypatch.setattr(printdlg, "QFileDialog",
                        SimpleNamespace(getSaveFileName=lambda *args: chosen.pop(0)))
    chosen.append(("", ""))                         # cancelled
    dlg.choose.click()
    assert dlg.path.text() == "  "
    chosen.append(("~/Chosen.pdf", "PDF (*.pdf)"))
    dlg.choose.click()
    dlg.copies.setValue(3)
    dlg.ok.click()
    assert fut.result(1) == ("ok", 0, 0, 3, Path.home() / "Chosen.pdf")   # all the pages
    dlg.cancel()                                    # once answered, it stays answered
    assert fut.result(1)[0] == "ok"
    dlg.finish()


def test_page_setup_closed_or_escaped_is_cancelled(qapp):
    odd = pr.Setup(pr.Paper("Tabloid", 792, 1224))
    for close in (printdlg.PageSetupDialog.reject, printdlg.PageSetupDialog.close):
        dlg = printdlg.PageSetupDialog(None, odd)
        assert dlg.windowTitle() == "Page Setup" and dlg.setup() == pr.Setup()
        dlg.show()
        (fut,) = dlg.future()
        close(dlg)
        assert fut.result(1) == ("cancel",) and dlg.isVisible()
        dlg.finish()
    with pytest.raises(NotImplementedError):
        printdlg._Dialog(None, "Neither").accept_choice()

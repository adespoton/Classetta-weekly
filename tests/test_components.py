"""The Component Manager: components registered, found, opened, called and
closed, from 68k code as an application calls it (Inside Macintosh: More
Macintosh Toolbox, the Component Manager)."""

import struct

from guest import Processor

from macrt.m68k import dispatch, glue_components as cm, runtime
from macrt.resfork import Resource

TRAP = b"\xa8\x2a"

# pascal ComponentResult main(ComponentParameters *params, Handle storage):
# each request's what is logged at the cursor the long at offset 2 points
# at; request 1 answers its parameter plus the storage, 2 its A5, the
# version request $20001, the others 0, and anything else
# badComponentSelector.
COMPONENT = bytes.fromhex(
    "6004 00000000"
    "206F0008 30280002 227AFFF2 2451 34C0 228A"     # log params->what
    "0C400001 671C 0C400002 6720 0C40FFFC 671E"
    "4A40 6B08 223C80008002 6018 7200 6014"
    "22280004 D2AF0004 600A"                        # 1: the parameter plus the storage
    "220D 6006"                                     # 2: A5
    "223C00020001"                                  # the version
    "2F41000C 205F 508F 4ED0")
LOG = 2

# A fast-dispatch component, D0 the request and A0 where its storage is:
# request 1 answers its long parameter plus the storage.
FAST = bytes.fromhex(
    "4A40 6B12 0C400001 6614"
    "225F 221F D290 588F 2E81 4ED1"
    "225F 508F 4297 4ED1"                           # open and close: 0
    "225F 588F 2EBC80008002 4ED1")

# pascal long f(long storage, long a, long b): storage + a - b; and
# pascal long g(long a, long b): a - b
WITH_STORAGE = bytes.fromhex("205F 221F 201F 9081 D09F 2E80 4ED0")
WITHOUT = bytes.fromhex("205F 221F 201F 9081 2E80 4ED0")


def ostype(s: bytes) -> int:
    return struct.unpack(">I", s)[0]


TYPE, OTHER = ostype(b"test"), ostype(b"othr")


class Runner(Processor):
    """A Processor whose calls to 68k code run it, nested, as the
    runtime's do."""

    call = runtime.Runner.call
    call_for = runtime.Runner.call_for

    def __init__(self, resources=(), **system):
        super().__init__(resources, **system)
        self.stack_top = self.ptr(bytes(0x1000)) + 0x1000
        self.cpu.sp = self.stack_top
        self.stop = self.ptr(bytes(4))
        self.log_at = self.ptr(bytes(0x100))
        self.mem.w32(self.log_at, self.log_at + 4)

    def _jsr(self, addr):
        cpu = self.cpu
        pc = cpu.pc
        cpu.push32(self.stop)
        cpu.pc = addr
        while (ev := cpu.run(self.stop)).kind == "trap":
            auto_pop = dispatch.is_toolbox(ev.code) and ev.code & 0x400
            cpu.pc = cpu.pop32() if auto_pop else ev.pc + 2
            dispatch.dispatch(self, ev.code, ev.pc)
        assert ev.kind == "until", ev
        cpu.pc = pc

    def log(self) -> list[int]:
        """The requests the components logged, and the log emptied."""
        end = self.mem.r32(self.log_at)
        whats = [self.mem.r16s(p) for p in range(self.log_at + 4, end, 2)]
        self.mem.w32(self.log_at, self.log_at + 4)
        return whats

    def code(self, code: bytes = COMPONENT) -> int:
        p = self.ptr(code)
        if code is COMPONENT:
            self.mem.w32(p + LOG, self.log_at)
        return p

    def cm(self, selector: int, *args, result: str = "L") -> int:
        """A Component Manager routine called as its glue calls it."""
        cpu = self.cpu
        sp = cpu.sp
        size = dispatch.SIZES[result] if result else 0
        cpu.sp -= size
        for code, value in args:
            (cpu.push32 if dispatch.SIZES[code] == 4 else cpu.push16)(value & 0xFFFFFFFF)
        cpu.set_d(0, selector)
        self.run(TRAP)
        assert cpu.sp == sp - size
        read = {"L": self.mem.r32, "l": self.mem.r32s}.get(result, self.mem.r16s)
        value = read(cpu.sp) if size else 0
        cpu.sp = sp
        return value

    def call_instance(self, ci: int, what: int, *params: int) -> int:
        """A call made with ComponentCallNow's glue: the result, the
        instance and the parameters, then the flags, their size and what."""
        cpu = self.cpu
        sp = cpu.sp
        cpu.sp -= 4
        cpu.push32(ci)
        for value in params:
            cpu.push32(value & 0xFFFFFFFF)
        cpu.push16(what & 0xFFFF)
        cpu.push16(4 * len(params))
        cpu.set_d(0, 0)
        self.run(TRAP)
        assert cpu.sp == sp - 4
        value = self.mem.r32(cpu.sp)
        cpu.sp = sp
        return value

    def description(self, kind=TYPE, sub=0, maker=0, flags=0, mask=0) -> int:
        return self.ptr(cm.DESC.pack(kind, sub, maker, flags, mask))

    def register(self, entry: int, kind=TYPE, sub=0, flags=0, global_flags=0,
                 name: bytes = b"") -> int:
        name_h = self.handle(name) if name else 0
        return self.cm(0x01, ("p", self.description(kind, sub, ostype(b"mrtx"), flags)),
                       ("p", entry), ("h", global_flags), ("L", name_h), ("L", 0), ("L", 0))

    def find(self, after: int = 0, **looking) -> int:
        return self.cm(0x04, ("L", after), ("p", self.description(**looking)))

    def count(self, **looking) -> int:
        return self.cm(0x03, ("p", self.description(**looking)), result="l")

    def open(self, comp: int) -> int:
        return self.cm(0x07, ("L", comp))

    def close(self, ci: int) -> int:
        return self.cm(0x08, ("L", ci), result="e")


def test_registered_components_are_found_counted_and_described(qapp):
    g = Runner()
    code = g.code()
    first = g.register(code, sub=ostype(b"one "), name=b"\x03One")
    second = g.register(code, sub=ostype(b"two "))
    g.register(code, kind=OTHER)
    assert first and second and first != second
    assert g.count() == 2 and g.count(kind=0) == 3 and g.count(sub=ostype(b"two ")) == 1
    assert g.find() == first and g.find(first) == second and g.find(second) == 0
    assert g.find(sub=ostype(b"two ")) == second
    cd, name = g.ptr(bytes(20)), g.handle(b"")
    assert g.cm(0x05, ("L", first), ("p", cd), ("L", name), ("L", 0), ("L", 0), result="e") == 0
    assert cm.DESC.unpack(g.mem.read(cd, 20))[:3] == (TYPE, ostype(b"one "), ostype(b"mrtx"))
    assert g.contents(name) == b"\x03One"
    assert g.cm(0x05, ("L", 0x1234), ("p", cd), ("L", 0), ("L", 0), ("L", 0),
                result="e") == cm.invalidComponentID
    assert g.cpu.sp == g.stack_top and g.log() == []


def test_flags_are_compared_under_the_mask(qapp):
    g = Runner()
    comp = g.register(g.code(), flags=0x5)
    assert g.find(flags=0x1, mask=0x1) == comp and g.find(flags=0x2, mask=0x2) == 0
    assert g.find(flags=0x2) == comp            # no mask: any flags


def test_a_component_is_opened_called_and_closed(qapp):
    g = Runner()
    comp = g.register(g.code())
    ci = g.open(comp)
    assert ci and g.log() == [cm.kComponentOpenSelect]
    assert g.cm(0x13, ("L", comp), result="l") == 1
    g.cm(0x0D, ("L", ci), ("L", 100), result="")
    assert g.cm(0x0C, ("L", ci)) == 100
    assert g.call_instance(ci, 1, 5) == 105
    assert g.call_instance(ci, 7) == cm.badComponentSelector
    assert g.log() == [1, 7]
    assert g.cm(0x02, ("L", comp), result="e") == cm.validInstancesExist
    assert g.close(ci) == 0 and g.log() == [cm.kComponentCloseSelect]
    assert g.call_instance(ci, 1, 5) == cm.badComponentInstance and g.log() == []
    assert g.close(ci) == cm.invalidComponentID
    assert g.cm(0x02, ("L", comp), result="e") == 0 and g.count() == 0
    assert g.cpu.sp == g.stack_top


def test_open_default_component_opens_the_first_of_its_type(qapp):
    g = Runner()
    code = g.code()
    g.register(code, kind=OTHER)
    first = g.register(code, sub=ostype(b"one "))
    g.register(code, sub=ostype(b"two "))
    ci = g.cm(0x21, ("L", TYPE), ("L", 0))
    assert ci and g.cm(0x0C, ("L", ci)) == 0
    assert cm.manager(g).instances[ci].component.id == first
    assert g.cm(0x21, ("L", ostype(b"none")), ("L", 0)) == 0


def test_a_component_that_wants_it_is_sent_the_register_request(qapp):
    g = Runner()
    g.register(g.code(), flags=cm.cmpWantsRegisterMessage)
    assert g.log() == [cm.kComponentOpenSelect, cm.kComponentRegisterSelect,
                       cm.kComponentCloseSelect]


def test_registration_order_and_duplicates(qapp):
    """A component goes before those it's the same as, unless it asks to be
    after all of its type, and not at all if it asks for no duplicates."""
    g = Runner()
    code = g.code()
    first = g.register(code)
    second = g.register(code)
    assert g.find() == second and g.find(second) == first
    after = g.register(code, global_flags=cm.registerCompAfter)
    assert g.find(first) == after
    assert g.register(code, global_flags=cm.registerCmpNoDuplicates) == 0
    assert g.count() == 3


def test_call_component_function_with_storage(qapp):
    """A component's dispatcher hands a call's parameters to the routine
    for it: with the storage first, if it asks."""
    g = Runner()
    params = g.ptr(struct.pack(">BBhll", 0, 8, 1, 3, 10))     # b = 3, a = 10
    assert g.cm(0xFF, ("L", 1000), ("p", params), ("p", g.ptr(WITH_STORAGE))) == 1007
    assert g.cm(0xFF, ("p", params), ("p", g.ptr(WITHOUT))) == 7
    assert g.cpu.sp == g.stack_top


def test_a_fast_dispatch_component_gets_the_parameters_as_they_are(qapp):
    g = Runner()
    comp = g.register(g.code(FAST), flags=cm.cmpFastDispatch)
    ci = g.open(comp)
    assert ci
    g.cm(0x0D, ("L", ci), ("L", 40), result="")
    assert g.call_instance(ci, 1, 2) == 42
    assert g.call_instance(ci, 9) == cm.badComponentSelector
    assert g.close(ci) == 0
    assert g.cpu.sp == g.stack_top


def test_an_instances_error_refcon_and_a5(qapp):
    g = Runner()
    comp = g.register(g.code())
    ci = g.open(comp)
    g.cm(0x0B, ("L", ci), ("h", -50), result="")
    assert g.cm(0x0A, ("L", ci), result="e") == -50
    assert g.cm(0x0A, ("L", ci), result="e") == 0           # taken
    g.cm(0x11, ("L", comp), ("L", 0xCAFE), result="")
    assert g.cm(0x10, ("L", comp)) == 0xCAFE == g.cm(0x10, ("L", ci))
    a5 = g.cpu.a(5)
    assert g.cm(0x0E, ("L", ci)) == a5
    g.cm(0x0F, ("L", ci), ("L", 0x1230), result="")
    assert g.call_instance(ci, 2) == 0x1230 and g.cpu.a(5) == a5
    # A global component's instance runs in its client's A5 world.
    other = g.open(g.register(g.code(), global_flags=cm.registerCmpGlobal))
    assert g.cm(0x0E, ("L", other)) == 0 and g.call_instance(other, 2) == a5


def test_a_captured_component_is_hidden(qapp):
    g = Runner()
    comp = g.register(g.code())
    captured = g.cm(0x1C, ("L", comp), ("L", 0))
    assert captured and g.find() == 0 and g.cm(0x1C, ("L", captured), ("L", 0)) == 0
    assert g.open(captured)
    assert g.cm(0x1D, ("L", captured), result="e") == 0 and g.find() == captured
    assert g.cm(0x1D, ("L", captured), result="e") == cm.componentNotCaptured


def test_set_default_component(qapp):
    g = Runner()
    code = g.code()
    one = g.register(code, sub=ostype(b"one "))
    two = g.register(code, sub=ostype(b"two "))
    assert g.find() == one
    assert g.cm(0x1E, ("L", two), ("h", cm.defaultComponentAnySubType), result="e") == 0
    assert g.find() == two and g.find(two) == one


def thng(code_id=128, name_id=128, extension=None, flags=0) -> bytes:
    data = cm.DESC.pack(TYPE, ostype(b"sub "), ostype(b"mrtx"), flags, 0)
    data += cm.SPEC.pack(b"cmpc", code_id) + cm.SPEC.pack(b"STR ", name_id)
    data += cm.SPEC.pack(bytes(4), 0) * 2
    return data + (cm.EXTENSION.pack(*extension) if extension else b"")


def resource_runner(*things) -> Runner:
    g = Runner([Resource(b"cmpc", 128, COMPONENT), Resource(b"STR ", 128, b"\x06Tester"),
                *things])
    res = g.process.resources
    h = res.GetResource("cmpc", 128)        # where the code logs to
    g.mem.w32(g.heap.deref(h) + LOG, g.log_at)
    return g


def test_a_component_from_a_thng_is_loaded_from_its_file(qapp):
    g = resource_runner(Resource(b"thng", 128, thng()))
    res = g.process.resources
    comp = g.cm(0x12, ("L", res.GetResource("thng", 128)), ("h", 0))
    assert comp and g.log() == []
    name = g.handle(b"")
    g.cm(0x05, ("L", comp), ("p", 0), ("L", name), ("L", 0), ("L", 0), result="e")
    assert g.contents(name) == b"\x06Tester"
    ci = g.open(comp)
    assert ci and g.call_instance(ci, 1, 1) == 1 and g.log() == [-1, 1]
    refnum = g.cm(0x15, ("L", comp), result="h")
    assert refnum > 0 and res.CurResFile() == refnum
    assert g.cm(0x18, ("h", refnum), result="e") == 0


def test_a_thngs_version_is_asked_for_and_the_latest_kept(qapp):
    auto = (0, cm.componentDoAutoVersion, 0)
    g = resource_runner(Resource(b"thng", 128, thng(extension=auto)),
                        Resource(b"thng", 129, thng(extension=(0x10000, 1, 0))),
                        Resource(b"thng", 130, thng(extension=(0x30000, 1, 0))))
    res = g.process.resources
    first = g.cm(0x12, ("L", res.GetResource("thng", 128)), ("h", 0))
    assert first and g.log() == [-1, -4, -2]
    assert cm.manager(g).by_id[first].version == 0x20001
    assert g.cm(0x12, ("L", res.GetResource("thng", 129)), ("h", 0)) == 0     # older
    latest = g.cm(0x12, ("L", res.GetResource("thng", 130)), ("h", 0))
    assert latest and g.find() == latest and g.find(latest) == 0


def test_a_thng_older_than_one_registered_leaves_no_code(qapp, monkeypatch):
    g = resource_runner(Resource(b"thng", 128, thng(extension=(0, cm.componentDoAutoVersion, 0))),
                        Resource(b"thng", 130, thng(extension=(0x30000, 1, 0))))
    res = g.process.resources
    assert g.cm(0x12, ("L", res.GetResource("thng", 130)), ("h", 0))
    loaded = []
    load = cm._load

    def spy(t, comp):
        ok = load(t, comp)
        loaded.append(comp.code_handle)
        return ok
    monkeypatch.setattr(cm, "_load", spy)
    assert g.cm(0x12, ("L", res.GetResource("thng", 128)), ("h", 0)) == 0     # older
    assert g.log() == [-1, -4, -2] and loaded and loaded[0]
    assert not g.heap.is_handle(loaded[0])


def test_every_thng_in_a_file_is_registered(qapp):
    g = resource_runner(Resource(b"thng", 128, thng()), Resource(b"thng", 129, thng()))
    refnum = g.process.resources.CurResFile()
    assert g.cm(0x14, ("h", refnum), ("h", 0), result="l") == 2 and g.count() == 2
    assert g.cm(0x14, ("h", 999), ("h", 0), result="l") < 0


def test_an_applications_components_go_when_it_quits(qapp):
    g = Runner()
    comp = g.register(g.code())
    g.open(comp)
    g.log()
    cm.close_all(g)
    assert g.log() == [cm.kComponentCloseSelect] and g.count() == 0
    g.register(g.code())
    cm.forget(g)
    assert g.count() == 0 and g.log() == []


def test_an_unknown_routine_is_reported(qapp):
    g = Runner()
    assert g.cm(0x30, result="") == 0
    assert g.cpu.d(0) == cm.badComponentSelector and g.missing


def test_gestalt_says_theres_a_component_manager(qapp):
    g = Runner()
    assert g("Gestalt", ostype(b"cpnt")) == (0, cm.VERSION)
    assert dispatch.implemented(dispatch.trap_key(0xA82A))

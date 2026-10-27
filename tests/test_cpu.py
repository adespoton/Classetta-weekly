"""The processor: SR as the code itself would see it; stopping a run,
for the VBL tasks or a kill, at an instruction's end and not in the
middle of it; holding it to a speed; TRAPcc and tracing, which the core
gets wrong; and leaving the interpreter with code still running."""

import random
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from macrt.m68k import cpu as cpu_module
from macrt.m68k import instructions
from macrt.m68k.cpu import CPU
from macrt.memory import RAM
from macrt.toolbox import lowmem
from macrt.toolbox.events import tick_count, to_next_tick

CODE, COUNTER, TASK = 0x10000, 0x8000, 0x8100
COUNT_TWICE = bytes.fromhex("5290"     # 1: addq.l #1,(a0)
                            "5280"     # addq.l #1,d0
                            "60fa")    # bra.s 1b
NEVER = CODE + 0x100


def machine():
    mem = RAM(0x20000)
    mem.write(CODE, COUNT_TWICE)
    mem.w16(TASK + 10, 1)               # its vblCount: it's counting down to run
    cpu = CPU(mem)
    cpu.sr = 0x2000                     # interrupts let in
    cpu.sp = 0x9000
    cpu.set_a(0, COUNTER)
    cpu.pc = CODE
    return mem, cpu


def test_a_tick_stops_the_cpu_between_two_instructions():
    """While VBL tasks are queued, run() comes back for the runner to look
    at the clock, and the instruction it was in isn't run again after: the
    count in memory keeps step with D0."""
    mem, cpu = machine()
    mem.w32(lowmem.VBLQueue + 2, TASK)
    retraces, returns = 0, 0
    deadline = time.monotonic() + 1
    try:
        while time.monotonic() < deadline or retraces < 10:
            ev = cpu.run(NEVER)
            assert ev.kind == "interrupted", ev
            returns += 1
            if cpu.retrace_pending:
                retraces += 1
                cpu.retrace_pending = False
            ahead = 1 if ev.pc == CODE + 2 else 0       # past the first ADDQ only
            assert mem.r32(COUNTER) == (cpu.d(0) + ahead) & 0xFFFFFFFF, (returns, ev)
    finally:
        cpu.close()
    assert retraces >= 10


def test_a_vbl_task_not_counting_down_waits_for_nothing():
    """As the System's own task in the queue never is: run() goes on
    without a look at the clock."""
    mem, cpu = machine()
    mem.w32(lowmem.VBLQueue + 2, TASK)
    mem.w16(TASK + 10, 0)
    assert not cpu._interrupted_at_ticks()
    mem.w32(TASK, TASK + 0x20)          # another after it, that is
    mem.w16(TASK + 0x20 + 10, 3)
    assert cpu._interrupted_at_ticks()
    cpu.close()


def test_with_no_vbl_tasks_only_interrupt_stops_it():
    mem, cpu = machine()
    timer = threading.Timer(0.1, cpu.interrupt)
    timer.start()
    try:
        ev = cpu.run(NEVER)
    finally:
        timer.join()
        cpu.close()
    assert ev.kind == "interrupted"
    assert cpu.interrupt_requested and not cpu.retrace_pending
    assert mem.r32(COUNTER) > 1000


def test_a_speed_limit_holds_the_cpu_to_a_68000s_cycles():
    """With rate set, the code runs as fast as a 68000 at that many cycles
    a second would run it, by what its instructions take, and run() comes
    back about once a tick."""
    mem, cpu = machine()
    each = cpu_module.block_cycles(mem._b, CODE, len(COUNT_TWICE))
    assert each == 20 + 8 + 10          # ADDQ.L to memory, ADDQ.L to Dn, BRA.S
    cpu.rate = 600_000
    start = time.monotonic()
    returns = 0
    try:
        while time.monotonic() - start < 0.5:
            assert cpu.run(NEVER).kind == "interrupted"
            returns += 1
    finally:
        cpu.close()
    elapsed = time.monotonic() - start
    ran = each * cpu.d(0)
    assert 0.5 * cpu.rate * elapsed < ran <= cpu.rate * elapsed + cpu.rate // 100
    assert returns > 10


def test_ticks_is_what_tick_count_says():
    """The clock sets Ticks just after each tick: a program that reads it
    after TickCount sees the ticks gone by since."""
    mem, cpu = machine()
    try:
        for _ in range(10):
            time.sleep(max(0.0, to_next_tick() - 0.5) / 60)     # halfway through a tick
            for _ in range(17):         # a busy host may wake the clock late: give it a tick
                if mem.r32(lowmem.Ticks) == tick_count():
                    break
                time.sleep(0.001)
            else:
                pytest.fail(f"Ticks is {mem.r32(lowmem.Ticks)}, TickCount {tick_count()}")
            time.sleep(0.3 / 60)
    finally:
        cpu.close()


MOVE_SR_D7_NOP = bytes.fromhex("40c7" "4e71")
EDGES = [0, 1, 0x7F, 0x80, 0xFF, 0x7FFF, 0x8000, 0xFFFF, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]


@pytest.mark.parametrize("stop", ["until", "slice"])
@pytest.mark.parametrize("insn", [
    "b001", "b041", "b081",         # cmp.b/w/l d1,d0
    "d001", "d041", "d081",         # add
    "9001", "9041", "9081",         # sub
    "c041", "4a80", "2001",         # and.w d1,d0; tst.l d0; move.l d1,d0
    "d181",                         # addx.l d1,d0
])
def test_sr_is_what_move_from_sr_sees(insn, stop, monkeypatch):
    """Stopped after an instruction, the condition codes it set, as the
    next, which stores them, sees them; and still so for that one."""
    mem, cpu = machine()
    monkeypatch.setattr(cpu_module, "SLICE", 1)
    code = bytes.fromhex(insn) + MOVE_SR_D7_NOP
    at = CODE + 0x200

    def run(x, d0, d1, until, slicing=False):
        mem.write(at, code)
        mem.w32(lowmem.VBLQueue + 2, TASK if slicing else 0)
        cpu.sr = 0x2700 | x                     # masked, for no retrace to stop it first
        cpu.set_d(0, d0)
        cpu.set_d(1, d1)
        cpu.pc = at
        return cpu.run(until)

    try:
        for x in (0, 0x10):
            for d0 in EDGES:
                for d1 in EDGES:
                    assert run(x, d0, d1, at + 4).kind == "until"
                    sr = cpu.d(7) & 0xFFFF                          # not looked at on the way
                    at += 8
                    if stop == "until":
                        ev = run(x, d0, d1, at + 2)
                    else:                                       # after one instruction
                        ev = run(x, d0, d1, NEVER, slicing=True)
                    assert (ev.kind, ev.pc) == ("until" if stop == "until" else "interrupted",
                                                at + 2)
                    assert cpu.sr == sr, (insn, x, hex(d0), hex(d1))
                    mem.w32(lowmem.VBLQueue + 2, 0)
                    assert cpu.run(at + 4).kind == "until"
                    assert cpu.d(7) & 0xFFFF == sr, (insn, x, hex(d0), hex(d1))
                    at += 8
    finally:
        cpu.close()


def run_through(cpu, until):
    while (ev := cpu.run(until)).kind == "interrupted":
        pass
    assert (ev.kind, ev.pc) == ("until", until)


def test_68k_code_reaches_the_memory_a_range_mirrors_through_it():
    """Apache Strike draws its flight at a Mac Plus's $3FA700, which is the
    screen however much RAM it has: the memory reaches it there."""
    mem, cpu = machine()
    mem.mirror(0x1E000, 0x20000, 0x6000)
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("2080"         # move.l d0,(a0)
                                "2211"))       # move.l (a1),d1
    mem.w32(0x7710, 0xCAFEF00D)
    try:
        cpu.set_d(0, 0x12345678)
        cpu.set_a(0, 0x1F700)
        cpu.set_a(1, 0x1F710)
        cpu.pc = at
        run_through(cpu, at + 4)
        assert mem.r32(0x7700) == 0x12345678
        assert cpu.d(1) == 0xCAFEF00D
    finally:
        cpu.close()


def test_code_runs_as_written_a_moment_before():
    """An instruction put in place further on in the same block of code,
    as Microsoft Word puts a trap word, runs as it is now: each time."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("41fa000a"     # lea 1f(pc),a0
                                "3080"         # move.w d0,(a0)
                                "4e71" "4e71" "4e71"
                                "7200"))       # 1: moveq #0,d1, until it's written
    try:
        for n in (9, 3, 3, 7):
            cpu.set_d(0, 0x7200 | n)               # moveq #n,d1
            cpu.pc = at
            run_through(cpu, at + 14)
            assert cpu.d(1) == n
    finally:
        cpu.close()


def test_code_written_from_another_page_runs_as_written():
    """MacLanding writes the trap it's to call into a stub among its stack
    and runs it, the stack being written to between: each run is of the
    trap written last."""
    mem, cpu = machine()
    at, stub = CODE + 0x1000, CODE + 0x3000
    mem.write(at, bytes.fromhex("2282"         # move.l d2,(a1): something else on its page
                                "3080"         # move.w d0,(a0)
                                "4ed0"))       # jmp (a0)
    mem.write(stub, bytes.fromhex("7200" "4ef9") + (at + 6).to_bytes(4, "big"))
    try:
        for n in (9, 3, 3, 7, 1):
            cpu.set_d(0, 0x7200 | n)               # moveq #n,d1
            cpu.set_a(0, stub)
            cpu.set_a(1, stub + 0x100)
            cpu.pc = at
            run_through(cpu, at + 6)
            assert cpu.d(1) == n
    finally:
        cpu.close()


def test_an_instruction_that_clears_itself_runs_as_it_was_fetched():
    """Uninvited's last loop clears the code it decrypted, up to the
    instruction clearing it, and the two after it clear the rest: each
    runs as the processor fetched it, and the code after runs."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("43fafffe"     # lea (at)(pc),a1
                                "7001"         # moveq #1,d0
                                "4299"         # 1: clr.l (a1)+, itself the second time
                                "51c8fffc"     # dbra d0,1b
                                "4299"         # clr.l (a1)+: the DBRA
                                "4291"         # clr.l (a1): itself
                                "7205"))       # moveq #5,d1
    try:
        cpu.pc = at
        run_through(cpu, at + 18)
        assert cpu.d(1) == 5 and cpu.d(0) & 0xFFFF == 0xFFFF and cpu.a(1) == at + 12
        assert mem.read(at, 16) == bytes(16)
    finally:
        cpu.close()


def test_a_move_to_its_own_words_runs_as_it_was_fetched():
    """A MOVE of an immediate over its own words moves all of it, and
    what it wrote isn't run in its place."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("45fa0002"             # lea 1f(pc),a2
                                "24bc74077407"         # 1: move.l #$74077407,(a2)
                                "7205"))               # moveq #5,d1
    try:
        cpu.set_d(2, 0)
        cpu.pc = at
        run_through(cpu, at + 12)
        assert (cpu.d(1), cpu.d(2)) == (5, 0)       # not moveq #7,d2
        assert mem.read(at + 4, 6) == bytes.fromhex("740774077407")
    finally:
        cpu.close()


def test_a_page_written_to_from_another_by_turns_is_run_from_as_written(monkeypatch):
    """Word 1.0's interpreter keeps its variables on the page it runs each
    instruction from, and code on other pages writes them: the page comes
    to be mapped to be run from and written to at once, and goes on
    running what's written to it last."""
    mem, cpu = machine()
    at, stub = CODE + 0x1000, CODE + 0x3000
    mem.write(at, bytes.fromhex("2282"         # move.l d2,(a1): something else on its page
                                "3080"         # move.w d0,(a0)
                                "4ed0"))       # jmp (a0)
    mem.write(stub, bytes.fromhex("7200" "4ef9") + (at + 6).to_bytes(4, "big"))
    dropped = []
    drop = cpu.uc.ctl_remove_cache
    monkeypatch.setattr(cpu.uc, "ctl_remove_cache",
                        lambda start, end: (dropped.append(start), drop(start, end)))
    try:
        for i in range(3 * cpu_module.BOTH_AFTER):
            if i == 2 * cpu_module.BOTH_AFTER:
                dropped.clear()
            n = i % 7 + 1
            cpu.set_d(0, 0x7200 | n)               # moveq #n,d1
            cpu.set_a(0, stub)
            cpu.set_a(1, stub + 0x100)
            cpu.pc = at
            run_through(cpu, at + 6)
            assert cpu.d(1) == n
        assert dropped == []                        # by the core itself, now
    finally:
        cpu.close()


def test_python_drops_only_the_code_it_writes_over(monkeypatch):
    """QuickDraw writes the fields of a port kept on the page a program
    runs from: what's translated of the rest of the page is kept."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("7001" "7202"))    # moveq #1,d0; moveq #2,d1
    dropped = []
    drop = cpu.uc.ctl_remove_cache
    monkeypatch.setattr(cpu.uc, "ctl_remove_cache",
                        lambda start, end: (dropped.append((start, end)), drop(start, end)))
    try:
        run_through(cpu_at(cpu, at), at + 4)
        mem.w32(at + 0x800, 0x12345678)
        mem.w16(at + 0x80A, 0)
        run_through(cpu_at(cpu, at), at + 4)
        assert dropped == [(at + 0x800, at + 0x80C)]
        assert (cpu.d(0), cpu.d(1)) == (1, 2)
    finally:
        cpu.close()


def test_code_written_through_another_address_runs_as_written():
    """The top byte of an address isn't looked at, and a program that keeps
    its code in a resource writes it through a master pointer with the
    handle's flags in it.  Multiplan stores to its code segment through
    one, and puts a trap word in place ahead through the address it runs
    at, between: each run is of the instruction written last."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("2282"         # move.l d2,(a1): flags in a1's top byte
                                "4e71"
                                "41fa000a"     # lea 1f(pc),a0
                                "3080"         # move.w d0,(a0)
                                "4e71" "4e71" "4e71"
                                "7200"))       # 1: moveq #0,d1, until it's written
    try:
        for n in (9, 3, 3, 7, 1):
            cpu.set_a(1, 0x20000000 | (at + 0x800))
            cpu.pc = at
            run_through(cpu, at + 4)                # the store through the flags
            cpu.set_d(0, 0x7200 | n)                # moveq #n,d1
            cpu.pc = at + 4
            run_through(cpu, at + 18)
            assert cpu.d(1) == n
    finally:
        cpu.close()


def test_a_store_run_again_runs_at_the_address_it_was_run_at():
    """Code run through an address with flags in its top byte that stores
    ahead of itself runs on through that address, the store run again:
    Macintosh Pascal calls its jump table so, with its stack beside it."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("41fa000a"     # lea 1f(pc),a0
                                "3080"         # move.w d0,(a0)
                                "4e71" "4e71" "4e71"
                                "7200"         # 1: moveq #0,d1, until it's written
                                "45fa0000"))   # lea *(pc),a2
    flags = 0x80000000
    try:
        cpu.set_d(0, 0x7205)                    # moveq #5,d1
        cpu.pc = flags | at
        run_through(cpu, flags | (at + 18))
        assert cpu.d(1) == 5 and cpu.a(2) == flags | (at + 16)
    finally:
        cpu.close()


def test_code_written_from_python_after_a_store_to_its_page_runs_as_written():
    """A store to a page code runs from maps it to be written to; run from
    again, it's to be dropped once more when Python writes code there."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("2282"         # move.l d2,(a1): to its own page
                                "7200"))       # moveq #0,d1, until it's written
    try:
        for n in (9, 3, 3, 7):
            cpu.set_a(1, at + 0x800)
            run_through(cpu_at(cpu, at), at + 4)
            mem.w16(at + 2, 0x7200 | n)         # moveq #n,d1, from Python
            run_through(cpu_at(cpu, at), at + 4)
            assert cpu.d(1) == n
    finally:
        cpu.close()


def test_a_stack_written_from_python_isnt_taken_for_code(monkeypatch):
    """A trap leaves its result on the stack, from Python; the stack has
    no code to drop, and dropping it would take the page for code, and
    each push after it would drop it again."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("2f0d" "2a5f"))    # move.l a5,-(sp); movea.l (sp)+,a5
    dropped = []
    drop = cpu.uc.ctl_remove_cache
    monkeypatch.setattr(cpu.uc, "ctl_remove_cache",
                        lambda start, end: (dropped.append(start), drop(start, end)))
    try:
        cpu.set_a(7, CODE + 0x3800)
        for n in range(3):
            cpu.push32(n)
            cpu.pop32()
            run_through(cpu_at(cpu, at), at + 4)
        assert dropped == []
    finally:
        cpu.close()


def test_a_count_kept_among_the_code_counts_once():
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("41fa0006"     # lea 1f(pc),a0
                                "5250"         # addq.w #1,(a0)
                                "4e71"
                                "0000"))       # 1: the count
    try:
        for n in (1, 2, 3):
            cpu.pc = at
            run_through(cpu, at + 6)
            assert mem.r16(at + 8) == n
    finally:
        cpu.close()


def test_stores_past_the_block_theyre_from_dont_stop_the_core(monkeypatch):
    """Fontographer keeps the buffer of a file it writes in its code's
    page, and stores to it a byte at a time: a store that can't be to the
    block of code it's from is let be, with no stop to run it again, and
    the page comes to be mapped to be run from and written to at once."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("41fa00fe"     # lea at+$100(pc),a0
                                "7004"         # moveq #4,d0
                                "10c2"         # 1: move.b d2,(a0)+
                                "51c8fffc"     # dbra d0,1b
                                "7205"))       # moveq #5,d1
    stops, dropped = [], []
    stop, drop = cpu.uc.emu_stop, cpu.uc.ctl_remove_cache
    monkeypatch.setattr(cpu.uc, "emu_stop", lambda: (stops.append(cpu.pc), stop()))
    monkeypatch.setattr(cpu.uc, "ctl_remove_cache",
                        lambda start, end: (dropped.append(start), drop(start, end)))
    try:
        for i in range(3 * cpu_module.BOTH_AFTER):
            if i == 2 * cpu_module.BOTH_AFTER:
                dropped.clear()
            cpu.set_d(2, i)
            cpu.pc = at
            run_through(cpu, at + 14)
            assert cpu.d(1) == 5 and mem.read(at + 0x100, 5) == bytes([i] * 5)
        assert stops == [] and dropped == []
    finally:
        cpu.close()


def test_a_page_its_own_code_has_written_its_block_in_goes_on_being_watched():
    """Once code has stored to the block it's in, as Word does, its page
    isn't mapped to be run from and written to at once, however many
    stores past the block come after."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("41fa000a"     # lea 1f(pc),a0
                                "3080"         # move.w d0,(a0)
                                "4e71" "4e71" "4e71"
                                "7200"))       # 1: moveq #0,d1, until it's written
    mem.write(at + 0x20, bytes.fromhex("43fa00de"  # lea at+$100(pc),a1
                                       "3281"))    # move.w d1,(a1)
    try:
        for i in range(3 * cpu_module.BOTH_AFTER):
            n = i % 7 + 1
            cpu.set_d(0, 0x7200 | n)               # moveq #n,d1
            cpu.pc = at
            run_through(cpu, at + 14)
            assert cpu.d(1) == n
            cpu.pc = at + 0x20
            run_through(cpu, at + 0x26)
            assert mem.r16(at + 0x100) == n
    finally:
        cpu.close()


@pytest.mark.parametrize("code, length", [
    ("7001" "2080" "6000 0010", 8),                 # moveq; move.l d0,(a0); bra.w
    ("0cb9 12345678 0001 0000" "4e75", 12),         # cmpi.l #,abs.l; rts
    ("48e7 fffe" "2030 0173 00000004 00000008" "4e90", 18),   # movem; move.l ([bd,a0],od); jsr (a0)
    ("082c 0003 0006" "4a6e fffe" "51c9 fff0", 14),     # btst #3,6(a4); tst.w -2(a6); dbra
    ("e9c0 0841" "4e71" "a9f0", 8),                 # bfextu d0{1:1},d0; nop; a trap
])
def test_where_the_block_running_must_end(code, length):
    mem = bytes.fromhex(code) + bytes(64)
    assert cpu_module._run_end(mem, 0) == length


def test_a_block_not_known_to_end_may_run_to_the_pages_end():
    mem = bytes.fromhex("7001" "f200 0000") + bytes(cpu_module.PAGE_SIZE)     # an FPU instruction
    assert cpu_module._run_end(mem, 0) >= cpu_module.PAGE_SIZE
    assert cpu_module._run_end(bytes(2 * cpu_module.PAGE_SIZE), 8) >= cpu_module.PAGE_SIZE


# -- TRAPcc, which the core takes for an Scc to an immediate operand ----------
TRAPFS = bytes.fromhex("51fc"                  # trapf
                       "7001"                  # moveq #1,d0
                       "51fa 0100"             # trapf.w #$100
                       "7202"                  # moveq #2,d1
                       "51fb 0000 0100"        # trapf.l #$100
                       "7403")                 # moveq #3,d2


def test_trapf_goes_on_past_itself_and_its_operand():
    """The 350-point Adventure's runtime looks for a 68020 by running a
    TRAPF: the core took the next instruction's first word with it."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, TRAPFS)
    try:
        run_through(cpu_at(cpu, at), at + len(TRAPFS))
        assert (cpu.d(0), cpu.d(1), cpu.d(2)) == (1, 2, 3)
        assert mem.read(at, 0x200) == TRAPFS + bytes(0x200 - len(TRAPFS))   # no Sccs
    finally:
        cpu.close()


def test_trapf_written_to_code_that_has_run_is_seen():
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("4e71" "7001" "7202" "7403"))
    try:
        run_through(cpu_at(cpu, at), at + 8)
        cpu.set_d(0, 0)
        mem.w16(at, 0x51FC)                     # from Python: a segment loaded there
        run_through(cpu_at(cpu, at), at + 8)
        assert cpu.d(0) == 1
    finally:
        cpu.close()


@pytest.mark.parametrize("d1, trapped", [(5, True), (6, False)])
def test_trapcc_traps_on_its_condition(d1, trapped):
    """A TRAPcc that holds is a TRAPV exception; one that doesn't leaves the
    condition codes as they were, for the branch after it."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("b280"         # cmp.l d0,d1
                                "56fc"         # trapne
                                "6702"         # beq.s 1f
                                "7601"         # moveq #1,d3
                                "4e71"))       # 1:
    try:
        cpu.set_d(0, 6)
        cpu.set_d(1, d1)
        cpu.set_d(3, 0)
        ev = cpu_at(cpu, at).run(at + 10)
        if trapped:
            assert ev == ("exception", at + 2, cpu_module.TRAPV)
        else:
            assert ev.kind == "until" and cpu.d(3) == 0
    finally:
        cpu.close()


@pytest.mark.parametrize("add, trapped", [(0x01, True), (0x81, False)])
def test_trapv_traps_on_overflow(add, trapped):
    """The core takes TRAPV for an illegal instruction (Kid Pix's): it's a
    TRAPV exception when V is set, and when it isn't, nothing, the
    condition codes as they were."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("707f"          # moveq #$7f,d0
                                f"0600 00{add:02x}"     # addi.b #add,d0: $80 overflows, $00 doesn't
                                "4e76"          # trapv
                                "6702"          # beq.s 1f
                                "7601"          # moveq #1,d3
                                "4e71"))        # 1:
    try:
        cpu.set_d(3, 0)
        ev = cpu_at(cpu, at).run(at + 14)
        if trapped:
            assert ev == ("exception", at + 6, cpu_module.TRAPV)
        else:
            assert ev.kind == "until" and cpu.d(3) == 0
    finally:
        cpu.close()


@pytest.mark.parametrize("ccr", [0x04, 0x1B])
def test_rtr_returns_with_the_condition_codes_it_pops(ccr):
    """The core takes RTR for an illegal instruction too: it pops the
    condition codes, leaving the rest of SR, and returns.  The Angelsoft
    adventures' p-Machine compares reals so, with MOVE SR to the stack."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("487a 000a"           # pea back(pc)
                                f"3f3c ff{ccr:02x}"     # move.w #$ffxx,-(sp): the codes
                                "4e77"                  # rtr
                                "7601"                  # moveq #1,d3: not run
                                "4e71"))                # back:
    try:
        cpu.set_d(3, 0)
        run_through(cpu_at(cpu, at), at + 14)
        assert (cpu.d(3), cpu.sp, cpu.sr) == (0, 0x9000, 0x2000 | ccr)
    finally:
        cpu.close()


def test_two_stores_to_an_instruction_ahead_are_both_seen():
    """A trap word stored a byte at a time, low byte first, in the block
    running: the instruction's run as the second store left it, not as the
    block was translated after the first.  The Angelsoft p-Machine calls
    each trap so."""
    mem, cpu = machine()
    at = CODE + 0x1000
    stub = at + 16
    mem.write(at, bytes.fromhex(f"13fc 0054 {stub + 1:08x}"     # move.b #$54,(stub+1).l
                                f"13fc 00a9 {stub:08x}"         # move.b #$a9,(stub).l
                                "0000"))                        # stub: $a954
    try:
        cpu.pc = at
        ev = cpu.run(at + 0x100)
        assert ev == ("trap", stub, 0xA954)
    finally:
        cpu.close()


def test_jsr_sp_goes_to_the_code_on_the_stack():
    """The core pushes JSR (SP)'s return address before it works out where
    to go, and goes to the address it pushed.  King's Quest's glue for an
    asynchronous file call pushes an RTS and the trap and JSRs to them."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("3f3c 4e75"     # move.w #$4e75,-(sp): rts
                                "3f01"          # move.w d1,-(sp)
                                "4e97"          # jsr (sp)
                                "588f"          # addq.l #4,sp
                                "4e71"))
    try:
        cpu.set_d(1, 0x7001)                    # moveq #1,d0
        cpu.set_d(0, 0)
        run_through(cpu_at(cpu, at), at + 12)
        assert (cpu.d(0), cpu.d(1), cpu.sp) == (1, 0x7001, 0x9000)
    finally:
        cpu.close()


WARM = CODE + 0x5000


def warm(cpu):
    """Have the core run a block first, on a page of its own: the core
    shows _translated each block it translates after its first."""
    cpu.mem.write(WARM, bytes.fromhex("6002"    # bra.s 1f
                                      "4e71"
                                      "4e71"))  # 1:
    run_through(cpu_at(cpu, WARM), WARM + 6)
    assert cpu._edged


@pytest.mark.parametrize("sliced", [False, True])
@pytest.mark.parametrize("first", [True, False])
def test_trapf_is_stopped_at_in_the_first_block_or_after_and_in_slices(first, sliced):
    """Each block the core translates is looked through for the words to
    stop at as it's translated, but the first it runs, which is looked
    through before; and in slices, the core counts the instructions."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, TRAPFS)
    if sliced:
        mem.w32(lowmem.VBLQueue + 2, TASK)
        cpu.sr = 0x2700                         # the ticks not taken
    try:
        if not first:
            warm(cpu)
        assert cpu._interrupted_at_ticks() == sliced
        run_through(cpu_at(cpu, at), at + len(TRAPFS))
        assert (cpu.d(0), cpu.d(1), cpu.d(2)) == (1, 2, 3)
    finally:
        cpu.close()


def test_a_word_in_an_operand_isnt_stopped_at():
    """The core goes through each stop it has at each instruction it
    counts, so there's one only where an instruction starts."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("303c 51fc"     # move.w #$51fc,d0
                                "4e71"))
    try:
        warm(cpu)
        run_through(cpu_at(cpu, at), at + 6)
        assert cpu.d(0) == 0x51FC and at + 2 not in cpu._watched
    finally:
        cpu.close()


@pytest.mark.parametrize("code, count, stopped", [
    ("7001" "303c 51fc", 2, False),             # moveq #1,d0; move.w #$51fc,d0
    ("7001" "303c 51fc", 3, True),              # not the instructions the core has
    ("4e7a 0002" "303c 51fc", 2, True),         # movec cacr,d0: not one known here
])
def test_where_instructions_start_in_a_block_isnt_known_each_word_is_stopped_at(
        code, count, stopped):
    mem, cpu = machine()
    at = CODE + 0x1000
    code = bytes.fromhex(code)
    mem.write(at, code)
    try:
        assert cpu._hook_watched(at, at + len(code), count) == stopped
        assert (at + len(code) - 2 in cpu._watched) == stopped
    finally:
        cpu.close()


def cpu_at(cpu, pc):
    cpu.pc = pc
    return cpu


# -- where an exception from a divide, CHK or TRAPV goes back to --------------
@pytest.mark.parametrize("code, length", [
    ("80c1", 2),                        # divu.w d1,d0
    ("80ed 0004", 4),                   # divu.w 4(a5),d0
    ("81f9 0000 1000", 6),              # divs.w $1000.l,d0
    ("80fc 0000", 4),                   # divu.w #0,d0
    ("80f0 1002", 4),                   # divu.w 2(a0,d1.w),d0
    ("80f0 0162 0004 0008", 8),         # divu.w ([4,a0],8),d0: the 68020's full format
    ("4c41 0800", 4),                   # divs.l d1,d0
    ("4c7c 0000 0000 0000", 8),         # divu.l #0,d0
    ("4181", 2),                        # chk.w d1,d0
    ("41bc 000a", 4),                   # chk.w #10,d0
    ("413c 0000 000a", 6),              # chk.l #10,d0
    ("02fa 0800 012e", 6),              # chk2.w BOUNDS(pc),d0
    ("04d0 8800", 4),                   # chk2.l (a0),a0
    ("00f0 1800 0162 0004 0008", 10),   # chk2.b ([4,a0],8),d1
    ("4e76", 2),                        # trapv
    ("51fc", 2),                        # trapf
    ("57fa 0001", 4),                   # trapeq.w #1
    ("56fb 0000 0001", 6),              # trapne.l #1
])
def test_the_exception_goes_back_past_the_instruction(code, length):
    from macrt.m68k.runtime import after_instruction
    mem = RAM(0x2000)
    mem.write(0x1000, bytes.fromhex(code))
    assert after_instruction(mem, 0x1000) == 0x1000 + length


def test_a_programs_own_interrupt_handler_is_looked_for_at_each_tick():
    mem, cpu = machine()
    try:
        cpu.rom_interrupts = 0x7000
        mem.w32(4 * cpu_module.LEVEL_1, 0x7000)
        assert not cpu.own_interrupts()
        mem.w32(4 * cpu_module.LEVEL_1, 0x7100)
        assert cpu.own_interrupts()
        assert cpu.run(NEVER).kind == "interrupted"     # in slices, as for VBL tasks
    finally:
        cpu.close()


def test_the_stub_for_unhandled_exceptions_in_the_vector_is_no_handler_of_its_own():
    """SimCity 2000's demo moves vectors over vectors through NIL handles."""
    mem, cpu = machine()
    try:
        cpu.rom_interrupts, cpu.no_handler = 0x7000, 0x7010
        mem.w32(4 * cpu_module.LEVEL_1, 0x7010)
        assert not cpu.own_interrupts()
    finally:
        cpu.close()


def test_a_programs_own_routine_in_lvl1dt_is_looked_for_at_each_tick_too():
    """Master Tracks Pro leaves the System's handler in the vector and puts
    its own routine for timer 1 in Lvl1DT."""
    mem, cpu = machine()
    try:
        cpu.rom_interrupts = 0x7000
        cpu.rom_level_1_routines = (0x7100, 0x7160)
        mem.w32(4 * cpu_module.LEVEL_1, 0x7000)
        for n in range(8):
            mem.w32(lowmem.Lvl1DT + 4 * n, 0x7100 + 12 * n)
        assert cpu.own_level_1_routines() == 0 and not cpu.own_interrupts()
        mem.w32(lowmem.Lvl1DT + 4 * 6, 0x7200)
        assert cpu.own_level_1_routines() == 0x40 and cpu.own_interrupts()
        assert cpu.run(NEVER).kind == "interrupted"
    finally:
        cpu.close()


@pytest.mark.parametrize("short, instruction, size", [
    (True, None, 6),                    # a 68000's: SR and PC
    (True, CODE, 6),                    # and the same for a divide by zero
    (False, None, 8),                   # a 68020's: and the format and vector
    (False, CODE, 12),                  # format 2: and the instruction's address
])
def test_an_exception_frame_is_the_models(short, instruction, size):
    """MacWrite 4.5 returns from its TRAP handler with ADDQ.W #2,A7 and
    RTS, which works with a 68000's frame and no other."""
    mem, cpu = machine()
    try:
        cpu.short_frames = short
        mem.w32(4 * cpu_module.ZERO_DIVIDE, NEVER)
        cpu.sr = 0x2004                     # the Z flag
        cpu.take_exception(cpu_module.ZERO_DIVIDE, CODE + 2, instruction)
        assert (cpu.sp, cpu.pc) == (0x9000 - size, NEVER)
        assert (mem.r16(cpu.sp), mem.r32(cpu.sp + 2)) == (0x2004, CODE + 2)
        if not short:
            assert mem.r16(cpu.sp + 6) == (2 if instruction else 0) << 12 | 4 * 5
        cpu.sr = 0x2700
        cpu.return_from_exception()
        assert (cpu.sp, cpu.pc, cpu.sr) == (0x9000, CODE + 2, 0x2004)
    finally:
        cpu.close()


# -- trace mode ----------------------------------------------------------------
TRACED = bytes.fromhex("007c 8000"     # ori.w #$8000,sr: trace from here
                       "7001"          # moveq #1,d0
                       "7202"          # moveq #2,d1
                       "027c 7fff"     # andi.w #$7fff,sr: to here
                       "7403")         # moveq #3,d2
HANDLER = CODE + 0x1800


def run_traced(mem, cpu, until):
    """Run as the runtime does, to a trace handler that returns at once:
    each trace exception's frame, where it goes back to and the address
    of the instruction traced (a 68000's frame hasn't that)."""
    mem.w16(HANDLER, 0x4E73)                    # rte
    mem.w32(4 * cpu_module.TRACE, HANDLER)
    frames = []
    while (ev := cpu.run(until)).kind != "until":
        if ev.kind == "exception" and ev.code == cpu_module.TRACE:
            cpu.take_exception(ev.code, ev.pc, cpu.traced)
            assert not cpu.sr & cpu_module.T1   # the handler isn't traced
            frames.append((mem.r32(cpu.sp + 2), None if cpu.short_frames
                           else (mem.r16(cpu.sp + 6), mem.r32(cpu.sp + 8))))
        elif ev.kind == "exception":
            assert ev.code == cpu_module.RTE
            cpu.return_from_exception()
        else:
            assert ev.kind == "interrupted", ev
    return frames


@pytest.mark.parametrize("short, first", [(True, True), (False, True), (True, False)])
def test_with_t1_set_each_instruction_is_followed_by_a_trace_exception(short, first):
    """FullPaint's loader decrypts its segments in its trace handler, as
    the core doesn't trace: T1 set in SR, after each instruction that
    starts with it set, from the next one to the one that clears it."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, TRACED)
    try:
        if not first:
            warm(cpu)
        cpu.short_frames = short
        frames = run_traced(mem, cpu_at(cpu, at), at + len(TRACED))
        traced = [at + 4, at + 6, at + 8]
        assert [pc for pc, _ in frames] == [at + 6, at + 8, at + 12]
        if not short:
            assert [f for _, f in frames] == [
                (2 << 12 | 4 * cpu_module.TRACE, a) for a in traced]
        assert (cpu.d(0), cpu.d(1), cpu.d(2)) == (1, 2, 3)
        assert not cpu.sr & cpu_module.T1
    finally:
        cpu.close()


DATA = CODE + 0x1C00


@pytest.mark.parametrize("write, a0", [
    ("46c3", 0),                        # move.w d3,sr
    ("46d8", DATA),                     # move.w (a0)+,sr
    ("46e0", DATA + 2),                 # move.w -(a0),sr
    ("46e8 0004", DATA - 4),            # move.w 4(a0),sr
    ("46fc {sr:04x}", 0),               # move.w #sr,sr
    ("46f9 {data:08x}", 0),             # move.w data,sr: it may set it, so it's run alone
])
@pytest.mark.parametrize("sr", [0xA000, 0x2000])
def test_a_write_to_sr_that_sets_t1_is_traced_from(write, a0, sr):
    mem, cpu = machine()
    at = CODE + 0x1000
    code = bytes.fromhex(write.format(sr=sr, data=DATA) + "7401" "7602")
    mem.write(at, code)
    mem.w16(DATA, sr)
    try:
        cpu.set_d(3, sr)
        cpu.set_a(0, a0)
        frames = run_traced(mem, cpu_at(cpu, at), at + len(code))
        assert [pc for pc, _ in frames] == ([at + len(code) - 2, at + len(code)]
                                            if sr & cpu_module.T1 else [])
        assert (cpu.d(2), cpu.d(3)) == (1, 2)
    finally:
        cpu.close()


def test_a_write_to_sr_the_core_writes_on_a_page_mapped_for_both_is_traced_from():
    """The Surgeon decrypts its ORI #$8000,SR on a page that its loader's
    loop has come to map to be run from and written to at once, and runs it
    a few traps on: the page is looked through again for it."""
    mem, cpu = machine()
    at, page = CODE + 0x1000, CODE + 0x3000
    slot = page + 0x10
    mem.write(at, bytes.fromhex("2282"         # move.l d2,(a1)
                                "3080"         # move.w d0,(a0)
                                "4ed0"))       # jmp (a0)
    mem.write(at + 0x20, bytes.fromhex("2081"))     # move.l d1,(a0)
    mem.write(page, bytes.fromhex("7200" "4ef9") + (at + 6).to_bytes(4, "big"))
    mem.write(slot, bytes.fromhex("4e71 4e71" "7401" "7602"))
    try:
        for i in range(2 * cpu_module.BOTH_AFTER):
            cpu.set_d(0, 0x7200 | i % 7 + 1)       # moveq #n,d1
            cpu.set_a(0, page)
            cpu.set_a(1, page + 0x100)
            run_through(cpu_at(cpu, at), at + 6)
        assert page >> cpu_module.PAGE_BITS in cpu._both
        cpu.set_d(1, 0x007C8000)                    # ori.w #$8000,sr
        cpu.set_a(0, slot)
        run_through(cpu_at(cpu, at + 0x20), at + 0x22)
        frames = run_traced(mem, cpu_at(cpu, slot), slot + 8)
        assert [pc for pc, _ in frames] == [slot + 6, slot + 8]
        assert (cpu.d(2), cpu.d(3)) == (1, 2)
    finally:
        cpu.close()


def test_a_page_mapped_for_both_is_looked_through_again_where_it_changed():
    """A page mapped for both is written a few bytes at a time, at each
    trap where it's a program's jump table and stack: it's looked through
    again only around the bytes that changed, but every word to stop at
    it has now that it didn't have is in what's looked through."""
    rng = random.Random(1)
    words = (b"\x4e\x97", b"\x00\x7c", b"\x46\xfc", b"\x5f\xfb", b"\xf2\x20\x7c")
    size, chunk = cpu_module.PAGE_SIZE, cpu_module.CHUNK

    def found(page, start=0, end=size):
        return set(cpu_module._words_to_stop_at(page, start, end))

    for _ in range(300):
        old = bytearray(rng.randrange(256) for _ in range(size))
        new = bytearray(old)
        for _ in range(rng.randint(1, 4)):      # often across where a chunk ends
            at = rng.choice((rng.randrange(size - 3), rng.randrange(1, size // chunk) * chunk - 2,
                             size - chunk - 2))
            at += rng.randrange(-1, 2) & ~1
            word, way = rng.choice(words), rng.randrange(4)
            if way == 0:
                new[at] ^= 1 + rng.randrange(255)
            elif way == 1:
                new[at:at + len(word)] = word
            elif way == 2:                      # it was all there but its last byte
                old[at:at + len(word) - 1] = new[at:at + len(word) - 1] = word[:-1]
                new[at + len(word) - 1] = word[-1]
            else:                               # or but its first
                old[at + 1:at + len(word)] = new[at + 1:at + len(word)] = word[1:]
                new[at] = word[0]
        old, new = bytes(old), bytes(new)
        if new == old:
            continue
        differ = [i for i in range(size) if old[i] != new[i]]
        runs = cpu_module._changed(old, new)
        assert found(new) <= found(old).union(*(found(new, *run) for run in runs))
        for start, end in runs:                 # each near a byte that differs
            assert any(start - chunk < i < end + chunk for i in differ)
        assert sum(end - start for start, end in runs) <= len(differ) * (chunk + 4)


def test_flush_code_drops_what_the_core_has_translated():
    mem = RAM(0x20000)
    mem.write(CODE, bytes.fromhex("6100 00fe"))             # bsr SUB
    mem.write(CODE + 0x100, bytes.fromhex("7001 4e75"))     # SUB: moveq #1,d0; rts
    cpu = CPU(mem)
    cpu.set_a(7, 0x8000)

    def call():
        cpu.set_d(0, 0)
        cpu.pc = CODE
        cpu.run(CODE + 4)
        return cpu.d(0)

    assert call() == 1
    mem._b[CODE + 0x101] = 2    # moveq #2,d0, where the core doesn't see it change
    assert call() == 1          # as it was translated
    cpu.flush_code()
    assert call() == 2


# -- CHK2, CMP2 and FMOVE.P, which the core doesn't know --------------------
@pytest.mark.parametrize("d0, passed", [
    (5, True), (1, True), (10, True), (11, False), (0, False), (0xFFFF0005, True)])
def test_chk2_raises_a_chk_exception_out_of_bounds(d0, passed):
    """MPWAccuracy's subranges: in them, it goes on; out, it's a CHK
    exception, reported a word into the instruction as the core's CHK is.
    A data register is compared in the bounds' size."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("02fa 0800 0006"      # chk2.w bounds(pc),d0
                                "7601"                # moveq #1,d3
                                "4e71"                # nop
                                "0001 000a"))         # bounds: 1 to 10
    try:
        cpu.set_d(0, d0)
        cpu.set_d(3, 0)
        ev = cpu_at(cpu, at).run(at + 10)
        if passed:
            assert ev.kind == "until" and cpu.d(3) == 1
        else:
            assert ev == ("exception", at + 2, cpu_module.CHK)
            assert cpu.d(3) == 0
    finally:
        cpu.close()


@pytest.mark.parametrize("op, reg, bounds, value, z, c", [
    ("02fa 0000", 0, "0001 000a", 1, True, False),          # cmp2.w: on the lower bound
    ("02fa 0000", 0, "0001 000a", 10, True, False),         # on the upper
    ("02fa 0000", 0, "0001 000a", 5, False, False),
    ("02fa 0000", 0, "0001 000a", 0, False, True),
    ("02fa 0000", 0, "fffb 0005", 0xFFFF, False, False),    # -5 to 5: -1
    ("02fa 0000", 0, "fffb 0005", 6, False, True),
    ("02fa 0000", 0, "0005 fffb", 6, False, False),         # 5 to $FFFB, unsigned
    ("04fa 0000", 0, "8000 0000 7fff ffff", 0x80000000, True, False),   # cmp2.l
    ("00fa 8000", 8, "807f", 0xFFFFFF80, True, False),      # cmp2.b to a0: -128
    ("00fa 8000", 8, "807f", 0x80, False, True),            # a0 compared whole
])
def test_cmp2_sets_z_on_a_bound_and_c_outside_them(op, reg, bounds, value, z, c):
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex(op + "0008"           # cmp2 bounds(pc),rn
                                "55c4"                # scs d4
                                "57c5"                # seq d5
                                "4e71" + bounds))     # nop; bounds:
    try:
        (cpu.set_a if reg >= 8 else cpu.set_d)(reg & 7, value)
        run_through(cpu_at(cpu, at), at + 12)
        assert (cpu.d(5) & 0xFF == 0xFF, cpu.d(4) & 0xFF == 0xFF) == (z, c)
    finally:
        cpu.close()


def extended(x: float) -> bytes:
    """x as an extended real in memory: its sign and exponent, a word
    unused, and its mantissa."""
    bits = struct.unpack(">Q", struct.pack(">d", x))[0]
    sign, exponent = bits >> 48 & 0x8000, bits >> 52 & 0x7FF
    if not exponent:
        return struct.pack(">HHQ", sign, 0, 0)
    return struct.pack(">HHQ", sign | exponent - 1023 + 16383, 0,
                       1 << 63 | (bits & (1 << 52) - 1) << 11)


# The examples of FMOVE.P's k-factor in Motorola's manual: 12345.678765.
@pytest.mark.parametrize("k, packed", [
    (-5, "00040001 2345678770000000"),
    (-3, "00040001 2345679000000000"),
    (-1, "00040001 2345700000000000"),
    (0, "00040001 2346000000000000"),
    (1, "00040001 0000000000000000"),
    (3, "00040001 2300000000000000"),
    (5, "00040001 2346000000000000"),
])
def test_fmove_p_puts_a_real_as_packed_decimal_to_k_digits(k, packed):
    """Mandelbrot 2.7's numbers as text: to k digits after the point, or
    with k above 0, k digits.  With the k-factor in the instruction, and in
    a data register."""
    mem, cpu = machine()
    at, x, out = CODE + 0x1000, 0x6000, 0x6100
    mem.write(x, extended(12345.678765))
    mem.write(at, bytes.fromhex("f210 4800"           # fmove.x (a0),fp0
                                f"f211 6c{k & 0x7F:02x}"    # fmove.p fp0,(a1){#k}
                                "f212 7c30"))         # fmove.p fp0,(a2){d3}
    try:
        cpu.set_a(0, x)
        cpu.set_a(1, out)
        cpu.set_a(2, out + 0x10)
        cpu.set_d(3, k & 0xFFFFFFFF)
        run_through(cpu_at(cpu, at), at + 12)
        assert mem.read(out, 12).hex() == packed.replace(" ", "")
        assert mem.read(out + 0x10, 12).hex() == packed.replace(" ", "")
        assert cpu.fpsr & instructions.EXC == instructions.INEX2
    finally:
        cpu.close()


def test_fmove_p_takes_a_packed_decimal_real_to_a_register():
    """Rounded to the nearest extended real, as the FPU's registers are
    seen after it: by the FMOVE.X and FMOVE.L after it, and in the FPSR."""
    mem, cpu = machine()
    at, src, out = CODE + 0x1000, 0x6000, 0x6100
    mem.write(src, bytes.fromhex("00040001 2345678765000000"))  # 1.2345678765E+4
    mem.write(at, bytes.fromhex("f218 4c80"           # fmove.p (a0)+,fp1
                                "f211 6880"           # fmove.x fp1,(a1)
                                "f200 6080"           # fmove.l fp1,d0
                                "f201 a800"))         # fmove.l fpsr,d1
    try:
        cpu.set_a(0, src)
        cpu.set_a(1, out)
        run_through(cpu_at(cpu, at), at + 16)
        assert mem.read(out, 12).hex() == "400c0000c0e6b70e2c12ad82"
        assert cpu.d(0) == 12346
        assert cpu.d(1) & (instructions.INEX1 | instructions.AEXC_INEX) == (
            instructions.INEX1 | instructions.AEXC_INEX)
        assert cpu.a(0) == src + 12
    finally:
        cpu.close()


def test_fmove_p_to_a_predecrement_leaves_an_twelve_bytes_down():
    """The core takes it for an address error."""
    mem, cpu = machine()
    at, x, out = CODE + 0x1000, 0x6000, 0x6100
    mem.write(x, extended(-0.25))
    mem.write(at, bytes.fromhex("f210 4800"           # fmove.x (a0),fp0
                                "f221 6c03"))         # fmove.p fp0,-(a1){#3}
    try:
        cpu.set_a(0, x)
        cpu.set_a(1, out + 12)
        run_through(cpu_at(cpu, at), at + 8)
        assert cpu.a(1) == out
        assert mem.read(out, 12).hex() == "c0010002" "5000000000000000"     # -2.50E-1
    finally:
        cpu.close()


@pytest.mark.parametrize("packed, se, mantissa, raised", [
    ("7fff0000 0000000000000000", 0x7FFF, 0, 0),                        # infinity
    ("ffff0000 4000000000000000", 0xFFFF, 0x4000000000000000, 0),       # a quiet NaN
    ("7fff0000 2000000000000000", 0x7FFF, 0x6000000000000000, instructions.SNAN),
    ("80000000 0000000000000000", 0x8000, 0, 0),                        # -0
    ("00000001 0000000000000000", 0x3FFF, 1 << 63, 0),                  # 1
    ("40010001 0000000000000000", 0x3FFB, 0xCCCCCCCCCCCCCCCD, instructions.INEX1),  # 0.1
])
def test_a_packed_decimal_real_as_an_extended_one(packed, se, mantissa, raised):
    assert instructions.from_packed(bytes.fromhex(packed)) == (se, mantissa, raised)


@pytest.mark.parametrize("mode, digit", [
    (instructions.RN, 2), (instructions.RZ, 1), (instructions.RM, 1), (instructions.RP, 2)])
def test_a_packed_decimal_real_is_rounded_in_the_fpcrs_mode(mode, digit):
    data, raised = instructions.to_packed(0x3FFF, 0xC000000000000000, 1, mode)    # 1.5
    assert (data.hex(), raised) == (f"0000000{digit}" + "0" * 16, instructions.INEX2)


def test_a_packed_decimal_reals_exponent_past_999_raises_operr():
    data, raised = instructions.to_packed(0x3FFF - 4000, 1 << 63, 1)    # 2 ** -4000
    assert struct.unpack(">I", data[:4])[0] & 0xFFFFFFF0 == 0x42051000   # E-1205
    assert raised == instructions.OPERR | instructions.INEX2


def test_more_than_17_digits_raises_operr_and_gives_17():
    data, raised = instructions.to_packed(0x3FFF, 0xC000000000000000, 20)
    assert (data.hex(), raised) == ("00000001" "5000000000000000", instructions.OPERR)


@pytest.mark.parametrize("code, fpcr, fpsr", [
    ("f23c 8800 0800 0208", 0, 0x08000208),             # fmove.l #$08000208,fpsr
    ("f23c 9000 0000 0030", 0x30, 0),                   # fmove.l #$30,fpcr
    ("f23c 8400 0000 1234", 0, 0),                      # fmove.l #$1234,fpiar
    ("f23c 9800 0000 0010 0800 0000", 0x10, 0x08000000),    # fmovem.l #..,fpcr/fpsr
    ("f23c 9c00 0000 0020 0000 0008 0000 1234", 0x20, 0x08),
    ("f23c 8c00 0000 0008 0000 1234", 0, 0x08),         # fmovem.l #..,fpsr/fpiar
])
def test_fmove_of_data_to_the_fpus_control_registers(code, fpcr, fpsr):
    """The core takes it for an address error; and then FMOVE.L of FPCR
    and FPSR to D1 and D2 sees what it did."""
    mem, cpu = machine()
    at = CODE + 0x1000
    words = bytes.fromhex(code)
    mem.write(at, words + bytes.fromhex("f201 b000"     # fmove.l fpcr,d1
                                        "f202 a800"))   # fmove.l fpsr,d2
    try:
        run_through(cpu_at(cpu, at), at + len(words) + 8)
        assert (cpu.d(1), cpu.d(2)) == (fpcr, fpsr)
    finally:
        cpu.close()


@pytest.mark.parametrize("mode, rounded", [
    (0x00, (2, -2)),                    # to nearest
    (0x10, (1, -1)),                    # toward zero
    (0x20, (1, -2)),                    # toward minus infinity
    (0x30, (2, -1)),                    # toward plus infinity
])
def test_the_core_rounds_as_an_fmove_of_data_to_the_fpcr_says(mode, rounded):
    mem, cpu = machine()
    at, x = CODE + 0x1000, 0x6000
    mem.write(x, extended(1.5) + extended(-1.5))
    mem.write(at, bytes.fromhex(f"f23c 9000 0000 00{mode:02x}"     # fmove.l #mode,fpcr
                                "f218 4800"           # fmove.x (a0)+,fp0
                                "f200 6000"           # fmove.l fp0,d0
                                "f210 4800"           # fmove.x (a0),fp0
                                "f201 6000"))         # fmove.l fp0,d1
    try:
        cpu.set_a(0, x)
        run_through(cpu_at(cpu, at), at + 24)
        assert (cpu.d(0), cpu.d(1) - (1 << 32)) == rounded
    finally:
        cpu.close()


@pytest.mark.parametrize("mode, mantissa", [
    (0x00, 0x8000000400000000),         # extended
    (0x40, 0x8000000000000000),         # single
    (0x80, 0x8000000400000000),         # double
])
def test_the_core_rounds_to_the_precision_an_fmove_to_the_fpcr_says(mode, mantissa):
    """1 + 2**-29 has 30 bits of mantissa: a single's 24 can't keep them."""
    mem, cpu = machine()
    at, x, out = CODE + 0x1000, 0x6000, 0x6100
    mem.write(x, extended(1.0) + extended(2.0 ** -29))
    mem.write(at, bytes.fromhex(f"f23c 9000 0000 00{mode:02x}"     # fmove.l #mode,fpcr
                                "f218 4800"           # fmove.x (a0)+,fp0
                                "f210 4822"           # fadd.x (a0),fp0
                                "f211 6800"))         # fmove.x fp0,(a1)
    try:
        cpu.set_a(0, x)
        cpu.set_a(1, out)
        run_through(cpu_at(cpu, at), at + 20)
        assert mem.read(out + 4, 8).hex() == f"{mantissa:016x}"
    finally:
        cpu.close()


def test_setting_the_fpcr_leaves_the_core_as_an_fmove_to_it_does():
    """Every mode and precision: the core's state after each the same."""
    mem, cpu = machine()
    at = CODE + 0x1000
    mem.write(at, bytes.fromhex("f200 9000"))       # fmove.l d0,fpcr
    words = cpu_module.FPCR_WORD, cpu_module.FPCR_WORD + 3

    def state():
        cpu.uc.context_update(cpu._ctx)
        return list(cpu._state[cpu._state_at + words[0]:cpu._state_at + words[1]])
    try:
        for before in (0x00, 0x50, 0xA0):
            for value in range(0, 0x100, 0x10):
                cpu.fpcr = before
                cpu.set_d(0, value)
                run_through(cpu_at(cpu, at), at + 4)
                by_the_core = state()
                cpu.fpcr = before
                cpu.fpcr = value
                assert state() == by_the_core, (hex(before), hex(value))
    finally:
        cpu.close()


def test_fsave_and_frestore_an_idle_frame_leave_the_fpu_as_it_was():
    """FSAVE -(A7) puts the 68881's idle state frame 28 bytes down, and
    FRESTORE (A7)+ takes it back up; the registers are as they were."""
    mem, cpu = machine()
    at, x, out = CODE + 0x1000, 0x6000, 0x6100
    mem.write(x, extended(-0.25))
    mem.write(at, bytes.fromhex("f210 4800"           # fmove.x (a0),fp0
                                "f23c 9000 0000 0010"     # fmove.l #$10,fpcr
                                "f327"                # fsave -(a7)
                                "f35f"                # frestore (a7)+
                                "f211 6800"           # fmove.x fp0,(a1)
                                "f201 b000"))         # fmove.l fpcr,d1
    try:
        cpu.set_a(0, x)
        cpu.set_a(1, out)
        cpu.sp = sp = 0x8000
        run_through(cpu_at(cpu, at), at + 24)
        assert mem.read(sp - 28, 28) == instructions.IDLE
        assert mem.read(sp - 28, 4).hex() == "1f180000"
        assert cpu.sp == sp
        assert mem.read(out, 12) == extended(-0.25)
        assert cpu.d(1) == 0x10
    finally:
        cpu.close()


def test_frestore_of_a_null_frame_resets_the_fpu():
    mem, cpu = machine()
    at, x, out = CODE + 0x1000, 0x6000, 0x6100
    mem.write(x, extended(1.0))
    mem.write(at, bytes.fromhex("f210 4800"           # fmove.x (a0),fp0
                                "f23c 9800 0000 0030 0800 0000"     # fmovem.l #..,fpcr/fpsr
                                "f351"                # frestore (a1)
                                "f212 6800"           # fmove.x fp0,(a2)
                                "f201 b000"           # fmove.l fpcr,d1
                                "f202 a800"))         # fmove.l fpsr,d2
    try:
        cpu.set_a(0, x)
        cpu.set_a(1, out)
        cpu.set_a(2, out + 16)
        run_through(cpu_at(cpu, at), at + 26)
        assert mem.read(out + 16, 12).hex() == "7fff0000" "ffffffffffffffff"
        assert (cpu.d(1), cpu.d(2)) == (0, 0)
    finally:
        cpu.close()


def test_frestore_of_a_frame_of_another_format_raises_a_format_error():
    mem, cpu = machine()
    at, frame = CODE + 0x1000, 0x6000
    mem.write(frame, bytes.fromhex("1fb40000"))         # a 68881's busy frame
    mem.write(at, bytes.fromhex("f350"))                # frestore (a0)
    try:
        cpu.set_a(0, frame)
        cpu_at(cpu, at)
        while (ev := cpu.run(at + 2)).kind == "interrupted":
            pass
        assert (ev.kind, ev.pc, ev.code) == ("exception", at, instructions.FORMAT_ERROR)
    finally:
        cpu.close()


# A program still running as the interpreter exits: an application that
# didn't stop in time when its window closed.
STILL_RUNNING = """
import sys, threading, time
sys.path.insert(0, sys.argv[1])
from macrt.m68k.cpu import CPU
from macrt.memory import RAM
mem = RAM(0x20000)
mem.write(0x10000, bytes.fromhex("60fe"))       # bra.s *
cpu = CPU(mem)
cpu.pc, cpu.sp = 0x10000, 0x8000
threading.Thread(target=cpu.run, args=(0x20000,), daemon=True).start()
time.sleep(0.2)
"""


def test_the_interpreter_exits_cleanly_with_code_running():
    root = Path(__file__).resolve().parent.parent
    done = subprocess.run([sys.executable, "-c", STILL_RUNNING, str(root)],
                          capture_output=True, timeout=60)
    assert done.returncode == 0, done.stderr.decode()[-2000:]

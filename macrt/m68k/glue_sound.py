"""
The Sound Manager's traps (Inside Macintosh V-473): the channels and
their synthesizers are macrt.m68k.sound_manager's, which plays them.
SysBeep is the Toolbox's, ErrorSound the Dialog Manager's.  Sound
compressed with MACE expands to silence.

The Sound Input Manager's (Inside Macintosh: Sound) find no device to
record from, as on a Mac Plus or a Mac II, which have none.
"""

from __future__ import annotations

import struct

from ..memory import ADDRESS_MASK
from ..toolbox.files import paramErr
from ..toolbox.memmgr import memFullErr, nilHandleErr, noErr
from ..toolbox.resources import resNotFound
from . import sound_manager as sm
from .dispatch import trap
from .sound import SILENCE

badChannel = sm.badChannel
SCSTATUS_SIZE = 24
SMSTATUS_SIZE = 6
sysBeepDisable, sysBeepEnable = 0, 1
siNoSoundInHardware, siBadSoundInDevice = -220, -221
# NumVersions: 2.0, the Sound Manager of System 6.0.7 and System 7; and
# 3.0, which every System 7.5 has (Apple's Technical Q&A QTPC 03) where
# there is an Apple Sound Chip, not on a Mac Plus (Inside Macintosh: Sound)
VERSION, VERSION_3 = 0x02008000, 0x03008000
SYSTEM_7_5 = 0x0750
gestaltHasASC = 3


def _command(t, cmd: int) -> sm.Command:
    return struct.unpack(">HHI", t.mem.read(cmd & ADDRESS_MASK, 8))


@trap
def SndSoundManagerVersion(t):
    system = t.system
    if system.version >= SYSTEM_7_5 and system.model.hardware >> gestaltHasASC & 1:
        return VERSION_3
    return VERSION


@trap
def SndNewChannel(t, chan_ptr, synth, init, user_routine):
    """A channel record, unless the program passed one of its own, which
    has to say how long its queue is."""
    chan = t.mem.r32(chan_ptr) & ADDRESS_MASK
    owned = not chan
    if owned:
        chan = t.process.heap.new_ptr(sm.CHANNEL_SIZE, clear=True)
        if not chan:
            return memFullErr
        t.mem.w16(chan + sm.QLENGTH, sm.STD_QLENGTH)
        t.w32(chan_ptr, chan)
    elif t.mem.r16s(chan + sm.QLENGTH) <= 0:
        return badChannel
    t.mem.w32(chan + sm.CALLBACK, user_routine)
    t.machine.sound_manager.new_channel(t, chan, synth, owned)
    return noErr


@trap
def SndAddModifier(t, chan, modifier, id, init):
    ch = t.machine.sound_manager.channel(chan)
    if ch is None:
        return badChannel
    t.machine.sound_manager.add_modifier(t, ch, modifier & ADDRESS_MASK, init)
    return noErr


@trap
def SndDoCommand(t, chan, cmd, no_wait):
    ch = t.machine.sound_manager.channel(chan)
    if ch is None:
        return badChannel
    return noErr if ch.put(t.mem, _command(t, cmd), wait=not no_wait) else sm.queueFull


@trap
def SndDoImmediate(t, chan, cmd):
    ch = t.machine.sound_manager.channel(chan)
    if ch is None:
        return badChannel
    t.machine.sound_manager.do_immediate(t, ch, _command(t, cmd))
    return noErr


@trap
def SndPlay(t, chan, snd, asynch):
    manager = t.machine.sound_manager
    ch = None
    if chan:
        ch = manager.channel(chan)
        if ch is None:
            return badChannel
    if not snd:
        return sm.resProblem
    return manager.play(t, ch, snd & ADDRESS_MASK, bool(asynch))


@trap
def SndPlayDoubleBuffer(t, chan, params):
    ch = t.machine.sound_manager.channel(chan)
    if ch is None:
        return badChannel
    return t.machine.sound_manager.play_double(ch, params & ADDRESS_MASK)


@trap
def SndControl(t, synth, cmd):
    """availableCmd: whether a synthesizer can do what init asks, which
    is anything but stereo; versionCmd: its version."""
    c, p1, p2 = _command(t, cmd)
    if c == sm.availableCmd:
        p1 = int(synth in sm.SYNTHS and p2 & sm.initStereo != sm.initStereo)
    elif c == sm.versionCmd:
        p2 = sm.SYNTH_VERSION
    t.mem.write(cmd & ADDRESS_MASK, struct.pack(">HHI", c, p1, p2))
    return noErr


@trap
def SndChannelStatus(t, chan, length, status):
    ch = t.machine.sound_manager.channel(chan)
    if ch is None:
        return badChannel
    t.mem.write(status, t.machine.sound_manager.status(ch)[:min(max(length, 0), SCSTATUS_SIZE)])
    return noErr


@trap
def SndManagerStatus(t, length, status):
    """An SMStatus: the most load it takes, its channels and the load
    they make, which macrt doesn't measure."""
    smstatus = struct.pack(">hhh", 100, len(t.machine.sound_manager.channels), 0)
    t.mem.write(status, smstatus[:min(max(length, 0), SMSTATUS_SIZE)])
    return noErr


@trap
def SndGetSysBeepState(t, state):
    t.w16(state, int(t.machine.sound_manager.sys_beep))


@trap
def SndSetSysBeepState(t, state):
    if state not in (sysBeepDisable, sysBeepEnable):
        return paramErr
    t.machine.sound_manager.sys_beep = state == sysBeepEnable
    return noErr


# The system beep's volume and the default for sound out, each a long:
# the right side's in the high word, the left's in the low, kFullVolume
# ($0100) at most (Inside Macintosh: Sound, the Sound Manager).  They're
# kept for whoever asks; what's played isn't made softer by them.
@trap
def GetSysBeepVolume(t, level):
    t.w32(level, t.machine.sound_manager.volumes["beep"])
    return noErr


@trap
def SetSysBeepVolume(t, level):
    t.machine.sound_manager.volumes["beep"] = level & 0xFFFFFFFF
    return noErr


@trap
def GetDefaultOutputVolume(t, level):
    t.w32(level, t.machine.sound_manager.volumes["output"])
    return noErr


@trap
def SetDefaultOutputVolume(t, level):
    t.machine.sound_manager.volumes["output"] = level & 0xFFFFFFFF
    return noErr


@trap
def SndDisposeChannel(t, chan, quiet_now):
    ch = t.machine.sound_manager.channel(chan)
    if ch is None:
        return badChannel
    t.machine.sound_manager.dispose(t, ch, bool(quiet_now))
    return noErr


def _settings_heap(t, settings: int):
    """The heap of a handle a program passed, or None."""
    try:
        heap = t.system.heap_of(settings)
    except ValueError:
        return None
    return heap if heap.is_handle(settings & ADDRESS_MASK) else None


@trap
def SetSoundPreference(t, kind, name, settings):
    """A sound component's settings, by resource type and name, for
    GetSoundPreference to give back (Inside Macintosh: Sound, the Sound
    Manager).  macrt keeps them while it runs, not in a file in the
    Preferences folder."""
    heap = _settings_heap(t, settings)
    if heap is None or not heap.deref(settings):
        return nilHandleErr
    t.machine.sound_manager.preferences[kind & 0xFFFFFFFF, t.pstr(name)] = \
        t.mem.read(heap.deref(settings), heap.handle_size(settings))
    return noErr


@trap
def GetSoundPreference(t, kind, name, settings):
    """The settings saved with that type and name, in the handle the
    caller passes, resized to fit; without any, the Resource Manager's
    error for a resource that isn't there."""
    data = t.machine.sound_manager.preferences.get((kind & 0xFFFFFFFF, t.pstr(name)))
    if data is None:
        return resNotFound
    heap = _settings_heap(t, settings)
    if heap is None:
        return nilHandleErr
    if not heap.set_handle_size(settings, len(data)):
        return memFullErr
    t.mem.write(heap.deref(settings), data)
    return noErr


# =========================================================================
# MACE: sound compressed 3:1 and 6:1
# =========================================================================
def _expand(t, out: int, cnt: int) -> None:
    """Silence, as much as cnt packets expand to: 6 samples each, of the
    one channel asked for (Inside Macintosh: Sound, the Sound Manager).
    How MACE compresses sound isn't published, so macrt can't expand it."""
    cnt &= 0xFFFFFFFF
    if 0 < cnt and cnt * 6 <= ADDRESS_MASK + 1:
        t.mem.write(out & ADDRESS_MASK, bytes([SILENCE]) * (cnt * 6))


@trap
def Exp1to3(t, in_buffer, out_buffer, cnt, in_state, out_state, channels, which):
    _expand(t, out_buffer, cnt)


@trap
def Exp1to6(t, in_buffer, out_buffer, cnt, in_state, out_state, channels, which):
    _expand(t, out_buffer, cnt)


# =========================================================================
# The Sound Input Manager
# =========================================================================
@trap
def SPBVersion(t):
    return VERSION


@trap
def SPBGetIndexedDevice(t, count, name, icon):
    return siBadSoundInDevice


@trap
def SPBOpenDevice(t, name, permission, ref):
    return siBadSoundInDevice


@trap
def SndRecord(t, filter_proc, corner, quality, snd):
    return siNoSoundInHardware


@trap
def SndRecordToFile(t, filter_proc, corner, quality, refnum):
    return siNoSoundInHardware

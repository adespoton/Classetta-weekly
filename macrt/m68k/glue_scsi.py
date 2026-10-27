"""
The SCSI Manager (Inside Macintosh IV and V, The SCSI Manager): a bus
with nothing on it.  The disks macrt mounts are images, reached through
the File Manager, not devices on a bus, so there's no target for a
program that talks to drives itself (to find and mount them, or to
format one) to select.  SCSIGet wins the bus, as it does when no one
else is using it, and selecting a device fails with scCommErr, as it
does when "no device [is] connected", IM IV's gloss on the code.  The
calls that need a device selected first fail the same way.
"""

from __future__ import annotations

from ..toolbox.memmgr import noErr
from .dispatch import trap

scCommErr = 2


@trap
def SCSIReset(t):
    return noErr


@trap
def SCSIGet(t):
    return noErr


@trap
def SCSISelect(t, _target_id):
    return scCommErr


@trap
def SCSISelAtn(t, _target_id):
    return scCommErr


@trap
def SCSICmd(t, _buffer, _count):
    return scCommErr


@trap
def SCSIRead(t, _tib):
    return scCommErr


@trap
def SCSIRBlind(t, _tib):
    return scCommErr


@trap
def SCSIWrite(t, _tib):
    return scCommErr


@trap
def SCSIWBlind(t, _tib):
    return scCommErr


@trap
def SCSIComplete(t, _stat_p, _message_p, _wait):
    return scCommErr


@trap
def SCSIMsgIn(t, _message_p):
    return scCommErr


@trap
def SCSIMsgOut(t, _message):
    return scCommErr


@trap
def SCSIStat(t):
    """The bus's control and status bits: none of its signals asserted."""
    return 0

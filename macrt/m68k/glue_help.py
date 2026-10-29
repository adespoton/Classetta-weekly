"""
Help Manager traps (Pack14): the Help menu, and the calls about balloons,
which are never shown.
"""

from __future__ import annotations

from weakref import WeakKeyDictionary

from ..toolbox import script
from ..toolbox.memmgr import memFullErr, noErr
from ..toolbox.resources import resNotFound
from .dispatch import trap
from .glue_menus import _menu_handle


# =========================================================================
# Help Manager (Pack14): the Help menu.  Balloons are never shown, as
# they aren't on a Mac with Show Balloons off, and Show Balloons can't be
# turned on.  What an application sets for its balloons is kept, for it
# to get back.
# =========================================================================
hmHelpDisabled = -850
hmNoBalloonUp = -862


class _Balloons:
    """An application's balloon settings: the font, its 'hdlg' for the
    next dialog and its menus' 'hmnu's."""

    def __init__(self):
        help_font = script.script_variable(script.smScriptHelpFondSize)
        self.font, self.size = help_font >> 16, help_font & 0xFFFF
        self.dialog = -1
        self.menus: dict[int, int] = {}


_balloons: WeakKeyDictionary = WeakKeyDictionary()       # process: _Balloons


def _balloon_settings(t) -> _Balloons:
    return _balloons.setdefault(t.process, _Balloons())


@trap
def HMGetHelpMenuHandle(t, mh_p):
    """The application's own Help menu, to append its items to."""
    m = t.tb.HMGetHelpMenuHandle()
    t.mem.w32(mh_p, _menu_handle(m))
    return noErr if m is not None else memFullErr


@trap
def HMGetBalloons(t):
    return False


@trap
def HMSetBalloons(t, flag):
    return noErr


@trap
def HMIsBalloon(t):
    return False


@trap
def HMShowBalloon(t, msg_p, tip, rect_p, proc, wdef, variant, method):
    return hmHelpDisabled


@trap
def HMShowMenuBalloon(t, item, menu_id, flags, reserved, tip, rect_p, proc, wdef, variant):
    return hmHelpDisabled


@trap
def HMRemoveBalloon(t):
    return hmNoBalloonUp


@trap
def HMGetBalloonWindow(t, window_p):
    t.mem.w32(window_p, 0)
    return noErr


@trap
def HMScanTemplateItems(t, which_id, res_file, which_type):
    return noErr


@trap
def HMGetFont(t, font_p):
    t.mem.w16(font_p, _balloon_settings(t).font)
    return noErr


@trap
def HMSetFont(t, font):
    _balloon_settings(t).font = font
    return noErr


@trap
def HMGetFontSize(t, size_p):
    t.mem.w16(size_p, _balloon_settings(t).size)
    return noErr


@trap
def HMSetFontSize(t, size):
    _balloon_settings(t).size = size
    return noErr


@trap
def HMGetDialogResID(t, res_p):
    t.mem.w16(res_p, _balloon_settings(t).dialog & 0xFFFF)
    return noErr


@trap
def HMSetDialogResID(t, res_id):
    _balloon_settings(t).dialog = res_id
    return noErr


@trap
def HMGetMenuResID(t, menu_id, res_p):
    res_id = _balloon_settings(t).menus.get(menu_id)
    if res_id is None:
        return resNotFound
    t.mem.w16(res_p, res_id & 0xFFFF)
    return noErr


@trap
def HMSetMenuResID(t, menu_id, res_id):
    _balloon_settings(t).menus[menu_id] = res_id
    return noErr

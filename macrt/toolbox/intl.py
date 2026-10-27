"""
The International Utilities' formats: the US international resources
(Inside Macintosh I-495 and I-497) for a System file without them, and
dates, times and string order as those resources describe them.  Text is
Mac Roman bytes throughout.
"""

from __future__ import annotations

import datetime
import struct
import unicodedata
from typing import NamedTuple

from . import numformat

# Intl0Rec, 'INTL' 0: numbers, short dates and times
DATE_ORDER = 7
SHRT_DATE_FMT = 8
DATE_SEP = 9
TIME_CYCLE = 10
TIME_FMT = 11
MORN_STR = 12
EVE_STR = 16
TIME_SEP = 20
TIME1_SUFF = 21
TIME5_SUFF = 25
METRIC_SYS = 29
INTL0_SIZE = 32

# Intl1Rec, 'INTL' 1: long dates
DAYS_AT = 0
MONTHS_AT = 112
SUPPRESS_DAY = 304
LNG_DATE_FMT = 305
DAY_LEADING0 = 306
ABBR_LEN = 307
ST0 = 308
INTL1_SIZE = 332

# NItl4Rec, 'itl4', the tokens resource (Inside Macintosh: Text, Appendix
# B): where its tables are, from the start of the resource, and how long
ITL4_TABLES = 8
UNTOKEN_OFFSET, DEF_PARTS_OFFSET, WHT_SP_LIST_OFFSET = 32, 36, 40
UNTOKEN_LENGTH, DEF_PARTS_LENGTH, WHT_SP_LIST_LENGTH = 58, 60, 62
ITL4_HEADER = 68

century, mntLdingZ, dayLdingZ = 0x80, 0x40, 0x20        # shrtDateFmt
hrLeadingZ, minLeadingZ, secLeadingZ = 0x80, 0x40, 0x20  # timeFmt
timeCycle24, timeCycleZero, timeCycle12 = 0, 1, 255
shortDate, longDate, abbrevDate = 0, 1, 2
# dateOrder: mdy, dmy, ymd, myd, dym, ydm
DATE_ORDERS = ("mdy", "dmy", "ymd", "myd", "dym", "ydm")

DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
EPOCH = datetime.datetime(1904, 1, 1)
FIRST, LAST = datetime.datetime(1, 1, 1), datetime.datetime(9999, 12, 31, 23, 59, 59)


def _str15(s: str) -> bytes:
    return bytes([len(s)]) + s.encode("mac_roman").ljust(15, b"\0")


def us_intl0() -> bytes:
    """The US Intl0Rec: 1,234.56, $, 12/21/83 and 1:05:09 PM."""
    return (b".,;$\0\0" + bytes([0xD0, 0, 0, ord("/"), timeCycle12, minLeadingZ | secLeadingZ])
            + b" AM\0 PM\0:" + bytes(8) + b"\0" + struct.pack(">H", 1))


def us_intl1() -> bytes:
    """The US Intl1Rec: Wednesday, December 21, 1983."""
    names = b"".join(map(_str15, DAYS + MONTHS))
    return (names + bytes([0, 0xFF, 0, 3]) + b"\0\0\0\0, \0\0 \0\0\0, \0\0\0\0\0\0"
            + struct.pack(">HH", 1, 0x4E75))


def us_itl4() -> bytes:
    """The US tokens resource, with only its number parts table, the one
    the Text Utilities' number formatting and Numbers use: there's no
    IntlTokenize here to use the others."""
    parts = numformat.us_parts()
    header = struct.pack(">h4shhhhIh", 0, b"itl4", 0, 1, 0, 0, 0, ITL4_TABLES)
    header += bytes(DEF_PARTS_OFFSET - len(header)) + struct.pack(">I", ITL4_HEADER)
    header = header.ljust(DEF_PARTS_LENGTH, b"\0") + struct.pack(">h", len(parts))
    return header.ljust(ITL4_HEADER, b"\0") + parts


DEFAULTS = {0: us_intl0, 1: us_intl1}


class DateTime(NamedTuple):
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    day_of_week: int        # 1 for Sunday


def date_time(secs: int) -> DateTime:
    """Seconds since 1904, as SecondsToDate (or, for a LongDateTime, its
    64-bit form) gives them."""
    try:
        d = EPOCH + datetime.timedelta(seconds=secs)
    except OverflowError:
        d = FIRST if secs < 0 else LAST
    return DateTime(d.year, d.month, d.day, d.hour, d.minute, d.second, d.isoweekday() % 7 + 1)


def _number(n: int, leading_zero: int) -> bytes:
    return b"%02d" % n if leading_zero else b"%d" % n


def _packed(data: bytes) -> bytes:
    """A PACKED ARRAY[1..4] OF CHAR: up to the first NUL."""
    return data.split(b"\0", 1)[0]


def date_string(secs: int, form: int, intl: bytes) -> bytes:
    """IUDateString's text: intl is an Intl0Rec for shortDate, an Intl1Rec
    for longDate and abbrevDate."""
    dt = date_time(secs)
    if form == shortDate:
        fmt = intl[SHRT_DATE_FMT]
        fields = {"m": _number(dt.month, fmt & mntLdingZ), "d": _number(dt.day, fmt & dayLdingZ),
                  "y": b"%d" % dt.year if fmt & century else b"%02d" % (dt.year % 100)}
        order = DATE_ORDERS[intl[DATE_ORDER]] if intl[DATE_ORDER] < len(DATE_ORDERS) else "mdy"
        return _packed(intl[DATE_SEP:DATE_SEP + 1]).join(fields[c] for c in order)
    # The abbreviation is the first abbrLen bytes of the name's field (I-505)
    abbr = intl[ABBR_LEN] if form != longDate else 0

    def name(at: int) -> bytes:
        return intl[at + 1:at + 1 + (abbr or intl[at])]

    st = [_packed(intl[ST0 + 4 * i:ST0 + 4 * i + 4]) for i in range(5)]
    month, day = name(MONTHS_AT + 16 * (dt.month - 1)), _number(dt.day, intl[DAY_LEADING0])
    out = st[0]
    if not intl[SUPPRESS_DAY]:
        out += name(DAYS_AT + 16 * (dt.day_of_week - 1)) + st[1]
    out += month + st[2] + day if intl[LNG_DATE_FMT] else day + st[2] + month
    return out + st[3] + b"%d" % dt.year + st[4]


def time_string(secs: int, seconds: bool, intl: bytes) -> bytes:
    """IUTimeString's text, from an Intl0Rec."""
    dt = date_time(secs)
    fmt, cycle, sep = intl[TIME_FMT], intl[TIME_CYCLE], intl[TIME_SEP:TIME_SEP + 1]
    hour = dt.hour if cycle == timeCycle24 else dt.hour % 12 or (12 if cycle == timeCycle12 else 0)
    out = _number(hour, fmt & hrLeadingZ) + sep + _number(dt.minute, fmt & minLeadingZ)
    if seconds:
        out += sep + _number(dt.second, fmt & secLeadingZ)
    pm = dt.hour >= 12
    if cycle == timeCycle24:
        # The suffix's first four bytes are for the morning, the last four
        # for the afternoon.
        at = TIME5_SUFF if pm else TIME1_SUFF
    else:
        at = EVE_STR if pm else MORN_STR
    return out + _packed(intl[at:at + 4])


# StringToDate and StringToTime (Inside Macintosh: Text, Text Utilities):
# the date or time at the start of some text, and how sure of it they are.
longDateFound, leftOverChars, sepNotIntlSep, fieldOrderNotIntl = 1, 2, 4, 8
extraneousStrings, tooManySeps, sepNotConsistent = 16, 32, 64
fatalDateTime, dateTimeNotFound, dateTimeInvalid = 0x8000, 0x8400, 0x8800


class Parsed(NamedTuple):
    status: int
    used: int               # how many bytes of the text it took
    fields: tuple           # (year, month, day, dayOfWeek) or (hour, minute, second)


def _tokens(text: bytes) -> list[tuple[str, int, int]]:
    """(kind, start, end): a number, a word, a space or one other byte."""
    out, i = [], 0
    while i < len(text):
        c = text[i:i + 1]
        kind = ("number" if c.isdigit() else "word" if c.isalpha() or text[i] >= 0x80
                else "space" if c in b" \t\r\n" else "sep")
        j = i + 1
        if kind != "sep":
            while j < len(text) and (text[j:j + 1].isdigit() if kind == "number" else
                                     text[j:j + 1] in b" \t\r\n" if kind == "space" else
                                     text[j:j + 1].isalpha() or text[j] >= 0x80):
                j += 1
        out.append((kind, i, j))
        i = j
    return out


def _names(intl1: bytes, at: int, count: int) -> list[bytes]:
    return [intl1[at + 16 * i + 1:at + 16 * i + 1 + intl1[at + 16 * i]].lower()
            for i in range(count)]


def _named(word: bytes, names: list[bytes], abbr: int) -> int:
    """Which of names word is, from 1: the whole of one, or the first
    three or more letters of one (\"Sept\"), or its abbreviation."""
    word = word.lower()
    for i, name in enumerate(names):
        if word == name or (len(word) >= min(3, len(name)) and name.startswith(word)) \
                or (abbr and word == name[:abbr]):
            return i + 1
    return 0


def _year(y: int, digits: int, this_year: int) -> int:
    """A year of two digits is the one nearest this year, as Inside
    Macintosh: Text has it; of three, a year after 1000."""
    if digits <= 2 and y < 100:
        century = this_year - this_year % 100
        if this_year % 100 >= 90 and y <= 10:
            century += 100
        elif this_year % 100 <= 10 and y >= 90:
            century -= 100
        return century + y
    return y + 1000 if 100 <= y < 1000 else y


def parse_date(text: bytes, intl0: bytes, intl1: bytes, today: DateTime) -> Parsed:
    """StringToDate: a short date in the Intl0Rec's order and separator,
    or a long one with a month's name in the Intl1Rec (\"September 1,
    1987\", \"1 Sept 1987\", \"1 1987 sEpT\"), a day's name allowed before
    it.  What it doesn't give is today's."""
    months = _names(intl1, MONTHS_AT, 12)
    days = _names(intl1, DAYS_AT, 7)
    abbr = intl1[ABBR_LEN]
    date_sep = _packed(intl0[DATE_SEP:DATE_SEP + 1])
    numbers, month, status, used, day_name = [], 0, 0, 0, False
    seps: list[bytes] = []
    pending_sep = 0
    for kind, start, end in _tokens(text):
        token = text[start:end]
        if kind == "space":
            continue
        if kind == "sep":
            if not (numbers or month or day_name):
                break
            pending_sep += 1
            seps.append(token)
            continue
        if kind == "number" and len(numbers) < (2 if month else 3):
            numbers.append((int(token), end - start))
        elif kind == "word" and not month and _named(token, months, abbr):
            month = _named(token, months, abbr)
        elif kind == "word" and not (numbers or month or day_name) and _named(token, days, abbr):
            day_name = True                     # a day's name, before the date
            seps = []
        else:
            break
        if pending_sep > 1:
            status |= tooManySeps
        pending_sep = 0
        used = end
        if len(numbers) + bool(month) == 3:
            break
    if not numbers and not month:
        return Parsed(dateTimeNotFound, 0, ())
    order = DATE_ORDERS[intl0[DATE_ORDER]] if intl0[DATE_ORDER] < len(DATE_ORDERS) else "mdy"
    if month:
        status |= longDateFound
        order = order.replace("m", "")
    else:
        short = [s for s in seps if s not in b",."]
        if any(s != date_sep for s in short):
            status |= sepNotIntlSep
        if len(set(short)) > 1:
            status |= sepNotConsistent
    if len(numbers) < len(order):           # no year: this year's
        order = order.replace("y", "")
    fields = dict(zip(order, numbers))
    if "y" in fields and "d" in fields and fields["d"][1] > 2 >= fields["y"][1]:
        fields["d"], fields["y"] = fields["y"], fields["d"]
        status |= fieldOrderNotIntl
    if "m" in fields and "d" in fields and fields["m"][0] > 12 >= fields["d"][0]:
        fields["d"], fields["m"] = fields["m"], fields["d"]
        status |= fieldOrderNotIntl
    year, digits = fields.get("y", (today.year, 4))
    year = _year(year, digits, today.year)
    month = month or fields.get("m", (today.month, 0))[0]
    day = fields.get("d", (today.day, 0))[0]
    try:
        d = datetime.date(year, month, day)
    except ValueError:
        return Parsed(dateTimeInvalid, used, ())
    if text[used:].strip():
        status |= leftOverChars
    return Parsed(status, used, (year, month, day, d.isoweekday() % 7 + 1))


def _suffixes(intl0: bytes) -> tuple[list[bytes], list[bytes]]:
    """The morning and evening strings, as typed: without spaces or
    full stops, either case (\"p.m.\" for \" PM\")."""
    def plain(at: int) -> bytes:
        return _packed(intl0[at:at + 4]).replace(b" ", b"").replace(b".", b"").lower()
    morning = [s for s in (plain(MORN_STR), plain(TIME1_SUFF)) if s]
    evening = [s for s in (plain(EVE_STR), plain(TIME5_SUFF)) if s]
    return morning, evening


def parse_time(text: bytes, intl0: bytes) -> Parsed:
    """StringToTime: hours, minutes and seconds with the Intl0Rec's time
    separator, then its morning or evening string if it's on a 12-hour
    clock."""
    time_sep = intl0[TIME_SEP:TIME_SEP + 1]
    morning, evening = _suffixes(intl0)
    numbers, status, used, pm = [], 0, 0, None
    tokens = _tokens(text)
    i = 0
    while i < len(tokens):
        kind, start, end = tokens[i]
        token = text[start:end]
        i += 1
        if kind == "space":
            continue
        if kind == "number" and len(numbers) < 3 and pm is None:
            numbers.append(int(token))
            used = end
            continue
        if kind == "sep" and numbers and pm is None and len(numbers) < 3 \
                and i < len(tokens) and tokens[i][0] == "number":
            if token != time_sep:
                status |= sepNotIntlSep
            continue
        if kind in ("word", "sep") and numbers and pm is None:
            # The suffix and its full stops, "p.m.": the longest run of
            # words and stops up to a space that is one.
            run = i - 1
            while run < len(tokens) and tokens[run][0] in ("word", "sep"):
                run += 1
            for j in range(run, i - 1, -1):
                plain = text[start:tokens[j - 1][2]].replace(b".", b"").lower()
                if plain in morning or plain in evening:
                    pm, used, i = plain in evening, tokens[j - 1][2], j
                    break
            if pm is not None:
                continue
        break
    if not numbers:
        return Parsed(dateTimeNotFound, 0, ())
    hour, minute, second = (numbers + [0, 0])[:3]
    if pm is not None:
        if not 1 <= hour <= 12:
            return Parsed(dateTimeInvalid, used, ())
        hour = hour % 12 + (12 if pm else 0)
    if hour > 23 or minute > 59 or second > 59:
        return Parsed(dateTimeInvalid, used, ())
    if text[used:].strip():
        status |= leftOverChars
    return Parsed(status, used, (hour, minute, second))


def is_metric(intl0: bytes) -> bool:
    return bool(intl0[METRIC_SYS])


# Sorting: letters compare first without case or accents ("primary"),
# then, if all of that is equal, upper case before lower and plain before
# accented.  Ligatures sort as their letters.
_LIGATURES = {"Æ": "AE", "æ": "ae", "Œ": "OE", "œ": "oe", "ß": "ss", "ﬁ": "fi", "ﬂ": "fl"}
_VARIANTS = {"Ø": "O", "ø": "o", "ı": "i", "“": '"', "”": '"', "«": '"', "»": '"',
             "‘": "'", "’": "'", "\xa0": " "}
_MARKS = "̧́̀̂̈̃̊"   # acute grave circumflex umlaut...
OTHER_MARK, VARIANT, LIGATURE = len(_MARKS) + 1, len(_MARKS) + 2, len(_MARKS) + 3
_LOWER = 0x80


def _sort_keys(code: int) -> tuple[tuple[int, int], ...]:
    """Each letter's (primary, secondary) key; a ligature has two."""
    c = bytes([code]).decode("mac_roman")
    keys = []
    for i, ch in enumerate(_LIGATURES.get(c, c)):
        variant = LIGATURE if c in _LIGATURES and i == 0 else 0
        if ch in _VARIANTS:
            ch, variant = _VARIANTS[ch], VARIANT
        base, *marks = unicodedata.normalize("NFD", ch)
        if marks:
            variant = _MARKS.index(marks[0]) + 1 if marks[0] in _MARKS else OTHER_MARK
        upper = base.upper()
        try:
            primary = upper.encode("mac_roman")
        except UnicodeEncodeError:
            primary = b""
        if len(primary) != 1:
            keys.append((code, 0))
        else:
            keys.append((primary[0], variant | (_LOWER if base != upper else 0)))
    return tuple(keys)


SORT_KEYS = tuple(_sort_keys(code) for code in range(256))


def _keys(text: bytes) -> list[tuple[int, int]]:
    return [k for code in text for k in SORT_KEYS[code]]


def compare(a: bytes, b: bytes) -> int:
    """IUMagString: -1, 0 or 1 as a sorts before, with or after b."""
    ka, kb = _keys(a), _keys(b)
    for x, y in (([p for p, _ in ka], [p for p, _ in kb]), (ka, kb)):
        if x != y:
            return -1 if x < y else 1
    return 0


def equal(a: bytes, b: bytes) -> int:
    """IUMagIDString: 0 if a and b are the same text without regard for
    secondary ordering, so for case and accents ('Rose' is 'rose'), else
    1 (Inside Macintosh I, the International Utilities Package)."""
    return 0 if [p for p, _ in _keys(a)] == [p for p, _ in _keys(b)] else 1

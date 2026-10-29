"""
Number format specification strings (Inside Macintosh: Text, the Text
Utilities): a format such as "###,###.##;-###,###.##;0" says how
StringToFormatRec, FormatRecToString, ExtendedToString and
StringToExtended write numbers and read them, with a number parts table,
from the tokens resource ('itl4'), to say which characters are its
digits, separators and signs.

What's in a NumFormatString is private to the system that made it, so
macrt's are its own: a tag, then the format's parts.  One made anywhere
else, such as one a program keeps in its resources, can't be read here:
ExtendedToString writes the number plainly for it, and StringToExtended
reads a plain number.  Text is Mac Roman bytes throughout.
"""

from __future__ import annotations

import decimal
import struct
from typing import NamedTuple

from . import sane

# The number parts table's entries (NumberParts.data, from 1)
tokLeftQuote, tokRightQuote, tokLeadPlacer, tokLeader, tokNonLeader = 1, 2, 3, 4, 5
tokZeroLead, tokPercent, tokPlusSign, tokMinusSign, tokThousands = 6, 7, 8, 9, 10
tokSeparator, tokEscape, tokDecPoint, tokUnquoteds, tokMaxSymbols = 12, 13, 14, 15, 31
curNumberPartsVersion = 1
NUMBER_PARTS_SIZE = 172             # version, 31 wide characters, 4 arrays of 10, 20 spare

# FormatResultType, the low byte of a FormatStatus
(fFormatOK, fBestGuess, fOutOfSynch, fSpuriousChars, fMissingDelimiter, fExtraDecimal,
 fMissingLiteral, fExtraExp, fFormatOverflow, fFormStrIsNAN, fBadPartsTable, fExtraPercent,
 fExtraSeparator, fEmptyFormatString) = range(14)
fPositive, fNegative, fZero = range(3)

NUM_FORMAT_SIZE = 256               # NumFormatString: fLength, fVersion and 254 bytes
TAG = b"mcrt"                       # macrt's NumFormatStrings start with this

# A format's items, as macrt keeps them: digits, separators and signs,
# the exponent with its sign always or only when negative, and literals
ZERO, SKIP, PAD = b"0", b"#", b"^"
DIGIT_ITEMS = (ZERO, SKIP, PAD)
POINT, THOUSANDS, PERCENT, PLUS, MINUS = b".", b",", b"%", b"+", b"-"
EXP_PLUS, EXP_MINUS = b"E", b"e"
LITERAL, NEXT_PART = 0, b";"


# =========================================================================
# The number parts table
# =========================================================================
US_PARTS = {tokLeftQuote: b"'", tokRightQuote: b"'", tokLeadPlacer: b"^",
            tokLeader: b"\xca", tokNonLeader: b"#", tokZeroLead: b"0", tokPercent: b"%",
            tokPlusSign: b"+", tokMinusSign: b"-", tokThousands: b",", tokSeparator: b";",
            tokEscape: b"\\", tokDecPoint: b"."}
US_UNQUOTED = b"()[]{} $"
US_EXPONENTS = (b"E+", b"E-", b"E")         # pePlus, peMinus, peMinusPlus


def _wide(c: bytes) -> bytes:
    return c.rjust(2, b"\0")


def _wide_array(s: bytes) -> bytes:
    return struct.pack(">h", len(s) - 1) + b"".join(_wide(s[i:i + 1]) for i in range(len(s))) \
        .ljust(20, b"\0")


def us_parts() -> bytes:
    """macrt's US number parts table: 1,234.56, with a nonbreaking space
    to pad with."""
    data = [US_PARTS.get(n, b"") for n in range(1, tokUnquoteds)]
    data += [US_UNQUOTED[i:i + 1] for i in range(len(US_UNQUOTED))]
    data += [b""] * (tokMaxSymbols - len(data))
    table = struct.pack(">h", curNumberPartsVersion) + b"".join(map(_wide, data))
    table += b"".join(_wide_array(s) for s in US_EXPONENTS) + _wide_array(b"0123456789")
    return table.ljust(NUMBER_PARTS_SIZE, b"\0")


class Parts:
    """A number parts table: the characters, of one byte or two, for each
    of its entries."""

    def __init__(self, data: bytes):
        data = data[:NUMBER_PARTS_SIZE].ljust(NUMBER_PARTS_SIZE, b"\0")
        self.valid = struct.unpack_from(">h", data)[0] == curNumberPartsVersion

        def char(at: int) -> bytes:
            w = data[at:at + 2]
            return w if w[0] else w[1:].replace(b"\0", b"")

        def array(at: int) -> bytes:
            n = struct.unpack_from(">h", data, at)[0] + 1
            return b"".join(char(at + 2 + 2 * i) for i in range(max(0, min(n, 10))))
        self.chars = {n: char(2 * n) for n in range(1, tokMaxSymbols + 1)}
        self.unquoted = {c for n, c in self.chars.items() if n >= tokUnquoteds and c}
        at = 2 + 2 * tokMaxSymbols
        self.exp_plus, self.exp_minus, self.exp_minus_plus = (array(at + 22 * i) for i in range(3))
        self.valid = self.valid and all(self.chars[n] for n in (
            tokNonLeader, tokZeroLead, tokLeadPlacer, tokDecPoint, tokSeparator))

    def __getitem__(self, token: int) -> bytes:
        return self.chars[token]


US = Parts(us_parts())


# =========================================================================
# Format strings to formats and back
# =========================================================================
class Format(NamedTuple):
    """A format's parts: positive, then negative and zero if it has them.
    Each item is one of the codes above, or (LITERAL, text)."""
    parts: tuple

    def encode(self) -> bytes | None:
        """The NumFormatString, or None if it won't fit."""
        out = TAG
        for i, part in enumerate(self.parts):
            out += NEXT_PART if i else b""
            for item in part:
                out += b"".join(bytes([LITERAL, c]) for c in item[1]) if type(item) is tuple \
                    else item
        if len(out) > NUM_FORMAT_SIZE - 2:
            return None
        return bytes([len(out), 1]) + out.ljust(NUM_FORMAT_SIZE - 2, b"\0")

    @staticmethod
    def decode(rec: bytes) -> Format | None:
        """The format a NumFormatString macrt made has; None for another's."""
        n = rec[0]
        data = rec[2:2 + n]
        if not data.startswith(TAG):
            return None
        parts, part, i = [], [], len(TAG)
        while i < len(data):
            c = data[i:i + 1]
            if c[0] == LITERAL and i + 1 < len(data):
                _literal(part, data[i + 1:i + 2])
                i += 2
                continue
            if c == NEXT_PART:
                parts.append(tuple(part))
                part = []
            else:
                part.append(c)
            i += 1
        parts.append(tuple(part))
        return Format(tuple(parts))


def _literal(part: list, text: bytes) -> None:
    if part and type(part[-1]) is tuple:
        text = part.pop()[1] + text
    part.append((LITERAL, text))


def parse(spec: bytes, parts: Parts) -> tuple[Format | None, int]:
    """StringToFormatRec: a format specification string's format, and how
    well it was read.  Characters that mean nothing in a format are left
    out.  The exponent is matched in either case: AppleScript's formats
    have '0.0#e+##0' against the table's 'E+'."""
    if not parts.valid:
        return None, fBadPartsTable
    if not spec:
        return None, fEmptyFormatString
    tokens = {parts[n]: item for n, item in (
        (tokZeroLead, ZERO), (tokNonLeader, SKIP), (tokLeadPlacer, PAD), (tokDecPoint, POINT),
        (tokThousands, THOUSANDS), (tokPercent, PERCENT), (tokPlusSign, PLUS),
        (tokMinusSign, MINUS)) if parts[n]}
    exponents = [(s, item) for s, item in ((parts.exp_plus, EXP_PLUS),
                                           (parts.exp_minus, EXP_MINUS)) if s]
    status = fFormatOK
    found: list[list] = [[]]
    i = 0
    while i < len(spec):
        part = found[-1]
        rest = spec[i:]
        exponent = next(((s, item) for s, item in exponents
                         if rest[:len(s)].upper() == s.upper()), None)
        two = rest[:2] if len(rest) > 1 and rest[:2] in tokens else None
        if parts[tokLeftQuote] and rest.startswith(parts[tokLeftQuote]):
            i += len(parts[tokLeftQuote])
            end = spec.find(parts[tokRightQuote], i) if parts[tokRightQuote] else -1
            if end < 0:
                _literal(part, spec[i:])
                return None, fMissingLiteral
            _literal(part, spec[i:end])
            i = end + len(parts[tokRightQuote])
        elif parts[tokEscape] and rest.startswith(parts[tokEscape]):
            i += len(parts[tokEscape])
            if i < len(spec):
                _literal(part, spec[i:i + 1])
                i += 1
        elif rest.startswith(parts[tokSeparator]):
            if len(found) == 3:
                return None, fExtraSeparator
            found.append([])
            i += len(parts[tokSeparator])
        elif exponent is not None:
            if EXP_PLUS in part or EXP_MINUS in part:
                return None, fExtraExp
            part.append(exponent[1])
            i += len(exponent[0])
        elif two is not None or rest[:1] in tokens:
            key = two or rest[:1]
            item = tokens[key]
            if item == POINT and POINT in part:
                return None, fExtraDecimal
            if item == PERCENT and PERCENT in part:
                return None, fExtraPercent
            part.append(item)
            i += len(key)
        elif rest[:1] in parts.unquoted or rest[:2] in parts.unquoted:
            c = rest[:2] if rest[:2] in parts.unquoted else rest[:1]
            _literal(part, c)
            i += len(c)
        else:
            status = fSpuriousChars
            i += 1
    if not any(item in DIGIT_ITEMS for item in found[0]):
        return None, fFormStrIsNAN
    return Format(tuple(tuple(p) for p in found)), status


def _quoted(text: bytes, parts: Parts) -> bytes:
    """A literal as a format has it: in quotes, unless it's all characters
    that needn't be, with an escape before each closing quote in it."""
    if all(text[i:i + 1] in parts.unquoted for i in range(len(text))):
        return text
    out = b""
    for i, piece in enumerate(text.split(parts[tokRightQuote])):
        if i:
            out += parts[tokEscape] + parts[tokRightQuote]
        if piece:
            out += parts[tokLeftQuote] + piece + parts[tokRightQuote]
    return out


def unparse(fmt: Format, parts: Parts) -> tuple[bytes, list[tuple[int, int]]]:
    """FormatRecToString: the format's specification string, and where in
    it each part is (its first character, from 1, and length; 0 and 0 for
    a part it hasn't got)."""
    chars = {ZERO: parts[tokZeroLead], SKIP: parts[tokNonLeader], PAD: parts[tokLeadPlacer],
             POINT: parts[tokDecPoint], THOUSANDS: parts[tokThousands],
             PERCENT: parts[tokPercent], PLUS: parts[tokPlusSign], MINUS: parts[tokMinusSign],
             EXP_PLUS: parts.exp_plus, EXP_MINUS: parts.exp_minus}
    out, where = b"", []
    for n, part in enumerate(fmt.parts):
        if n:
            out += parts[tokSeparator]
        start = len(out)
        for item in part:
            out += _quoted(item[1], parts) if type(item) is tuple else chars[item]
        where.append((start + 1, len(out) - start))
    where += [(0, 0)] * (3 - len(where))
    return out[:255], where


# =========================================================================
# Numbers to strings
# =========================================================================
def _digits(x: sane.Num, places: int) -> tuple[bytes, bytes]:
    """|x| rounded to places decimals: its whole digits, without leading
    zeros (none for 0), and its decimals."""
    n, _ = sane._scaled(x, -places, sane.TONEAREST)
    whole, frac = divmod(n, 10 ** places)
    # Decimal writes an Extended's thousands of whole digits, which str won't
    return (str(decimal.Decimal(whole)).encode() if whole else b""), \
        (str(frac).encode().rjust(places, b"0") if places else b"")


def _scientific(x: sane.Num, whole: int, places: int) -> tuple[bytes, bytes, int]:
    """|x| as m * 10**e, m with whole digits before the point (rounded to
    places after it): its digits, and e."""
    if x.zero:
        return b"0" * whole, b"0" * places, 0
    count = whole + places
    d = sane.to_decimal(sane.Num(x.kind, 0, x.sig, x.exp), False, count, sane.Env())
    short = count - len(d.sig)          # past the 19 digits SANE gives
    sig = d.sig + b"0" * short
    return sig[:whole].lstrip(b"0") or b"0", sig[whole:], d.exp - short + places


class _Writer:
    """A part's items written out, with number's digits in them."""

    def __init__(self, parts: Parts):
        self.parts = parts
        self.chars = {POINT: parts[tokDecPoint], THOUSANDS: parts[tokThousands],
                      PERCENT: parts[tokPercent], PLUS: parts[tokPlusSign],
                      MINUS: parts[tokMinusSign]}

    def text(self, item) -> bytes:
        return item[1] if type(item) is tuple else self.chars.get(item, b"")

    def whole(self, items, digits: bytes) -> tuple[bytes, bool]:
        """Whole digits fill from the right: what's between them comes out
        if there's a digit to its left, else padding if there's a padding
        digit.  Whether there were too many digits."""
        out = []
        left = list(digits)
        for i in range(len(items) - 1, -1, -1):
            item = items[i]
            more = [it for it in items[:i] if it in DIGIT_ITEMS]
            if item in DIGIT_ITEMS:
                if left:
                    out.append(bytes([left.pop()]))
                elif item == ZERO:
                    out.append(b"0")
                elif item == PAD:
                    out.append(self.parts[tokLeader])
            elif left or ZERO in more:
                out.append(self.text(item))
            elif PAD in more:
                out.append(self.parts[tokLeader] * len(self.text(item)))
        over = bool(left)
        return bytes(left) + b"".join(reversed(out)), over

    def fraction(self, items, digits: bytes) -> tuple[bytes, bool]:
        """Decimals fill from the left: a skipping digit after the last
        that isn't zero (or a zero digit) comes out as nothing, a padding
        digit as padding.  Whether any digit came out."""
        places = [it for it in items if it in DIGIT_ITEMS]
        last = max([i for i, c in enumerate(digits) if c != ord("0")]
                   + [i for i, it in enumerate(places) if it == ZERO], default=-1)
        out, n = [], 0
        for item in items:
            if item in DIGIT_ITEMS:
                if n <= last:
                    out.append(digits[n:n + 1])
                elif item == PAD:
                    out.append(self.parts[tokLeader])
                n += 1
            elif n <= last:
                out.append(self.text(item))
        return b"".join(out), last >= 0

    def exponent(self, marker: bytes, items, e: int) -> bytes:
        p = self.parts
        sign = p.exp_minus if e < 0 else p.exp_plus if marker == EXP_PLUS else p.exp_minus_plus
        digits, _ = self.whole(items, str(abs(e)).encode() if e else b"")
        return sign + digits


class _Layout(NamedTuple):
    """A part's items: before its first digit, the whole digits' and the
    decimals' (either side of the point, if it has one), after the last
    digit, then its exponent marker, the exponent's digits and what
    follows them."""
    before: list
    whole: list
    point: bool
    frac: list
    tail: list
    marker: bytes | None
    exponent: list
    end: list


def _split(part) -> _Layout:
    part = list(part)
    marker = next((it for it in part if it in (EXP_PLUS, EXP_MINUS)), None)
    mantissa = part[:part.index(marker)] if marker else part
    exponent = part[part.index(marker) + 1:] if marker else []
    is_digit = [it in DIGIT_ITEMS for it in mantissa]
    first = is_digit.index(True) if True in is_digit else len(mantissa)
    last = len(is_digit) - 1 - is_digit[::-1].index(True) if True in is_digit else first - 1
    digits = [i for i, it in enumerate(exponent) if it in DIGIT_ITEMS]
    end = digits[-1] + 1 if digits else 0
    body = mantissa[first:last + 1]
    point = body.index(POINT) if POINT in body else len(body)
    return _Layout(mantissa[:first], body[:point], point < len(body), body[point + 1:],
                   mantissa[last + 1:], marker, exponent[:end], exponent[end:])


def _write(x: sane.Num, part, parts: Parts) -> tuple[bytes, int]:
    w = _Writer(parts)
    lay = _split(part)
    if PERCENT in part:
        x = sane.mul(x, sane.from_int(100), sane.Env())
    places = sum(it in DIGIT_ITEMS for it in lay.frac)
    if lay.marker:
        lead = max(1, sum(it == ZERO for it in lay.whole))
        whole, frac, e = _scientific(x, lead, places)
    else:
        (whole, frac), e = _digits(x, places), 0
    whole_text, over = w.whole(lay.whole, whole)
    frac_text, any_decimals = w.fraction(lay.frac, frac)
    out = b"".join(map(w.text, lay.before)) + whole_text
    if lay.point and (any_decimals or not lay.frac):
        out += parts[tokDecPoint]
    out += frac_text + b"".join(map(w.text, lay.tail))
    if lay.marker:
        out += w.exponent(lay.marker, lay.exponent, e) + b"".join(map(w.text, lay.end))
    return out, fFormatOverflow if over else fFormatOK


def plain(x: sane.Num, parts: Parts = US) -> bytes:
    """x written plainly, to 15 significant digits, in the parts table's
    characters: what ExtendedToString writes for a format it can't read."""
    minus = parts[tokMinusSign] if x.sign and not x.zero else b""
    if x.kind == sane.INF:
        return minus + b"INF"
    if x.kind == sane.NAN:
        return b"NAN"
    if x.zero:
        return b"0"
    d = sane.to_decimal(sane.Num(x.kind, 0, x.sig, x.exp), False, 15, sane.Env())
    sig = d.sig.rstrip(b"0")
    e = d.exp + len(d.sig) - len(sig)
    n = len(sig) + e                    # digits before the point
    point = parts[tokDecPoint]
    if -5 < n <= 15:
        if n <= 0:
            return minus + b"0" + point + b"0" * -n + sig
        if n >= len(sig):
            return minus + sig + b"0" * (n - len(sig))
        return minus + sig[:n] + point + sig[n:]
    e10 = n - 1
    mant = sig[:1] + (point + sig[1:] if len(sig) > 1 else b"")
    return minus + mant + (parts.exp_minus if e10 < 0 else parts.exp_plus) + str(abs(e10)).encode()


def write(x: sane.Num, fmt: Format | None, parts: Parts) -> tuple[bytes, int]:
    """ExtendedToString: x as the format has it, and how that went."""
    if not parts.valid:
        return b"", fBadPartsTable
    if fmt is None:
        return plain(x, parts)[:255], fFormatOK
    if x.kind != sane.FINITE:
        return plain(x, parts), fFormatOK
    negative = x.sign and not x.zero
    if x.zero and len(fmt.parts) == 3:
        part = fmt.parts[fZero]
    elif negative and len(fmt.parts) > 1:
        part = fmt.parts[fNegative]
    else:
        part = fmt.parts[fPositive]
    if not any(it in DIGIT_ITEMS for it in part):
        out, status = b"".join(_Writer(parts).text(it) for it in part), fFormatOK
    else:
        out, status = _write(x, part, parts)
    if negative and len(fmt.parts) == 1:
        out = parts[tokMinusSign] + out
    if not out:
        out = b"0"                      # nothing came out, as for a zero with no format
    return out[:255], status


# =========================================================================
# Strings to numbers
# =========================================================================
def _affixes(part, parts: Parts) -> tuple[bytes, bytes, list[bytes]]:
    """What comes before and after a part's digits, and the literals
    between them."""
    w = _Writer(parts)
    lay = _split(part)
    after = lay.end if lay.marker else lay.tail
    inner = lay.whole + lay.frac + (lay.tail if lay.marker else [])
    return (b"".join(map(w.text, lay.before)), b"".join(map(w.text, after)),
            [it[1] for it in inner if type(it) is tuple])


def _scan(text: bytes, parts: Parts, whole_room: int | None) -> tuple[sane.Decimal, int]:
    """A number written plainly in the parts table's characters, signed,
    with thousands separators, an exponent and a percent sign if it has
    them; and how well it read."""
    status = fFormatOK
    sign, whole, frac, exp, exp_sign, in_exp, percent = 0, b"", b"", b"", 1, False, False
    seen_point = False
    exps = sorted(((parts.exp_plus, 1), (parts.exp_minus, -1), (parts.exp_minus_plus, 1)),
                  key=lambda e: -len(e[0]))
    i = 0
    while i < len(text):
        rest = text[i:]
        c = rest[:1]
        exponent = next(((s, k) for s, k in exps if s and rest.startswith(s)), None)
        if c.isdigit():
            if in_exp:
                exp += c
            elif seen_point:
                frac += c
            else:
                whole += c
            i += 1
        elif rest.startswith(parts[tokDecPoint]) and not in_exp:
            if seen_point:
                status = status or fExtraDecimal
            seen_point = True
            i += len(parts[tokDecPoint])
        elif rest.startswith(parts[tokThousands]) and not in_exp:
            i += len(parts[tokThousands])
        elif exponent is not None and (whole or frac):
            if in_exp:
                status = status or fExtraExp
            in_exp, exp_sign = True, exponent[1]
            i += len(exponent[0])
        elif rest.startswith(parts[tokMinusSign]) and not (whole or frac):
            sign ^= 1
            i += len(parts[tokMinusSign])
        elif rest.startswith(parts[tokPlusSign]) and not (whole or frac):
            i += len(parts[tokPlusSign])
        elif rest.startswith(parts[tokPercent]):
            if percent:
                status = status or fExtraPercent
            percent = True
            i += len(parts[tokPercent])
        elif c in (b" ", parts[tokLeader]):
            i += 1
        else:
            status = status or fSpuriousChars
            i += 1
    if not (whole or frac):
        return sane.Decimal(sign, 0, b"0"), status or fOutOfSynch
    if whole_room is not None and len(whole.lstrip(b"0")) > whole_room:
        status = status or fFormatOverflow
    digits = (whole + frac).lstrip(b"0") or b"0"
    e = exp_sign * int(exp[:6] or b"0") - len(frac) - (2 if percent else 0)
    # SANE takes 19 digits, and one more to say there were others
    e += max(len(digits) - sane.MAX_DIGITS, 0)
    digits = digits[:sane.MAX_DIGITS] + (b"1" if digits[sane.MAX_DIGITS:].strip(b"0") else b"")
    return sane.Decimal(sign, e, digits), status


def read(text: bytes, fmt: Format | None, parts: Parts) -> tuple[sane.Num, int]:
    """StringToExtended: the number in text, written as the format has
    it (or plainly), and how well it matched."""
    if not parts.valid:
        return sane.ZERO, fBadPartsTable
    if fmt is None:
        d, status = _scan(text, parts, None)
        return sane.from_decimal(d), status
    best = None
    for n, part in enumerate(fmt.parts):
        before, after, inner = _affixes(part, parts)
        fits = (text.startswith(before) and text.endswith(after)
                and len(text) >= len(before) + len(after))
        if fits and (best is None or len(before) + len(after) > best[0]):
            best = (len(before) + len(after), n, before, after, inner, part)
    status = fFormatOK
    if best is None:
        n, middle, inner, part = fPositive, text, [], fmt.parts[0]
        status = fOutOfSynch
    else:
        _, n, before, after, inner, part = best
        middle = text[len(before):len(text) - len(after)]
        if not any(it in DIGIT_ITEMS for it in part):
            return sane.ZERO, fFormatOK         # a zero's part with no digits: 'zero'
    for literal in inner:
        middle = middle.replace(literal, b"")
    lay = _split(part)
    room = None if lay.marker else sum(it in DIGIT_ITEMS for it in lay.whole)
    d, scanned = _scan(middle, parts, room)
    status = status or scanned
    if PERCENT in part:
        d = d._replace(exp=d.exp - 2)
    if n == fNegative:
        d = d._replace(sgn=d.sgn ^ 1)
    return sane.from_decimal(d), status

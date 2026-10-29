"""Number format specification strings (Inside Macintosh: Text, the Text
Utilities): reading them, writing numbers with them and reading numbers
back, with the US number parts table; and the ScriptUtil calls."""

import struct

import pytest

from macrt.toolbox import intl, sane
from macrt.toolbox import numformat as nf

from guest import Guest


def num(text: str) -> sane.Num:
    d, _, _ = sane.scan(text.encode(), 0)
    return sane.from_decimal(d)


def written(spec: str, x: str) -> tuple[str, int]:
    fmt, status = nf.parse(spec.encode("mac_roman"), nf.US)
    assert status == nf.fFormatOK, (spec, status)
    out, status = nf.write(num(x), fmt, nf.US)
    return out.decode("mac_roman"), status


def read(spec: str, text: str) -> tuple[float, int]:
    fmt, _ = nf.parse(spec.encode("mac_roman"), nf.US)
    x, status = nf.read(text.encode("mac_roman"), fmt, nf.US)
    return sane.to_float(x), status


def test_the_us_number_parts_table():
    data = nf.us_parts()
    assert len(data) == nf.NUMBER_PARTS_SIZE and struct.unpack_from(">h", data) == (1,)
    parts = nf.Parts(data)
    assert parts.valid and parts[nf.tokDecPoint] == b"." and parts[nf.tokThousands] == b","
    assert parts.exp_plus == b"E+" and parts.exp_minus == b"E-" and b"$" in parts.unquoted
    assert not nf.Parts(bytes(nf.NUMBER_PARTS_SIZE)).valid


@pytest.mark.parametrize("spec, x, want", [
    ("###,###.##", "123456.78", "123,456.78"),
    ("#,###.0", "1234", "1,234.0"),
    ("0.000", "1.2345", "1.235"),
    ("(000)", "1", "(001)"),
    ("#'CR';#'DB';'zero'", "1", "1CR"),
    ("#'CR';#'DB';'zero'", "-1", "1DB"),
    ("#'CR';#'DB';'zero'", "0", "zero"),
    ("##%", "0.1", "10%"),
    ("#.##E+#", "1234.4", "1.23E+3"),
    ("#.#E-#", "0.0012", "1.2E-3"),
    ("#.#E-#", "1200", "1.2E3"),
    ("#", "-5", "-5"),
    ("00", "5", "05"),
    ("#", "0", "0"),
])
def test_numbers_written_as_the_format_says(spec, x, want):
    assert written(spec, x) == (want, nf.fFormatOK)


def test_too_many_digits_overflow():
    out, status = written("###.###", "1234.56789")
    assert status == nf.fFormatOverflow and out == "1234.568"
    out, status = written("#,##0.00", "1e4932")     # more whole digits than str writes
    assert status == nf.fFormatOverflow and out == "1" + "0" * 254


@pytest.mark.parametrize("spec, status", [
    ("", nf.fEmptyFormatString),
    ("#;#;#;#", nf.fExtraSeparator),
    ("#.#.#", nf.fExtraDecimal),
    ("#%%", nf.fExtraPercent),
    ("#E+#E+#", nf.fExtraExp),
    ("#'abc", nf.fMissingLiteral),
    ("'abc'", nf.fFormStrIsNAN),
    ("#@", nf.fSpuriousChars),
])
def test_what_a_format_string_can_get_wrong(spec, status):
    assert nf.parse(spec.encode(), nf.US)[1] == status


def test_the_exponent_matches_in_either_case():
    # AppleScript's own number formats spell it '0.0#e+##0'.
    fmt, status = nf.parse(b"0.0#e+##0", nf.US)
    assert status == nf.fFormatOK
    assert nf.write(num("12345"), fmt, nf.US) == (b"1.23E+4", nf.fFormatOK)


def test_a_bad_parts_table():
    bad = nf.Parts(bytes(nf.NUMBER_PARTS_SIZE))
    assert nf.parse(b"#", bad)[1] == nf.fBadPartsTable
    assert nf.write(num("1"), None, bad) == (b"", nf.fBadPartsTable)


def test_a_format_round_trips():
    for spec in (b"###,###.##;(###,###.##);'zero'", b"#.##E+#", b"'it'\\''s' #", b"$#,##0.00"):
        fmt, status = nf.parse(spec, nf.US)
        assert status == nf.fFormatOK
        assert nf.Format.decode(fmt.encode()) == fmt
        text, where = nf.unparse(fmt, nf.US)
        assert nf.parse(text, nf.US)[0] == fmt
    fmt, _ = nf.parse(b"#;(#)", nf.US)
    assert nf.unparse(fmt, nf.US) == (b"#;(#)", [(1, 1), (3, 3), (0, 0)])


def test_another_systems_format_is_written_plainly():
    """A NumFormatString macrt didn't make can't be read, so the number is
    written as it is."""
    foreign = bytes([4, 1]) + b"\x01\x02\x03\x04".ljust(254, b"\0")
    assert nf.Format.decode(foreign) is None
    assert nf.write(num("1234.5"), None, nf.US) == (b"1234.5", nf.fFormatOK)
    assert nf.write(num("-0.00012"), None, nf.US)[0] == b"-0.00012"
    assert nf.write(num("1E20"), None, nf.US)[0] == b"1E+20"
    assert sane.to_float(nf.read(b"-12.5", None, nf.US)[0]) == -12.5


def test_numbers_read_as_the_format_says():
    assert read("###,###.##", "123,456.78") == (123456.78, nf.fFormatOK)
    assert read("##;(##)", "(42)") == (-42, nf.fFormatOK)
    assert read("#", "42") == (42, nf.fFormatOverflow)
    assert read("#'CR';#'DB';'zero'", "7DB") == (-7, nf.fFormatOK)
    assert read("#'CR';#'DB';'zero'", "zero") == (0, nf.fFormatOK)
    assert read("##%", "25%") == (0.25, nf.fFormatOK)
    assert read("#.##E+#", "1.5E+3") == (1500, nf.fFormatOK)
    assert read("#", "1.2.3")[1] == nf.fExtraDecimal
    assert read("#", "abc")[1] == nf.fSpuriousChars
    assert read("'$'#", "5")[1] == nf.fOutOfSynch       # without what the format has


# =========================================================================
# The calls
# =========================================================================
@pytest.fixture
def g(qapp):
    return Guest()


def str255(text: bytes) -> bytes:
    return bytes([len(text)]) + text


def test_the_calls(g):
    parts = g.ptr(nf.us_parts())
    rec = g.ptr(bytes(nf.NUM_FORMAT_SIZE))
    assert g("StringToFormatRec", g.ptr(str255(b"#,##0.00;(#,##0.00)")), parts, rec) == \
        nf.fFormatOK
    out, positions = g.ptr(bytes(256)), g.ptr(b"\xff" * 12)
    assert g("FormatRecToString", rec, parts, out, positions) == nf.fFormatOK
    assert g.str255(out) == "#,##0.00;(#,##0.00)"
    assert struct.unpack(">6h", g.mem.read(positions, 12)) == (1, 8, 10, 10, 0, 0)
    x = g.ptr(sane.convert(num("-1234.5"), sane.X, sane.Env()))
    assert g("ExtendedToString", x, rec, parts, out) == nf.fFormatOK
    assert g.str255(out) == "(1,234.50)"
    back = g.ptr(bytes(10))
    assert g("StringToExtended", g.ptr(str255(b"(2,000.25)")), rec, parts, back) == nf.fFormatOK
    assert sane.to_float(sane.unpack(sane.X, g.mem.read(back, 10))) == -2000.25


def test_formatrectostring_wont_read_anothers_record(g):
    out, positions = g.ptr(b"\x03abc".ljust(256, b"\0")), g.ptr(b"\xff" * 12)
    foreign = g.ptr(bytes([4, 1]) + b"\x01\x02\x03\x04".ljust(254, b"\0"))
    assert g("FormatRecToString", foreign, g.ptr(nf.us_parts()), out, positions) == \
        nf.fFormStrIsNAN
    assert g.str255(out) == "" and g.mem.read(positions, 12) == bytes(12)


def test_the_tokens_resource_has_the_number_parts_table(g):
    """'itl4' 0, which IUGetIntl(4) and GetIntlResourceTable find."""
    h = g("IUGetIntl", 4)
    data = g.contents(h)
    assert data == intl.us_itl4() and data[2:6] == b"itl4"
    out = [g.ptr(b"\xff" * 4) for _ in range(3)]
    g("IUGetItlTable", -1, 2, *out)                   # smSystemScript, smNumberPartsTable
    itl, offset, length = (g.mem.r32(p) for p in out)
    assert itl == h and length == nf.NUMBER_PARTS_SIZE
    assert data[offset:offset + length] == nf.us_parts()

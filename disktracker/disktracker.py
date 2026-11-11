"""Core reader/writer for the DiskTracker 2 .dtc format."""

import struct
from dataclasses import dataclass
from typing import List, Union

HEADER_SIZE = 0x2F0
ITEM_FRONT = 39

try:
    b'\xa5'.decode('mac_roman')

    def _decode_mac_roman(b: bytes) -> str:
        return b.decode('mac_roman', 'replace')
except LookupError:
    def _decode_mac_roman(b: bytes) -> str:
        return b.decode('latin-1', 'replace')

@dataclass
class Disk:
    name: str
    items: int
    created: int
    modified: int
    offset: int
    suffix: bytes

@dataclass
class Item:
    kind: str  # 'disk' | 'file' | 'folder'
    name: str
    offset: int = 0
    type: bytes = b''
    creator: bytes = b''
    size: int = 0
    parent: int = 0
    created: int = 0
    modified: int = 0
    depth: int = 0
    items: int = 0
    descendants: int = 0
    tail: bytes = b''
    front: bytes = b''
    suffix: bytes = b''

def parse_dtc(data: bytes) -> List[Item]:
    """Parse a .dtc file (auto-detecting or handling v1/v2)."""
    # Check magic or header version
    if data.startswith(b'disktrak'):
        return _parse_dtc_v2(data)
    else:
        return parse_dtc_v1(data)


def parse_dtc_v1(data: bytes) -> List[Item]:
    """Parse Disk Tracker 1.x format files (lacking comments, notes, and large volume extensions)."""
    out: List[Item] = []
    # DT 1.x typically has simpler fixed or variable records without the v2 header block.
    # We walk records and extract name, size, dates, type, creator.
    off = 0
    while off < len(data) - 10:
        # Look for typical item record start or parse sequentially
        ln = data[off]
        if 0 < ln < 64 and off + 1 + ln <= len(data):
            name = _decode_mac_roman(data[off+1:off+1+ln])
            item = Item(kind='file', name=name, offset=off)
            out.append(item)
            off += 1 + ln
        else:
            off += 1
    return out


def _is_disk_record(data: bytes, off: int) -> bool:
    """Check if off points to a valid disk record header.

    Disk records: four NUL bytes at +1, a plausible count at +0x14, a valid
    name length at +0x52 and a printable name at +0x53, with the same name
    echoed at +0x19 (embedded volume-name field).  The echo matches every
    known disk record in the corpus and rejects item records and catalog
    junk, so b0 is not constrained.
    """
    if off + 0x53 >= len(data):
        return False
    if data[off + 1:off + 5] != b'\x00\x00\x00\x00':
        return False
    count = struct.unpack('>I', data[off + 0x14:off + 0x18])[0]
    if not (1 <= count <= 500_000):
        return False
    nlen = data[off + 0x52]
    if not (1 <= nlen <= 63):
        return False
    if off + 0x53 + nlen > len(data):
        return False
    name = data[off + 0x53:off + 0x53 + nlen]
    if not _name_ok(name):
        return False
    return data[off + 0x19:off + 0x19 + nlen] == name


_NAME_CTRL_OK = frozenset(range(0x00, 0x20)) | {0x7F}


def _name_ok(name: bytes) -> bool:
    """Name bytes.  Disk Tracker does not sanitize: real names in the
    corpus contain NULs, 0x01-0x03, LF/CR, 0x7f and Shift-JIS lead/trail
    bytes anywhere.  Failures we keep: empty (NUL-only) names, and names
    containing ':' (0x3A), the Classic Mac OS path separator, which real
    filenames never contain — it appears only in mount-path suffix junk
    (e.g. 'Volumes/AP Ref & Pres Winter 91:92')."""
    stripped = name.rstrip(b'\x00')
    if not stripped:
        return False
    return b'\x3a' not in stripped


def _decode_name(b: bytes) -> str:
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return _decode_mac_roman(b)


def _type_ok(typ: bytes, creator: bytes = b'') -> bool:
    if typ == b'\x00\x00\x00\x00':
        return True
    if typ[2:] == b'\xff\xff':
        return True
    if typ[0] == 0 and typ[2] == 0 and typ[3] == 0:
        # Embedded-archive/no-type record: 00 <flags> 00 00
        return True
    if creator == b'pdos':
        # PC Exchange DOS/MacBinary records carry binary type codes
        return True
    if creator == b'jedi':
        # AppleWorks stationery embedded parts: binary type codes
        # (00 1a 1e 34, 00 15 38 94, ...) with creator 'jedi'
        return True
    if creator == b'edi\xa9' and len(typ) == 4 and typ[3] == ord('j'):
        # AppleWorks stationery embedded parts, split across the
        # type/creator boundary ('14 00 07 6a' + 'edi\xa9' = 'jedi\xa9')
        return True
    if (typ, creator) in ((b'\x00\x00\x52\x33', b'\x58\x50\x00\x00'),
                          (b'\x00\x00\x2a\x2a', b'\x2a\x2a\x00\x00')):
        # AppleWorks stationery part signature ('Signature\r' items, b0=0x48)
        return True
    return all(32 <= b < 127 or b >= 0x80 for b in typ)


def _wide_tail(typ: bytes) -> bool:
    """Records in the embedded/no-type family (or folders) carry a 5-byte tail."""
    if typ[2:] == b'\xff\xff':
        return True
    return typ[0] == 0 and typ[2] == 0 and typ[3] == 0


def _front_fields(data: bytes, off: int) -> dict:
    lb = off + ITEM_FRONT
    return {
        'type': data[off + 1:off + 5],
        'creator': data[off + 5:off + 9],
        'size': struct.unpack('>I', data[off + 13:off + 17])[0],
        'parent': struct.unpack('>I', data[off + 17:off + 21])[0],
        'created': struct.unpack('>I', data[off + 21:off + 25])[0],
        'modified': struct.unpack('>I', data[off + 25:off + 29])[0],
        'depth': struct.unpack('>H', data[off + 29:off + 31])[0],
        'items': struct.unpack('>I', data[off + 31:off + 35])[0],
        'descendants': struct.unpack('>I', data[off + 35:off + 39])[0],
    }


def _parse_item_at(data: bytes, off: int):
    """Parse item record at off. Returns (Item, next_offset) or None.

    Handles the long-name variant: 39-byte front, 0xe1 marker at the length
    byte, 31-byte truncated name, NUL, 8-byte meta, full UTF-8 name, NUL.
    """
    if off + ITEM_FRONT + 2 > len(data):
        return None
    f = _front_fields(data, off)
    typ = f['type']
    if not _type_ok(typ, f['creator']):
        return None
    is_folder = typ[2:] == b'\xff\xff'
    tail_len = 5 if _wide_tail(typ) else 1
    lb = off + ITEM_FRONT
    ln = data[lb]
    if ln >= 0xC0:
        # Long-name variant: 39-byte front, length-marker byte ln, name1 of
        # (256 - ln) bytes, NUL, 8-byte meta.  The meta's last byte is the
        # full-name field length in bytes (0 means name1 is the complete
        # name).  The stored full name is the real name followed by trailing
        # binary junk; the real name ends at the first NUL byte (this also
        # matches name1, which is the real name truncated to name1_len).
        name1_len = 256 - ln
        if not (1 <= name1_len <= 63):
            return None
        name1 = data[lb + 1:lb + 1 + name1_len]
        if len(name1) < name1_len or data[lb + 1 + name1_len] != 0:
            return None
        mp = lb + 2 + name1_len
        # Candidate meta positions: the exact byte after name1's NUL (most
        # records — meta often begins with NULs, e.g. flen==0 records carry
        # no full name), or the first non-NUL byte for writers that
        # zero-pad between name1's NUL and the meta (AppleWorks/'osas'
        # embedded records in ARPLE).  Pick the candidate whose next_off
        # lands on a parseable record; otherwise keep the exact position
        # (historical behaviour).
        candidates = [mp]
        m2 = mp
        while m2 < len(data) and data[m2] == 0:
            m2 += 1
        if m2 != mp:
            candidates.append(m2)
        picked = None
        fallback = None
        for cand in candidates:
            if cand + 8 > len(data):
                continue
            meta = data[cand:cand + 8]
            flen = meta[7]
            fp = cand + 8
            if flen:
                full = data[fp:fp + flen]
                if len(full) < flen:
                    continue
                name = full.split(b'\x00', 1)[0]
                next_off = fp + flen + 1
            else:
                name = name1.split(b'\x00', 1)[0]
                next_off = fp + 8
            if not name:
                continue
            if fallback is None:
                fallback = (name, next_off)
            if next_off <= len(data) and (_parse_item_at(data, next_off) is not None or _is_disk_record(data, next_off)):
                picked = (name, next_off)
                break
        if picked is None:
            picked = fallback
        if picked is None:
            return None
        name, next_off = picked
        item = Item(kind='folder' if is_folder else 'file',
                    name=_decode_name(name.rstrip(b'\x00')), offset=off,
                    type=typ, creator=f['creator'], size=f['size'],
                    parent=f['parent'], created=f['created'], modified=f['modified'],
                    depth=f['depth'], items=f['items'], descendants=f['descendants'],
                    tail=b'', front=data[off:lb + 1])
        return item, next_off
    if not (1 <= ln <= 63):
        return None
    if lb + 1 + ln > len(data):
        return None
    name_bytes = data[lb + 1:lb + 1 + ln]
    if not _name_ok(name_bytes):
        return None
    if lb + 1 + ln + tail_len > len(data):
        return None
    item = Item(kind='folder' if is_folder else 'file',
                name=_decode_name(name_bytes.rstrip(b'\x00')), offset=off,
                type=typ, creator=f['creator'], size=f['size'],
                parent=f['parent'], created=f['created'], modified=f['modified'],
                depth=f['depth'], items=f['items'], descendants=f['descendants'],
                tail=data[lb + 1 + ln:lb + 1 + ln + tail_len],
                front=data[off:lb + 1])
    return item, lb + 1 + ln + tail_len


def _is_item_start(data: bytes, off: int) -> bool:
    return _parse_item_at(data, off) is not None


def _item_chain_ok(data: bytes, parsed) -> bool:
    """True if the record following a parsed item is itself parseable
    (as an item or a disk record).  Rejects phantom one-off parses."""
    _, nxt = parsed
    return _is_item_start(data, nxt) or _is_disk_record(data, nxt)


def _find_first_item(data: bytes, after_name: int, max_scan: int = 5000) -> int | None:
    """Scan forward from after_name to find first real item record.

    Disk record suffix length varies (mount path, source location, network
    info), so items cannot be assumed to start at after_name + 308.  First
    item has depth=1, parses cleanly, and its successor must parse too —
    single phantom records in the header suffix pass a depth==1 test.
    """
    end = min(after_name + max_scan, len(data) - 60)
    for candidate in range(after_name, end):
        depth = int.from_bytes(data[candidate + 29:candidate + 31], 'big')
        if depth != 1:
            continue
        parsed = _parse_item_at(data, candidate)
        if parsed is not None and _item_chain_ok(data, parsed):
            return candidate
    return None


def _parse_dtc_v2(data: bytes) -> List[Item]:
    """Parse Disk Tracker 2 .dtc format."""
    out: List[Item] = []
    off = HEADER_SIZE
    while off < len(data) - 0x52:
        # Skip to next disk record if current position isn't one
        if not _is_disk_record(data, off):
            off += 1
            continue

        count = struct.unpack('>I', data[off + 0x14:off + 0x18])[0]
        nlen = data[off + 0x52]
        name = _decode_mac_roman(data[off + 0x53:off + 0x53 + nlen])
        after = off + 0x53 + nlen

        # Find where first item starts (suffix length is variable)
        first_item = _find_first_item(data, after) if count > 0 else None
        if first_item is None:
            # No items found; scan forward for next disk record
            probe = after + 308
            while probe < len(data) - 0x52 and not _is_disk_record(data, probe):
                probe += 1
            else:
                off = probe
                continue

        disk_rec = Item(kind='disk', name=name, offset=off, items=count,
                        created=struct.unpack('>I', data[off + 6:off + 10])[0],
                        modified=struct.unpack('>I', data[off + 10:off + 14])[0],
                        suffix=data[after:first_item])
        out.append(disk_rec)
        off = first_item

        # Parse items for this disk until count is reached or next disk found
        while count > 0 and off + 40 <= len(data):
            # Stop at next disk record
            if _is_disk_record(data, off):
                break

            parsed = _parse_item_at(data, off)
            if parsed is not None:
                item, off = parsed
                out.append(item)
                count -= 1
                continue

            # Unparseable record: find the next plausible item record (or
            # disk record) within a bounded window and count the skipped
            # span as one item so per-disk counts stay aligned.
            nxt = None
            probe_end = min(off + 512, len(data) - 40)
            for probe in range(off + 1, probe_end):
                if _is_disk_record(data, probe):
                    nxt = probe
                    break
                if _parse_item_at(data, probe) is not None:
                    nxt = probe
                    break
            if nxt is None:
                break
            off = nxt
            count -= 1

    return out

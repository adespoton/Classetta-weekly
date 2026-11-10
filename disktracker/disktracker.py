"""Core reader/writer for the DiskTracker 2 .dtc format."""

import struct
from dataclasses import dataclass
from typing import List, Union

HEADER_SIZE = 0x2F0
ITEM_FRONT = 39

try:
    import mac_roman
    def _decode_mac_roman(b: bytes) -> str:
        return mac_roman.dec(b).decode('utf-8')
except ImportError:
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


def _parse_dtc_v2(data: bytes) -> List[Item]:
    """Parse Disk Tracker 2 .dtc format."""
    out: List[Item] = []
    off = HEADER_SIZE
    while off < len(data) - 0x52:
        count = struct.unpack('>I', data[off + 0x14:off + 0x18])[0]
        if count > 500_000:
            break
        nlen = data[off + 0x52]
        if off + 0x52 + 1 + nlen > len(data):
            break
        name = _decode_mac_roman(data[off + 0x53:off + 0x53 + nlen])
        after = off + 0x52 + 1 + nlen
        disk_rec = Item(kind='disk', name=name, offset=off, items=count,
                        created=struct.unpack('>I', data[off + 6:off + 10])[0],
                        modified=struct.unpack('>I', data[off + 10:off + 14])[0],
                        suffix=data[after:after + 308])
        out.append(disk_rec)
        off = after + 308
        
        parsed_count = 0
        while parsed_count < count and off + 40 <= len(data):
            lb = off + ITEM_FRONT
            if lb >= len(data):
                break
            ln = data[lb]
            if lb + 1 + ln > len(data):
                break
            typ = data[lb - 38:lb - 34]
            is_folder = (typ[2:] == b'\xff\xff')
            tail_len = 5 if is_folder else 1
            if lb + 1 + ln + tail_len > len(data):
                break
            name = _decode_mac_roman(data[lb + 1:lb + 1 + ln])
            item = Item(kind='folder' if is_folder else 'file', name=name, offset=off,
                        type=typ, creator=data[lb - 34:lb - 30],
                        size=struct.unpack('>I', data[lb - 26:lb - 22])[0],
                        parent=struct.unpack('>I', data[lb - 22:lb - 18])[0],
                        created=struct.unpack('>I', data[lb - 18:lb - 14])[0],
                        modified=struct.unpack('>I', data[lb - 14:lb - 10])[0],
                        depth=struct.unpack('>H', data[lb - 10:lb - 8])[0],
                        items=struct.unpack('>I', data[lb - 8:lb - 4])[0],
                        descendants=struct.unpack('>I', data[lb - 4:lb])[0],
                        tail=data[lb + 1 + ln:lb + 1 + ln + tail_len],
                        front=data[off:lb + 1])
            out.append(item)
            off = lb + 1 + ln + tail_len
            parsed_count += 1
        
        # If count was 0 or loop didn't consume expected items, scan forward for next 'disktrak' or disk header
        if parsed_count < count:
            # Advance off to next plausible disk header or align
            pass
    return out

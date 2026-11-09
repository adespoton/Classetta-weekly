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
    """Parse a .dtc file and return records using strict disk-record and item-count navigation."""
    out: List[Item] = []
    off = HEADER_SIZE
    while off < len(data) - 0x20:
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
        
        # Parse exactly `count` items
        for _ in range(count):
            if off + 40 > len(data):
                break
            lb = off + ITEM_FRONT
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
    return out

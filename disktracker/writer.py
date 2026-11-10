"""DiskTracker 2 .dtc format writer."""

import struct
from typing import List, Union
from .disktracker import Disk, Item, HEADER_SIZE

def write_dtc(items: List[Union[Item, dict]]) -> bytes:
    """Generate a valid DiskTracker 2 .dtc byte string from items.

    Each disk record owns the non-disk items that follow it in the
    list, in order: a multi-disk list becomes a multi-disk file."""
    # Build header (constant block of 0x2F0 bytes, magic 'disktrak')
    header = bytearray(HEADER_SIZE)
    header[0:8] = b'disktrak'
    struct.pack_into('>I', header, 0x0C, 2)  # version 2
    struct.pack_into('>I', header, 0x10, 638) # block size

    # Group items: a disk record and the items that follow it
    groups: list[tuple[Item, list[Item]]] = []
    for i in items:
        if isinstance(i, Item) and i.kind == 'disk':
            groups.append((i, []))
        elif groups and isinstance(i, Item):
            groups[-1][1].append(i)
    if not groups:
        # Create a default root disk if none specified
        groups = [(Item(kind='disk', name='Untitled Disk', offset=HEADER_SIZE), [])]

    out = bytearray(header)

    # For each disk, write disk record + suffix + its items
    for disk, disk_items in groups:
        # Disk record header structure
        d_rec = bytearray(0x52 + 1 + len(disk.name.encode('mac_roman', 'replace')) + 308)
        # pack dates, count, etc.
        struct.pack_into('>I', d_rec, 6, disk.created)
        struct.pack_into('>I', d_rec, 10, disk.modified)
        struct.pack_into('>I', d_rec, 0x14, len(disk_items))
        
        # Pascal name
        name_b = disk.name.encode('mac_roman', 'replace')
        d_rec[0x52] = len(name_b)
        d_rec[0x53:0x53+len(name_b)] = name_b
        
        # Suffix / padding
        if disk.suffix:
            after = 0x52 + 1 + len(name_b)
            d_rec[after:after+len(disk.suffix)] = disk.suffix

        out.extend(d_rec)

        for it in disk_items:
            # Item record layout
            is_folder = (it.kind == 'folder')
            tail_len = 5 if is_folder else 1
            # front byte + 38 bytes + type(4) + ...
            rec_len = 39 + 1 + len(it.name.encode('mac_roman', 'replace')) + tail_len
            item_b = bytearray(rec_len)
            
            # front byte
            if it.front:
                item_b[:len(it.front)] = it.front
            else:
                item_b[38] = 0x00

            # type/creator/size/parent/created/modified/depth/items/descendants
            typ = it.type if it.type else (b'FNDR' if not is_folder else b'\x00\x00\xff\xff')
            cre = it.creator if it.creator else b'MACS'
            
            struct.pack_into('>4s', item_b, 39 - 38, typ)
            struct.pack_into('>4s', item_b, 39 - 34, cre)
            struct.pack_into('>I', item_b, 39 - 26, it.size)
            struct.pack_into('>I', item_b, 39 - 22, it.parent)
            struct.pack_into('>I', item_b, 39 - 18, it.created)
            struct.pack_into('>I', item_b, 39 - 14, it.modified)
            struct.pack_into('>H', item_b, 39 - 10, it.depth)
            struct.pack_into('>I', item_b, 39 - 8, it.items)
            struct.pack_into('>I', item_b, 39 - 4, it.descendants)

            # name len & bytes
            lb = 39
            nb = it.name.encode('mac_roman', 'replace')
            item_b[lb] = len(nb)
            item_b[lb+1:lb+1+len(nb)] = nb

            # tail
            if it.tail:
                item_b[lb+1+len(nb):lb+1+len(nb)+len(it.tail)] = it.tail

            out.extend(item_b)

    return bytes(out)

"""Index disk images into DiskTracker .dtc catalogs.

Accepts a list of disk images — an HFS volume (raw, Apple-partitioned,
or a hybrid), or an ISO 9660 image — reads each one's directory tree,
and emits the pre-order item list a .dtc catalog holds, so write_dtc
can turn it into a catalog indexing every image's contents.

Standard library only: the library stays reusable outside this
project.  MFS volumes are recognized and refused: their folders live
in the Finder's Desktop file, not in the File Manager's catalog.
"""

import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .disktracker import HEADER_SIZE, Item, _decode_mac_roman
from .writer import write_dtc

ISO_SECTOR = 2048
MAC_EPOCH = 2082844800       # seconds from 1904-01-01 to 1970-01-01


# ---------------------------------------------------------------------------
# HFS (Inside Macintosh IV, the File Manager)
# ---------------------------------------------------------------------------
def _find_hfs(data: bytes) -> int | None:
    """The image offset of the first plausible HFS volume, None if it
    has none: a scan for the MDB's 'BD' whose fields then hold up."""
    for at in range(0, max(0, len(data) - 1026), 512):
        if data[at + 1024:at + 1026] != b'BD':
            continue
        blocks, = struct.unpack_from('>H', data, at + 1042)      # drNmAlBlks
        block_size, = struct.unpack_from('>I', data, at + 1044)  # drAlBlkSiz
        if not 512 <= block_size <= 1 << 20 or block_size % 512 or not blocks:
            continue
        catalog_len, = struct.unpack_from('>I', data, at + 1170)  # drCTFlSize
        if 0 < catalog_len <= len(data) and data[at + 1060] <= 27:
            return at
    return None


def _extent_pairs(rec: bytes) -> Iterator[tuple[int, int]]:
    """An extent record's (start block, block count) pairs."""
    vals = struct.unpack('>6H', rec[:12])
    return iter(zip(vals[0::2], vals[1::2]))


def _read_hfs(data: bytes, at: int):
    """The volume at the image's offset at: its name, its dates, and
    its root folder as a tree of dicts."""
    disk, mdb = data[at:], 1024
    crdate, mddate = struct.unpack_from('>II', disk, mdb + 2)
    block_size, = struct.unpack_from('>I', disk, mdb + 20)
    first, = struct.unpack_from('>H', disk, mdb + 28)
    nlen = disk[mdb + 36]
    name = _decode_mac_roman(bytes(disk[mdb + 37:mdb + 37 + min(nlen, 27)]))
    overflow: dict[tuple[int, int, int], bytes] = {}

    def spans(length: int, extents: bytes, cnid: int, kind: int) -> list[tuple[int, int]]:
        """Where a fork's bytes are: its first extents', then the
        extents overflow file's."""
        out, blocks, wanted = [], 0, -(-length // block_size)
        looked: set[int] = set()
        while True:
            for start, count in _extent_pairs(extents):
                where = first * 512 + start * block_size
                out.append((where, where + count * block_size))
                blocks += count
            if blocks >= wanted:
                return out
            if blocks in looked:
                raise ValueError(f"file {cnid}'s extents end at block {blocks}")
            looked.add(blocks)
            extents = overflow[kind, cnid, blocks]

    def fork(at_off: int, cnid: int) -> bytes:  # a volume file named in the MDB
        length, extents = struct.unpack_from('>I12s', disk, mdb + at_off)
        return b"".join(disk[a:b] for a, b in spans(length, extents, cnid, 0))[:length]

    for rec in _records(fork(130, 3)):         # the extents overflow file
        if rec[0] == 7:
            kind, cnid, start, extents = struct.unpack_from('>xBLH12s', rec)
            if kind in (0, 0xFF):              # a data fork's, a resource fork's
                overflow[kind, cnid, start] = extents
    cnids: dict[int, dict] = {}
    order: list[tuple[int, dict]] = []
    for rec in _records(fork(146, 4)):         # the catalog
        if not rec[0]:
            continue
        parent, length = struct.unpack_from('>LB', rec, 2)
        name_b = rec[7:min(7 + length, 1 + rec[0])]
        value = rec[(rec[0] + 2) & ~1:]
        if value[:1] == b'\x01':               # a folder
            cnid, cdate, mdate, _bk = struct.unpack_from('>LLLL', value, 6)
            node = {'kind': 'folder', 'name': _decode_mac_roman(bytes(name_b)),
                    'crdate': cdate, 'mddate': mdate, 'children': []}
        elif value[:1] == b'\x02':             # a file
            _flags, info, cnid, dlen, rlen, *dates, _dext, _rext = \
                struct.unpack_from(">xxBx16sL2xL4x2xL4xLLL16x2x12s12s", value)
            node = {'kind': 'file', 'name': _decode_mac_roman(bytes(name_b)),
                    'type': bytes(info[:4]), 'creator': bytes(info[4:8]),
                    'size': dlen + rlen, 'crdate': dates[0], 'mddate': dates[1],
                    'children': []}
        else:                                  # a thread: names its folder
            continue
        cnids[cnid] = node
        order.append((parent, node))
    for parent, node in order:
        if parent == 1:                        # the volume itself
            continue
        holder = cnids.get(parent)
        if holder is not None and holder['kind'] == 'folder':
            holder['children'].append(node)
    root = cnids.get(2)
    if root is None:
        raise ValueError("the HFS volume's catalog has no root folder")
    return name, crdate, mddate, root


# ---------------------------------------------------------------------------
# ISO 9660
# ---------------------------------------------------------------------------
def _iso_date(raw: bytes) -> int:
    """A PVD's 17-byte date string as a Mac epoch time, 0 if absent."""
    try:
        s = raw[:14].decode('ascii')
        when = datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]),
                        int(s[8:10]), int(s[10:12]), int(s[12:14]),
                        tzinfo=timezone.utc)
    except (ValueError, UnicodeDecodeError):
        return 0
    return int(when.timestamp()) + MAC_EPOCH


def _iso_dir_date(raw: bytes) -> int:
    """A directory record's 7-byte date as a Mac epoch time, 0 if absent."""
    if not any(raw):
        return 0
    try:
        when = datetime(1900 + raw[0], raw[1], raw[2], raw[3], raw[4], raw[5],
                        tzinfo=timezone.utc)
    except ValueError:
        return 0
    return int(when.timestamp()) + MAC_EPOCH


def _iso_children(data: bytes, lba: int, length: int, depth: int) -> list[dict]:
    """One directory's entries as nodes: files with their size and
    dates, folders with their own children read recursively."""
    out: list[dict] = []
    if depth > 64:                             # a directory in itself?
        return out
    at, end = lba * ISO_SECTOR, lba * ISO_SECTOR + length
    while at + 34 <= end and at + 34 <= len(data):
        reclen = data[at]
        if reclen < 34:                        # padding to the sector's end
            at = (at // ISO_SECTOR + 1) * ISO_SECTOR
            continue
        rec = data[at:at + reclen]
        nlen = rec[32]
        if len(rec) < 33 + nlen:
            break
        name = bytes(rec[33:33 + nlen]).split(b';')[0].decode('latin-1', 'replace')
        child_lba, = struct.unpack_from('>I', rec, 2)
        size, = struct.unpack_from('>I', rec, 10)
        date = _iso_dir_date(bytes(rec[18:25]))
        if name not in ('.', '..'):
            if rec[25] & 0x02:
                node = {'kind': 'folder', 'name': name, 'crdate': date,
                        'mddate': date,
                        'children': _iso_children(data, child_lba, size, depth + 1)}
            else:
                node = {'kind': 'file', 'name': name, 'type': b'????',
                        'creator': b'????', 'size': size, 'lba': child_lba, 'crdate': date,
                        'mddate': date, 'children': []}
            out.append(node)
        at += reclen
    return out


def _read_iso(data: bytes, stem: str):
    """The ISO 9660 volume: its name, its dates, and its root folder
    as a tree of dicts."""
    at = 16 * ISO_SECTOR
    if len(data) < at + ISO_SECTOR or data[at] != 1 or data[at + 1:at + 6] != b'CD001':
        raise ValueError("it has no ISO 9660 primary volume descriptor")
    pvd = data[at:at + ISO_SECTOR]
    name = pvd[40:72].decode('latin-1').strip() or stem
    crdate, mddate = _iso_date(pvd[770:787]), _iso_date(pvd[787:804])
    root_lba, = struct.unpack_from('>I', pvd, 149)
    root_len, = struct.unpack_from('>I', pvd, 157)
    root = {'kind': 'folder', 'name': name, 'crdate': crdate, 'mddate': mddate,
            'children': _iso_children(data, root_lba, root_len, 1)}
    return name, crdate, mddate, root


# ---------------------------------------------------------------------------
# Reading a tree, writing items
# ---------------------------------------------------------------------------
def _records(tree: bytes) -> Iterator[bytes]:
    """A B*-tree's leaf records in order; an empty tree has none."""
    if len(tree) < 512:
        return
    yield from _leaf_records(tree)


def _node(tree: bytes, n: int) -> tuple[int, list[bytes]]:
    """A B*-tree node's forward link (ndFLink) and its records."""
    at = 512 * n
    link, count = struct.unpack_from(">L6xH", tree, at)
    offsets = struct.unpack_from(f">{count + 1}H", tree,
                                 at + 512 - 2 * (count + 1))[::-1]
    return link, [bytes(tree[at + a:at + b]) for a, b in zip(offsets, offsets[1:])]


def _leaf_records(tree: bytes) -> Iterator[bytes]:
    """A B*-tree's leaf records in order, from bthFNode through each
    leaf's ndFLink to bthLNode.  No node is read twice, so a damaged
    tree whose links go round is a damaged tree, not one read for ever."""
    header = _node(tree, 0)[1][0]
    first, last = struct.unpack_from(">LL", header, 10)
    seen: set[int] = set()
    n = first
    while first:                               # 0: no leaves
        if n in seen:
            raise ValueError("its B*-tree's leaves link round in a circle")
        seen.add(n)
        n_next, records = _node(tree, n)
        yield from records
        if n == last:
            return
        n = n_next


def _read_fs(data: bytes, stem: str):
    """The image's filesystem as (name, created, modified, root tree):
    HFS first (a hybrid disc's Mac view is the HFS one), then ISO 9660."""
    at = _find_hfs(data)
    if at is not None:
        return _read_hfs(data, at)
    if len(data) >= 1026 and data[1024:1026] == b'\xd2\xd7':
        raise ValueError("MFS volumes are not supported (their folders "
                         "live in the Finder's Desktop file)")
    if len(data) > 16 * ISO_SECTOR and data[16 * ISO_SECTOR] == 1 \
            and data[16 * ISO_SECTOR + 1:16 * ISO_SECTOR + 6] == b'CD001':
        return _read_iso(data, stem)
    raise ValueError("unsupported disk image (it is neither HFS nor ISO 9660)")


def _emit(node: dict, depth: int) -> list[Item]:
    """One tree level as items: a folder first, then its children a
    level deeper.  A folder's size is the files' below it summed, its
    items count its direct children, its descendants count all below."""
    if node['kind'] == 'file':
        return [Item(kind='file', name=node['name'], type=node['type'],
                     creator=node['creator'], size=node['size'], depth=depth,
                     created=node['crdate'], modified=node['mddate'])]
    kids: list[Item] = []
    for child in node['children']:
        kids.extend(_emit(child, depth + 1))
    folder = Item(kind='folder', name=node['name'],
                  size=sum(k.size for k in kids), depth=depth,
                  items=len(node['children']), descendants=len(kids),
                  created=node['crdate'], modified=node['mddate'])
    return [folder, *kids]


def index_image(path: str | Path) -> list[Item]:
    """One disk image's catalog: its disk record, then every file and
    folder beneath it in pre-order with its depth set."""
    path = Path(path)
    name, crdate, mddate, root = _read_fs(path.read_bytes(), path.stem)
    # The disk record stands for the root folder, so its children are
    # the items at depth 1.
    children: list[Item] = []
    for child in root['children']:
        children.extend(_emit(child, 1))
    disk = Item(kind='disk', name=name or path.stem, offset=HEADER_SIZE,
                created=crdate, modified=mddate, items=len(children))
    return [disk, *children]


def index_images(paths: list[str | Path]) -> list[Item]:
    """Every image's catalog records in sequence: one disk record and
    its items per image, as a multi-disk .dtc holds them."""
    out: list[Item] = []
    for path in paths:
        out.extend(index_image(path))
    return out


def build_dtc(paths: list[str | Path]) -> bytes:
    """A .dtc catalog indexing every image's contents."""
    return write_dtc(index_images(paths))

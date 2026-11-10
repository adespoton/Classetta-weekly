"""Tests for Desktop DB parser."""

import struct
from macrt.macfile import _parse_desktop_db


def create_desktop_db(records):
    """Create a Desktop DB file with given records."""
    header = bytearray(8)
    heap_start = 8
    struct.pack_into('>H', header, 6, heap_start)
    heap_data = bytearray()
    for cnid, v, h, flags in records:
        rec_type = 0x01
        rec_data = struct.pack('>IHHH', cnid, v, h, flags)
        rec_size = len(rec_data)
        heap_data.append(rec_type)
        heap_data.extend(struct.pack('>H', rec_size))
        heap_data.extend(rec_data)
    end_used = heap_start + len(heap_data)
    struct.pack_into('>H', header, 4, end_used)
    struct.pack_into('>H', header, 2, end_used)
    return bytes(header) + bytes(heap_data)


def test_parse_desktop_db_basic():
    db_data = create_desktop_db([
        (16, 100, 200, 0x0001),
        (17, 300, 400, 0x0002),
    ])
    result = _parse_desktop_db(db_data)
    assert result[16] == {'v': 100, 'h': 200, 'flags': 1}
    assert result[17] == {'v': 300, 'h': 400, 'flags': 2}


def test_parse_desktop_db_empty():
    result = _parse_desktop_db(b'')
    assert result == {}


def test_parse_desktop_db_no_records():
    # Header only, no records
    header = bytearray(8)
    struct.pack_into('>H', header, 6, 8)  # heap start at 8
    struct.pack_into('>H', header, 4, 8)  # end used at 8
    struct.pack_into('>H', header, 2, 8)  # first free at 8
    result = _parse_desktop_db(bytes(header))
    assert result == {}


def test_parse_desktop_db_free_block():
    # Header + free block (type 0x00)
    header = bytearray(8)
    struct.pack_into('>H', header, 6, 8)  # heap start at 8
    heap_data = bytearray([0x00])  # Free block
    end_used = 8 + len(heap_data)
    struct.pack_into('>H', header, 4, end_used)
    struct.pack_into('>H', header, 2, end_used)
    result = _parse_desktop_db(bytes(header) + bytes(heap_data))
    assert result == {}

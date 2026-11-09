"""DiskTracker format reader + writer.

Implements parsing and writing of the proprietary DiskTracker 2 .dtc format used
by the classic Mac application DiskTracker.

Exports:
- parse_dtc, write_dtc : low-level functions.
- Disk, Item : dataclasses for records.
"""

from .disktracker import parse_dtc, Disk, Item
from .writer import write_dtc

__all__ = ["parse_dtc", "write_dtc", "Disk", "Item"]
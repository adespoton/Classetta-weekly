"""Adapter to open Disk Tracker .dtc/.dt1 files as read-only Filer volumes."""

from pathlib import Path
import machfs
from disktracker import parse_dtc

class CatalogFile(machfs.File):
    """A file whose size comes from the catalog index, not fork contents."""
    def __init__(self, type=b'????', creator=b'????', size=0, crdate=0, mddate=0):
        super().__init__()
        self.type = type[:4] if len(type) >= 4 else b'????'
        self.creator = creator[:4] if len(creator) >= 4 else b'????'
        self._catalog_size = size
        self.crdate = crdate
        self.mddate = mddate

    def sizes(self):
        return (self._catalog_size, 0)


class DiskTrackerVolume(machfs.Volume):
    """Wraps a parsed Disk Tracker file into a read-only machfs.Volume structure for Filer display."""
    def __init__(self, path: str | Path):
        super().__init__()
        path = Path(path)
        self.path = path
        self.name = path.stem
        data = path.read_bytes()
        items = parse_dtc(data)

        # Build tree using depth field (pre-order DFS)
        stack = [self]  # stack of folders at each depth level
        for item in items:
            if item.kind == 'disk':
                self.name = item.name
                continue

            # Ensure stack is long enough
            while len(stack) <= item.depth:
                stack.append(machfs.Folder())

            parent = stack[item.depth - 1]

            if item.kind == 'folder':
                f = machfs.Folder()
                try:
                    parent[item.name] = f
                except Exception:
                    pass
                # Push onto stack for children
                if len(stack) > item.depth:
                    stack[item.depth] = f
                else:
                    stack.append(f)
            elif item.kind == 'file':
                f = CatalogFile(
                    type=item.type,
                    creator=item.creator,
                    size=item.size,
                    crdate=item.created,
                    mddate=item.modified
                )
                try:
                    parent[item.name] = f
                except Exception:
                    pass

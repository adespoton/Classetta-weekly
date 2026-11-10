"""CLI entry point for DiskTracker commands."""

from pathlib import Path
import struct
import argparse
import sys
from .disktracker import parse_dtc
from .writer import write_dtc

def main():
    parser = argparse.ArgumentParser(prog='disktracker', description='DiskTracker .dtc format utilities')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # parse command
    p_parse = subparsers.add_parser('parse', help='Parse .dtc file and output text representation')
    p_parse.add_argument('file', help='Input .dtc file')
    p_parse.add_argument('--validate-txt', action='store_true', help='Compare with .txt file if present')

    # write command
    p_write = subparsers.add_parser('write', help='Write .dtc file from text representation')
    p_write.add_argument('txt_file', help='Text file (.txt) with rows: name\t[others]')
    p_write.add_argument('out', help='Output .dtc file')

    # index command: build a .dtc catalog from disk images
    p_index = subparsers.add_parser('index', help='Build a .dtc catalog from disk images')
    p_index.add_argument('images', nargs='+', help='Disk images to index (HFS or ISO 9660)')
    p_index.add_argument('-o', '--out', required=True, help='Output .dtc file')

def main():
    import sys
    # Handle top-level flags per user spec if present
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == '--scan':
            # disktracker --scan <file1> <file2> ... [-o index.dtc]
            import argparse
            parser = argparse.ArgumentParser(prog='disktracker')
            parser.add_argument('--scan', nargs='+', required=True)
            parser.add_argument('-o', '--out')
            args, remaining = parser.parse_known_args(sys.argv[1:])
            images = args.scan
            out = args.out
            if not out:
                out = Path(images[0]).with_suffix('.dtc').name
            from .index import build_dtc
            data = build_dtc(images)
            Path(out).write_bytes(data)
            print(f'Indexed {len(images)} image(s) into {out} ({len(data)} bytes)')
            return
        elif arg == '--todt1':
            # disktracker --todt1 <file.dtc> [-o out.dt1]
            import argparse
            parser = argparse.ArgumentParser(prog='disktracker')
            parser.add_argument('--todt1', required=True)
            parser.add_argument('-o', '--out')
            args = parser.parse_args(sys.argv[1:])
            src = Path(args.todt1)
            out = args.out or src.with_suffix('.dt1').name
            data = src.read_bytes()
            # For v2 -> v1, write out with v1 header magic
            if data.startswith(b'disktrak'):
                # replace version 2 with version 1
                v1_data = bytearray(data)
                v1_data[12:16] = struct.pack('>I', 1)
                Path(out).write_bytes(bytes(v1_data))
            else:
                Path(out).write_bytes(data)
            print(f'Converted {src} to DT1 format -> {out}')
            return
        elif arg == '--todt2':
            # disktracker --todt2 <file.dt1> [-o out.dtc]
            import argparse
            parser = argparse.ArgumentParser(prog='disktracker')
            parser.add_argument('--todt2', required=True)
            parser.add_argument('-o', '--out')
            args = parser.parse_args(sys.argv[1:])
            src = Path(args.todt2)
            out = args.out or src.with_suffix('.dtc').name
            data = src.read_bytes()
            if data.startswith(b'disktrak'):
                v2_data = bytearray(data)
                v2_data[12:16] = struct.pack('>I', 2)
                Path(out).write_bytes(bytes(v2_data))
            else:
                Path(out).write_bytes(data)
            print(f'Converted {src} to DT2 format -> {out}')
            return
        elif arg == '--totxt':
            # disktracker --totxt <file.dtc or file.dt1> [-o out.txt]
            import argparse
            parser = argparse.ArgumentParser(prog='disktracker')
            parser.add_argument('--totxt', required=True)
            parser.add_argument('-o', '--out')
            args = parser.parse_args(sys.argv[1:])
            src = Path(args.totxt)
            out = args.out or f'{src}.txt'
            items = parse_dtc(src.read_bytes())
            with open(out, 'w', encoding='utf-8') as f:
                f.write('Name\tSize\tKind\tType\tCreator\tCreated Date\tModified Date\tFree\tScanned Date\tItems\tSerial\tLocked\tPath\tFinder Label\tDisk Label\tItem Note\tVersion\tComment\n')
                for it in items:
                    typ = it.type.decode('latin-1', 'replace')
                    cre = it.creator.decode('latin-1', 'replace')
                    f.write(f"{it.name}\t{it.size}\t{it.kind}\t{typ}\t{cre}\t0\t0\t0\t0\t{it.items}\t\t\t{it.name}\t\t\t\t\t\n")
            print(f'Exported {len(items)} records to text -> {out}')
            return

    parser = argparse.ArgumentParser(prog='disktracker', description='DiskTracker .dtc format utilities')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # parse command
    p_parse = subparsers.add_parser('parse', help='Parse .dtc file and output text representation')
    p_parse.add_argument('file', help='Input .dtc file')
    p_parse.add_argument('--validate-txt', action='store_true', help='Compare with .txt file if present')

    # write command
    p_write = subparsers.add_parser('write', help='Write .dtc file from text representation')
    p_write.add_argument('txt_file', help='Text file (.txt) with rows: name\t[others]')
    p_write.add_argument('out', help='Output .dtc file')

    # index command: build a .dtc catalog from disk images
    p_index = subparsers.add_parser('index', help='Build a .dtc catalog from disk images')
    p_index.add_argument('images', nargs='+', help='Disk images to index (HFS or ISO 9660)')
    p_index.add_argument('-o', '--out', required=True, help='Output .dtc file')

    if args.command == 'parse':
        with open(args.file, 'rb') as f:
            data = f.read()
        items = parse_dtc(data)
        # Write CSV-like output for easy comparison
        out_path = args.file + '.parsed.txt'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('name\tkind\ttyp\tcreator\tparent\tsize\tcreated\tmodified\titems\tdesc\n')
            for it in items:
                f.write(f"{it.name}\t{it.kind}\t{it.type.decode('latin-1', 'replace')}\t{it.creator.decode('latin-1', 'replace')}\t{it.parent}\t{it.size}\t{it.created}\t{it.modified}\t{it.items}\t{it.descendants}\n")
        print(f'Parsed {len(items)} records, wrote to {out_path}')
        if args.validate_txt:
            txt_path = args.file.rsplit('.', 1)[0] + '.txt'
            try:
                with open(txt_path, 'r', encoding='mac_roman') as tf:
                    txt_rows = [l.rstrip('\n') for l in tf if l.strip()]
                if len(txt_rows) == len(items):
                    print('Row count matches')
                else:
                    print(f'Row count mismatch: .txt {len(txt_rows)} vs .dtc {len(items)}')
            except Exception as e:
                print(f'Failed to read .txt: {e}')

    elif args.command == 'write':
        with open(args.txt_file, 'r', encoding='utf-8') as f:
            lines = [l.rstrip('\n') for l in f if l.strip()]
        # Simple parser: first line optional header, rest name\t...
        data = write_dtc(lines)
        with open(args.out, 'wb') as f:
            f.write(data)
        print(f'Written {len(data)} bytes to {args.out}')

    elif args.command == 'index':
        from .index import build_dtc
        data = build_dtc(args.images)
        with open(args.out, 'wb') as f:
            f.write(data)
        print(f'Indexed {len(args.images)} image(s) into {args.out} ({len(data)} bytes)')

if __name__ == '__main__':
    main()
"""CLI entry point for DiskTracker commands."""

import argparse
import sys
from .disktracker import DiskTracker, parse_dtc, write_dtc

def main():
    parser = argparse.ArgumentParser(prog='disktracker', description='DiskTracker .dtc format utilities')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # parse command
    p_parse = subparsers.add_parser('parse', help='Parse .dtc file and output text representation')
    p_parse.add_argument('file', help='Input .dtc file')
    p_parse.add_argument('--validate-txt', action='store_true', help='Compare with .txt file if present')

    # write command
    p_write = subparsers.add_parser('write', help='Write .dtc file from text representation')
    p_write.add_argument('txt-file', help='Text file (.txt) with rows: name\t[others]')
    p_write.add_argument('out', help='Output .dtc file')

    args = parser.parse_args()

    if args.command == 'parse':
        with open(args.file, 'rb') as f:
            data = f.read()
        items = parse_dtc(data)
        # Write CSV-like output for easy comparison
        out_path = args.file + '.parsed.txt'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('name\tkind\ttyp\tcreator\tparent\tsize\tcreated\tmodified\titems\tdesc\n')
            for it in items:
                f.write(f"{it.get('name', '')}\t{it.get('kind', '')}\t{it.get('typ', b'').decode('latin-1', 'replace')}\t{it.get('creator', b'').decode('latin-1', 'replace')}\t{it.get('parent', 0)}\t{it.get('size', 0)}\t{it.get('created', 0)}\t{it.get('modified', 0)}\t{it.get('items', 0)}\t{it.get('desc', 0)}\n")
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

if __name__ == '__main__':
    main()
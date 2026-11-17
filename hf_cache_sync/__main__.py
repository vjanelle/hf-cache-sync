"""Command-line interface."""
import argparse
import sys
from .core import SyncError, sync, prune


def main(argv=None):
    parser = argparse.ArgumentParser(description='Synchronize Hugging Face Hub model caches')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('push', 'pull'):
        p = sub.add_parser(name)
        p.add_argument('--local', required=True, help='Local Hub cache directory')
        p.add_argument('--remote', required=True, help='CIFS-mounted Hub cache directory')
        select = p.add_mutually_exclusive_group(required=True)
        select.add_argument('--model', action='append', help='Model ID (repeatable)')
        select.add_argument('--all', action='store_true', help='Select all source models')
        p.add_argument('--source-wins', action='store_true', help='Replace conflicting refs with source refs')
        p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('prune', help='Remove selected remote models')
    p.add_argument('--remote', required=True)
    p.add_argument('--model', action='append', required=True)
    p.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'prune':
            changes = prune(args.remote, args.model, args.dry_run)
        else:
            source, dest = (args.local, args.remote) if args.command == 'push' else (args.remote, args.local)
            changes = sync(source, dest, args.model, args.source_wins, args.dry_run)
        for change in changes: print(change)
        print(f'{len(changes)} item(s) {"planned" if args.dry_run else "processed"}')
        return 0
    except (SyncError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

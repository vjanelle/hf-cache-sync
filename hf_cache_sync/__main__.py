"""Command-line interface."""
import argparse
import os
from pathlib import Path
import sys
import time
from .core import SyncError, sync, prune


def local_cache():
    """Resolve the Hub cache using Hugging Face environment precedence."""
    cache = os.environ.get("HF_HUB_CACHE") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    if cache:
        return Path(cache).expanduser()
    home = os.environ.get("HF_HOME")
    if home:
        return Path(home).expanduser() / "hub"
    base = Path(os.environ.get("XDG_CACHE_HOME") or "~/.cache").expanduser()
    return base / "huggingface" / "hub"


def cache_path(value):
    return Path(value).expanduser()


def progress_reporter(verbose):
    last = 0.0
    started = 0.0
    def report(phase, index, count, path, copied, total):
        nonlocal last, started
        if phase == 'planned':
            print(f'{count} item(s) planned', file=sys.stderr, flush=True)
        elif phase == 'copying':
            now = time.monotonic()
            if copied == 0:
                started = now
            if copied and copied != total and now - last < 1:
                return
            last = now
            percent = 100 if not total else int(copied * 100 / total)
            detail = f' {path}' if verbose else ''
            rate = copied / max(now - started, 0.001) / (1024 * 1024)
            print(f'[{index}/{count}] Copying{detail}: {percent}% ({copied}/{total} bytes, {rate:.1f} MiB/s)', file=sys.stderr, flush=True)
        elif phase == 'done' and verbose:
            print(f'[{index}/{count}] Completed {path}', file=sys.stderr, flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Synchronize Hugging Face Hub model caches')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('push', 'pull', 'repair'):
        p = sub.add_parser(name)
        p.add_argument('--local', type=cache_path, default=local_cache(), help='Local Hub cache (default: Hugging Face cache)')
        p.add_argument('--remote', type=cache_path, default=os.environ.get('HF_CACHE_SYNC_REMOTE'), required=not os.environ.get('HF_CACHE_SYNC_REMOTE'), help='CIFS Hub cache (or set HF_CACHE_SYNC_REMOTE)')
        select = p.add_mutually_exclusive_group(required=True)
        select.add_argument('--model', action='append', help='Model ID (repeatable)')
        select.add_argument('--all', action='store_true', help='Select all source models')
        if name == 'repair':
            p.add_argument('--from', dest='repair_source', choices=('local', 'remote'), required=True, help='Authoritative cache')
        p.add_argument('--source-wins', action='store_true', help='Replace conflicting refs with source refs')
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('-v', '--verbose', action='store_true', help='Show each path')
    p = sub.add_parser('prune', help='Remove selected remote models')
    p.add_argument('--remote', type=cache_path, default=os.environ.get('HF_CACHE_SYNC_REMOTE'), required=not os.environ.get('HF_CACHE_SYNC_REMOTE'), help='CIFS Hub cache (or set HF_CACHE_SYNC_REMOTE)')
    p.add_argument('--model', action='append', required=True)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('-v', '--verbose', action='store_true', help='Show each path')
    args = parser.parse_args(argv)
    try:
        print("Scanning and checking cache entries...", file=sys.stderr, flush=True)
        if args.command == 'prune':
            changes = prune(args.remote, args.model, args.dry_run, progress_reporter(args.verbose))
        else:
            source, dest = ((args.local, args.remote) if args.command == 'push' or (args.command == 'repair' and args.repair_source == 'local') else (args.remote, args.local))
            changes = sync(source, dest, args.model, args.source_wins, args.dry_run, progress_reporter(args.verbose), repair=args.command == 'repair')
        for change in changes: print(change)
        print(f'{len(changes)} item(s) {"planned" if args.dry_run else "processed"}')
        return 0
    except (SyncError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

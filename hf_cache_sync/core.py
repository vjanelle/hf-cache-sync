"""Plan and apply conservative cache transfers."""
import filecmp
import os
from pathlib import Path
import re
import shutil
import tempfile


class SyncError(Exception):
    """A cache operation cannot safely proceed."""


def repo_name(model):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', model) or '..' in model or '--' in model:
        raise SyncError(f'Invalid model ID: {model}')
    return 'models--' + model.replace('/', '--')


def select(root, models):
    if not root.is_dir():
        raise SyncError(f'Cache directory does not exist: {root}')
    names = [repo_name(m) for m in models] if models else sorted(p.name for p in root.iterdir() if p.name.startswith('models--') and p.is_dir() and not p.is_symlink())
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_dir():
            raise SyncError(f'Model not found or unsafe: {path}')
    return sorted(set(names))


def safe_path(root, relative):
    path = root / relative
    # Never traverse a destination symlink as an ancestor.
    for parent in list(path.parents)[:-len(root.parents)-1]:
        if parent.is_symlink():
            raise SyncError(f'Symlink in destination path: {parent}')
    return path


def sync(source, destination, models=None, source_wins=False, dry_run=False):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise SyncError('Cache directories must be distinct and non-overlapping')
    names = select(source, models)
    if not destination.is_dir():
        raise SyncError(f'Cache directory does not exist: {destination}')
    entries = {}
    def add(path):
        rel = path.relative_to(source)
        if rel in entries:
            return
        if path.is_symlink():
            target = os.readlink(path)
            if os.path.isabs(target):
                raise SyncError(f'Absolute symlink: {path}')
            resolved = path.resolve(strict=False)
            if not resolved.is_relative_to(source) or not resolved.is_file():
                raise SyncError(f'Missing or unsafe symlink target: {path}')
            entries[rel] = ('link', target)
            # Include intermediate symlinks as well as the ultimate file.
            target_path = Path(os.path.normpath(path.parent / target))
            add(target_path)
        elif path.is_file():
            entries[rel] = ('file', path)
        else:
            raise SyncError(f'Unsupported cache entry: {path}')
    for name in names:
        for base, dirs, files in os.walk(source / name, followlinks=False):
            dirs.sort(); files.sort()
            for d in list(dirs):
                if (Path(base)/d).is_symlink():
                    raise SyncError(f'Directory symlink not supported: {Path(base)/d}')
            for f in files:
                if f.endswith(('.incomplete', '.lock')):
                    continue
                add(Path(base)/f)
    # Shared-store marker enables the upstream client to recognize its store.
    if any(str(p).startswith('blobs/') for p in entries):
        blob_root = source / 'blobs'
        for marker in blob_root.iterdir():
            if marker.is_file() and not marker.is_symlink() and not marker.name.endswith('.refs'):
                add(marker)
    changes = []
    for rel, (kind, value) in sorted(entries.items(), key=lambda item: (item[1][0] == 'link', str(item[0]))):
        dst = safe_path(destination, rel)
        if dst.is_symlink() or dst.exists():
            same = (kind == 'link' and dst.is_symlink() and os.readlink(dst) == value) or (kind == 'file' and not dst.is_symlink() and dst.is_file() and filecmp.cmp(value, dst, shallow=False))
            if same:
                continue
            is_ref = len(rel.parts) >= 3 and rel.parts[1] == 'refs'
            if not (is_ref and source_wins and kind == 'file' and not dst.is_symlink() and dst.is_file()):
                raise SyncError(f'Destination conflict: {dst}')
        changes.append((rel, kind, value))
    if not dry_run:
        for rel, kind, value in changes:
            dst = safe_path(destination, rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix='.hf-cache-sync-', dir=dst.parent)
            os.close(fd)
            try:
                if kind == 'link':
                    os.unlink(tmp)
                    os.symlink(value, tmp)
                else:
                    shutil.copy2(value, tmp)
                os.replace(tmp, dst)
            finally:
                if os.path.lexists(tmp): os.unlink(tmp)
    return [str(item[0]) for item in changes]


def prune(remote, models, dry_run=False):
    remote = Path(remote).resolve()
    if not models:
        raise SyncError('Select at least one model to prune')
    names = select(remote, models)
    if not dry_run:
        for name in names:
            shutil.rmtree(remote / name)
    return names

"""Plan and apply conservative cache transfers."""
import errno
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


def cache_advice(fd, offset, length, advice):
    """Best-effort hint; filesystems and platforms may not support it."""
    hint = getattr(os, advice, None)
    advise = getattr(os, 'posix_fadvise', None)
    if hint is not None and advise is not None:
        try:
            advise(fd, offset, length, hint)
        except OSError:
            pass


def sync(source, destination, models=None, source_wins=False, dry_run=False, progress=None, repair=False):
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
    if any(p.parts[0] == 'blobs' for p in entries):
        blob_root = source / 'blobs'
        for marker in blob_root.iterdir():
            if marker.is_file() and not marker.is_symlink() and not marker.name.endswith('.refs'):
                add(marker)
    changes = []
    for rel, (kind, value) in sorted(entries.items(), key=lambda item: (item[1][0] == 'link', str(item[0]))):
        dst = safe_path(destination, rel)
        if dst.is_symlink() or dst.exists():
            is_data = (rel.parts[0] == 'blobs' or
                       (len(rel.parts) >= 2 and rel.parts[1] in ('blobs', 'snapshots')))
            same_file = (kind == 'file' and not dst.is_symlink() and dst.is_file() and
                         (value.stat().st_size == dst.stat().st_size if is_data and not repair
                          else filecmp.cmp(value, dst, shallow=False)))
            same = (kind == 'link' and dst.is_symlink() and os.path.normpath(os.readlink(dst)) == os.path.normpath(value)) or same_file
            if same:
                continue
            is_ref = len(rel.parts) >= 3 and rel.parts[1] == 'refs'
            if not ((is_ref and source_wins and kind == 'file' and not dst.is_symlink() and dst.is_file()) or
                    (repair and is_data and (dst.is_symlink() or dst.is_file()))):
                raise SyncError(f'Destination conflict: {dst}')
        changes.append((rel, kind, value))
    if progress:
        progress("planned", len(changes), len(changes), None, 0, 0)
    if not dry_run:
        for index, (rel, kind, value) in enumerate(changes, 1):
            dst = safe_path(destination, rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix='.hf-cache-sync-', dir=dst.parent)
            os.close(fd)
            try:
                if kind == 'link':
                    os.unlink(tmp)
                    os.symlink(os.path.normpath(value), tmp)
                else:
                    total = value.stat().st_size
                    copied = 0
                    if progress:
                        progress("copying", index, len(changes), str(rel), copied, total)
                    with value.open('rb', buffering=0) as src, open(tmp, 'wb', buffering=0) as out:
                        cache_advice(src.fileno(), 0, 0, 'POSIX_FADV_SEQUENTIAL')
                        fast_copy = getattr(os, 'copy_file_range', None)
                        while copied < total:
                            if fast_copy:
                                try:
                                    count = fast_copy(src.fileno(), out.fileno(), min(8 * 1024 * 1024, total - copied))
                                except OSError as exc:
                                    if exc.errno not in (errno.EXDEV, errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP):
                                        raise
                                    fast_copy = None
                                    continue
                                if not count:
                                    fast_copy = None
                                    continue
                            else:
                                chunk = src.read(min(1024 * 1024, total - copied))
                                if not chunk:
                                    raise OSError(f'Source changed during copy: {value}')
                                count = out.write(chunk)
                                if not count:
                                    raise OSError(f'Unable to write: {tmp}')
                                if count < len(chunk):
                                    src.seek(count - len(chunk), os.SEEK_CUR)
                            cache_advice(src.fileno(), copied, count, 'POSIX_FADV_DONTNEED')
                            cache_advice(out.fileno(), copied, count, 'POSIX_FADV_DONTNEED')
                            copied += count
                            if progress:
                                progress("copying", index, len(changes), str(rel), copied, total)
                    shutil.copystat(value, tmp)
                os.replace(tmp, dst)
                if progress:
                    progress("done", index, len(changes), str(rel), 0, 0)
            finally:
                if os.path.lexists(tmp): os.unlink(tmp)
    return [str(item[0]) for item in changes]


def prune(remote, models, dry_run=False, progress=None):
    remote = Path(remote).resolve()
    if not models:
        raise SyncError('Select at least one model to prune')
    names = select(remote, models)
    if progress:
        progress("planned", len(names), len(names), None, 0, 0)
    if not dry_run:
        for index, name in enumerate(names, 1):
            shutil.rmtree(remote / name)
            if progress:
                progress("done", index, len(names), name, 0, 0)
    return names

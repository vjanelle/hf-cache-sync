# hf-cache-sync

Copy cached Hugging Face models between two **Hub cache directories**, including a CIFS-mounted cache. The tool runs locally; it does not download from or upload to the Hugging Face Hub.

## Usage

Build a standalone executable with `make build` with `uv` installed (Python 3.10 or newer). The executable is `dist/hf-cache-sync`. You can also run `python3 -m hf_cache_sync` from the checkout.

```sh
hf-cache-sync pull --local ~/.cache/huggingface/hub --remote /mnt/cache/hub --model org/model --dry-run
hf-cache-sync pull --local ~/.cache/huggingface/hub --remote /mnt/cache/hub --model org/model
hf-cache-sync push --local ~/.cache/huggingface/hub --remote /mnt/cache/hub --all
hf-cache-sync prune --remote /mnt/cache/hub --model org/model --dry-run
hf-cache-sync prune --remote /mnt/cache/hub --model org/model
```

Repeat `--model` to select multiple models, or use `--all` for all source models on push/pull. Both cache directories must exist. Sync merges existing revisions without deleting destination models. Conflicting files stop the operation; `--source-wins` permits replacing conflicting refs only. A dry run checks and lists planned changes without writing.

Prune removes selected remote model directories regardless of local cache contents. It deliberately leaves shared blobs in place, including unused ones, to avoid deleting data used by other repositories. It does not reclaim the separate Xet transfer cache.

CIFS must support symbolic links and atomic renames. Mount options and server support vary; test with `--dry-run` and a small model first (dry-run cannot test symlink creation). Run while downloads, cache cleanup and other sync operations are stopped: the tool does not coordinate with Hugging Face cache locks. Transfers may be partially completed if interrupted; rerun to resume. Snapshot and blob conflicts are checked by reading file contents, which can take time for large models.

## Development

Install `uv`, then run `make test`, `make coverage` (minimum 80%), and `make build`. Tests use given/when/then scenario names and temporary cache fixtures.

## Packages and installation

`make install` builds and installs the executable to `/usr/local/bin` by default. Override `PREFIX`, `BINDIR`, or `DESTDIR` for a different installation location or staging root. `make deb` produces a Debian package using `dpkg-deb`. `make appimage` requires `appimagetool` on PATH (or set `APPIMAGETOOL` to its path). Set `VERSION` to override the default `0.1.0` package version. The executable and Linux packages target the architecture and glibc of the build system.

On Windows, install Python, uv, and WiX Toolset 4, then run `./packaging/build-msi.ps1` in PowerShell. The MSI installs the executable and adds its directory to the system PATH; installation requires administrator privileges. Build on the target OS: PyInstaller does not cross-compile. CI builds Linux packages and the Windows MSI on their respective platforms; it does not publish releases.

`uv run --locked` creates and manages the project `.venv` and installs the locked development tools automatically. Run `uv sync --locked` to prepare it explicitly.

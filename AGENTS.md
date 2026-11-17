# Repository Guidelines

## Project Structure & Module Organization

`hf_cache_sync/core.py` implements cache discovery, synchronization, repair, and pruning. `hf_cache_sync/__main__.py` provides the CLI; `hf_cache_sync_cli.py` is the PyInstaller entry point. Behavioral tests live in `tests/test_sync.py`. Packaging scripts, the Windows installer definition, and assets are in `packaging/`; package CI is in `.github/workflows/packages.yml`. Design and implementation notes live under `docs/superpowers/`.

## Build, Test, and Development Commands

Install `uv` and use Python 3.10 or newer. `uv sync --locked` creates `.venv` and installs locked development dependencies; the Make targets also run through `uv`.

- `make help` lists supported targets and variables.
- `make test` runs the unittest suite; `make coverage` enforces 80% line coverage.
- `uv run --locked python -m hf_cache_sync --help` runs the CLI locally.
- `make build` creates `dist/hf-cache-sync`; `make install` installs it, honoring `PREFIX` and `DESTDIR`.
- `make deb` and `make appimage` build Linux packages. On Windows, run `./packaging/build-msi.ps1` with WiX installed.
- `make clean` removes build and distribution directories.

## Coding Style & Naming Conventions

Use four-space Python indentation and follow the surrounding standard-library-based code. Use `snake_case` for functions and variables, `PascalCase` for classes, and descriptive CLI options. Keep filesystem operations separate from CLI reporting where practical. No formatter or linter is configured; avoid introducing unrelated formatting changes.

## Testing Guidelines

Tests use Python's `unittest` and temporary cache fixtures. Name scenarios `test_given_<context>_when_<action>_then_<result>`. Cover symlinks, conflicts, dry runs, and failures when changing transfer or repair behavior. Run `make coverage` before submitting; CI requires at least 80% coverage. Exercise packaging on its target OS when changing package scripts.

## Commit & Pull Request Guidelines

The existing history uses a Conventional Commit style, such as `feat: add Hugging Face cache sync utility`. Write a concise imperative subject. In pull requests, describe the behavior and motivation, link relevant issues when available, and report tests and platform limitations. Screenshots are unnecessary for CLI-only changes.

## Cache Safety

Treat cached blobs as immutable and preserve symlink targets. Do not infer remote deletion from local absence. Repair requires a trusted source; use dry runs when checking potentially destructive changes. CIFS support varies, so document platform-specific assumptions and test with temporary fixtures rather than a user's live cache.

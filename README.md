# hf-cache-sync

Sync cached Hugging Face models between a local Hub cache and a second cache, such as one on a mounted CIFS share. The utility works with files already in the caches; it does not download from or upload to the Hugging Face Hub.

## Install

Run from a checkout with Python 3.10+ and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked
uv run --locked python -m hf_cache_sync --help
```

Alternatively, build a standalone executable with `make build`. See the [installation guide](docs/INSTALL.md) for Debian, AppImage, Windows MSI, and installation from source. CI produces package artifacts; it does not publish releases.

## Quick start

Set the remote path to the **Hub cache directory** on the mounted share. The directory must already exist.

```sh
export HF_CACHE_SYNC_REMOTE=/mnt/models/huggingface/hub

# Preview, then pull a model from the share into the local cache.
uv run --locked python -m hf_cache_sync pull --model org/model --dry-run
uv run --locked python -m hf_cache_sync pull --model org/model

# Push all locally cached models to the share.
uv run --locked python -m hf_cache_sync push --all
```

After installing the executable, replace `uv run --locked python -m hf_cache_sync` with `hf-cache-sync`. Repeat `--model` to select multiple models. `--all` selects all models in the source cache.

The local cache defaults to `HF_HUB_CACHE`, the legacy `HUGGINGFACE_HUB_CACHE`, `HF_HOME/hub`, or `${XDG_CACHE_HOME:-~/.cache}/huggingface/hub`, in that order. Override it with `--local`. Use `--remote` to override `HF_CACHE_SYNC_REMOTE`. Both cache directories must exist.

## Operations

- **Pull / push:** merge cached snapshots and blobs. Existing model data files with the same size are reused; equal sizes do not prove their contents match. Different sizes cause a conflict. Refs and other metadata are compared by content. Use `--source-wins` to replace conflicting refs.
- **Repair:** compare model data byte-for-byte and replace differing or missing destination data from a trusted source. Preview first:

  ```sh
  hf-cache-sync repair --from remote --model org/model --dry-run
  hf-cache-sync repair --from local --model org/model
  ```

  Use `--all` to select every model in the source cache. Repair cannot determine which copy is correct. Conflicting refs require `--source-wins`.
- **Prune:** remove selected model directories from the remote cache, independently of local cache contents. It retains shared blobs, even if unused, and does not prune the separate Xet transfer cache.

  ```sh
  hf-cache-sync prune --model org/model --dry-run
  hf-cache-sync prune --model org/model
  ```

Progress and average per-file throughput are printed to stderr. Use `-v` / `--verbose` for paths and completed entries. `--dry-run` checks and lists planned changes without writing.

## CIFS and cache safety

The CIFS mount must support the source layout's symbolic links and atomic renames. Mount and server behavior vary: try a dry run and a small model first. A dry run cannot test whether symlinks can be created. Stop downloads, cache cleanup, and other sync operations during transfers; this utility does not coordinate with Hugging Face cache locks. An interrupted transfer may leave partial results; rerun to resume.

Shared blob reference manifests are not rebuilt by sync. Avoid upstream shared-blob cleanup on synchronized caches until compatibility has been verified for your Hugging Face client version.

Where supported, transfers use kernel-assisted copying with a buffered fallback. The utility provides sequential-access and page-eviction hints; the OS or CIFS filesystem may ignore them, especially for dirty destination pages. Eviction can affect other processes sharing those pages and does not control server-side caching. The utility does not use `O_DIRECT` or force synchronous writes.

## Development

Use `make help` for available targets. `make test` runs the unittest suite, and `make coverage` enforces 80% line coverage. See [AGENTS.md](AGENTS.md) for contributor guidance.

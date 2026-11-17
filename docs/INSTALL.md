# Installation

## Requirements

The utility operates on existing Hugging Face **Hub cache directories**. Both the local cache and the remote cache directory must exist, and the CIFS share must already be mounted. Confirm that the mount supports the cache's symbolic links and atomic renames. No Hugging Face account is needed to copy files already cached.

Packages and standalone binaries target the operating system and architecture on which they were built. Linux builds also depend on the build system's glibc compatibility. The repository's CI produces artifacts for its configured platforms but does not publish releases.

## Run from source

Install Python 3.10 or newer and [uv](https://docs.astral.sh/uv/). From a checkout:

```sh
uv sync --locked
uv run --locked python -m hf_cache_sync --help
```

`uv` creates a project `.venv` and installs the locked development tools. Use the `uv run` prefix in place of `hf-cache-sync` in the README examples.

## Linux standalone executable

With Python and uv installed, build and run the executable:

```sh
make build
./dist/hf-cache-sync --help
```

To install to a user-writable location without administrator privileges:

```sh
make install PREFIX="$HOME/.local"
"$HOME/.local/bin/hf-cache-sync" --help
```

Add `$HOME/.local/bin` to your `PATH` if necessary. `make install` defaults to `/usr/local/bin`, which generally requires elevated permissions. `BINDIR` overrides the binary directory; `DESTDIR` stages an installation under a separate root.

## Debian package

On a Debian-compatible build host with `dpkg-deb`, Python, and uv:

```sh
make deb
sudo apt install ./dist/hf-cache-sync_0.1.0_amd64.deb
hf-cache-sync --help
```

Adjust the filename for the version and architecture produced. Set `VERSION` when building to override the default `0.1.0`. Remove the installed package with `sudo apt remove hf-cache-sync`.

## AppImage

Install `appimagetool` for your architecture, then build and launch:

```sh
make appimage
./dist/hf-cache-sync-0.1.0-x86_64.AppImage --help
```

Adjust the filename for the version and architecture produced. Set `APPIMAGETOOL` to its path if it is not on `PATH`; `VERSION` overrides the package version. `APPIMAGE_RUNTIME` can point to a local runtime file. Running an AppImage may require FUSE; where supported by the runtime, `APPIMAGE_EXTRACT_AND_RUN=1` runs it by extracting it first.

## Windows MSI

On Windows, install Python 3.10+, uv, and WiX Toolset 4. From PowerShell in the checkout:

```powershell
./packaging/build-msi.ps1
msiexec /i .\dist\hf-cache-sync-0.1.0-x64.msi
```

The installer requires administrator privileges and adds the installation directory to the system `PATH`. Open a new terminal and run `hf-cache-sync --help`. Uninstall through Windows installed apps or `msiexec /x` with the installed product's MSI or product code. Windows symbolic-link support depends on the host and permissions; verify the cache layout on the target system.

## Configure cache paths

The local Hub cache uses Hugging Face environment variables by default; `--local` overrides it. Set `HF_CACHE_SYNC_REMOTE` to the Hub cache on the mounted share, or pass `--remote` on each command. Both options accept directory paths, not model IDs. See the [README](../README.md) for precedence, examples, and repair and prune behavior.

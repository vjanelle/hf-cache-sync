#!/bin/sh
set -eu
version=${VERSION:-0.1.0}
arch=$(dpkg --print-architecture)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/share/doc/hf-cache-sync"
install -m 755 dist/hf-cache-sync "$stage/usr/bin/hf-cache-sync"
install -m 644 README.md "$stage/usr/share/doc/hf-cache-sync/README.md"
cat > "$stage/DEBIAN/control" <<CONTROL
Package: hf-cache-sync
Version: $version
Section: utils
Priority: optional
Architecture: $arch
Maintainer: hf-cache-sync contributors
Description: Synchronize Hugging Face model caches
 A command-line tool for copying cached models between local directories.
CONTROL
mkdir -p dist
 dpkg-deb --build --root-owner-group "$stage" "dist/hf-cache-sync_${version}_${arch}.deb"

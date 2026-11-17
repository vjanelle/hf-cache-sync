#!/bin/sh
set -eu
: "${APPIMAGETOOL:=appimagetool}"
command -v "$APPIMAGETOOL" >/dev/null || { echo 'appimagetool is required' >&2; exit 1; }
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
chmod 755 "$stage"
mkdir -p "$stage/usr/bin"
install -m 755 dist/hf-cache-sync "$stage/usr/bin/hf-cache-sync"
cat > "$stage/AppRun" <<'RUN'
#!/bin/sh
exec "$(dirname "$(readlink -f "$0")")/usr/bin/hf-cache-sync" "$@"
RUN
chmod 755 "$stage/AppRun"
cat > "$stage/hf-cache-sync.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=HF Cache Sync
Exec=hf-cache-sync
Icon=hf-cache-sync
Terminal=true
Categories=Utility;
DESKTOP
cat > "$stage/hf-cache-sync.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" rx="20" fill="#ffd21e"/><path d="M26 48h62l-13-13m27 45H40l13 13" fill="none" stroke="#202020" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/></svg>
SVG
install -m 644 packaging/icon.png "$stage/hf-cache-sync.png"
if [ -n "${APPIMAGE_RUNTIME:-}" ]; then
    set -- --runtime-file "$APPIMAGE_RUNTIME"
else
    set --
fi
ARCH=${ARCH:-$(uname -m)} "$APPIMAGETOOL" "$@" "$stage" "dist/hf-cache-sync-${VERSION:-0.1.0}-$(uname -m).AppImage"

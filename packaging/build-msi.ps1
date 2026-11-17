param([string]$Version = '0.1.0')
$ErrorActionPreference = 'Stop'
uv run --locked python -m PyInstaller --onefile --name hf-cache-sync --noconfirm hf_cache_sync_cli.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
wix build -arch x64 -d "Version=$Version" -d "SourceDir=$((Resolve-Path dist).Path)" packaging/hf-cache-sync.wxs -o "dist/hf-cache-sync-$Version-x64.msi"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

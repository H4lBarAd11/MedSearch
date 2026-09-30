#!/bin/bash
# MedSearch — build MedSearch.app and the macOS installer (.dmg).
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
#
#   packaging/build-mac.sh
#
# Needs a Python with requirements.txt and PyInstaller installed; PYTHON names
# it (default: python3). Writes, in the MedSearch folder:
#   dist/MedSearch.app
#   dist/MedSearch-<version>-mac.dmg
#
# THE .dmg IS WHAT A MAC USER EXPECTS: MedSearch beside a shortcut to
# Applications, dragged across once. It holds the whole app, so the Mac needs
# neither Python nor git.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
cd "$ROOT"

"$PY" -m PyInstaller --noconfirm --clean --distpath dist --workpath build \
  packaging/MedSearch.spec

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ditto dist/MedSearch.app "$STAGE/MedSearch.app"
ln -s /Applications "$STAGE/Applications"

DMG="dist/MedSearch-$VERSION-mac.dmg"
rm -f "$DMG"
hdiutil create -volname "MedSearch" -srcfolder "$STAGE" -format UDZO -ov "$DMG" >/dev/null
echo "Built $DMG"

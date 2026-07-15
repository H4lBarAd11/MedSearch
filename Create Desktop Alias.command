#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  MedSearch — create a Desktop alias (macOS)
#
#  Double-click this ONCE. It puts a "MedSearch" icon on your Desktop that is a
#  Finder alias to MedSearch.command in this folder, and gives it the MedSearch
#  app icon. Double-click that Desktop icon day-to-day to launch the app.
#
#  Run it again any time this folder moves, to refresh the alias.
#
#  Note: the first time, macOS may ask to let Terminal control Finder — click OK.
# ─────────────────────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TARGET="$SCRIPT_DIR/MedSearch.command"
DESKTOP="$HOME/Desktop"
ALIAS="$DESKTOP/MedSearch"
ICON="$SCRIPT_DIR/icon.icns"

if [ ! -f "$TARGET" ]; then
  echo "  ✗ MedSearch.command not found next to this script."
  echo "    Keep this file inside the MedSearch folder and try again."
  exit 1
fi

# Make sure the launcher is executable (git usually preserves this).
chmod +x "$TARGET" 2>/dev/null || true

# Remove any previous alias so we can recreate it cleanly.
rm -f "$ALIAS" "$DESKTOP/MedSearch.command alias" 2>/dev/null || true

echo "  Creating the Desktop alias…"
osascript >/dev/null <<EOF
tell application "Finder"
  set theTarget to POSIX file "$TARGET" as alias
  set theAlias to make new alias file at desktop to theTarget
  set name of theAlias to "MedSearch"
end tell
EOF

# Give the alias the MedSearch icon (uses the app's own pyobjc, installed in
# .venv by MedSearch.command; falls back to the system python3).
if [ -f "$ICON" ]; then
  PY="$SCRIPT_DIR/.venv/bin/python3"
  [ -x "$PY" ] || PY="$(command -v python3 || true)"
  if [ -n "$PY" ]; then
    "$PY" - "$ALIAS" "$ICON" <<'PYEOF' 2>/dev/null || echo "  (icon step skipped — alias still works)"
import sys
from AppKit import NSWorkspace, NSImage
alias_path, icon_path = sys.argv[1], sys.argv[2]
img = NSImage.alloc().initWithContentsOfFile_(icon_path)
NSWorkspace.sharedWorkspace().setIcon_forFile_options_(img, alias_path, 0)
PYEOF
  fi
fi

echo ""
echo "  ✓ Done. A 'MedSearch' icon is on your Desktop — double-click it to start."

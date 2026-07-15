#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  MedSearch — install a Desktop app (macOS)   [run this ONCE, during setup]
#
#  Double-click this once. It (1) sets up the app's environment, then (2) builds
#  a "MedSearch" app onto the Desktop that launches MedSearch WITH NO TERMINAL —
#  a normal Mac app with the MedSearch icon in the Dock. Day-to-day, users just
#  double-click that Desktop icon; they never see a terminal.
#
#  It's a thin wrapper that runs the app from THIS git clone, so the in-app
#  Update button still works. Re-run this if you move the MedSearch folder.
# ─────────────────────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "──────────────────────────────────────────────"
echo "  Installing MedSearch onto the Desktop…"
echo "──────────────────────────────────────────────"

# ── Need Python 3 ────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display alert "MedSearch needs Python 3" message "Install Python 3 from python.org, then run this again."' >/dev/null 2>&1 || true
  echo "  ✗ Python 3 not found."
  exit 1
fi

# ── First-run setup: virtual environment + dependencies (so the app launches
#    instantly later, with nothing to install and no terminal to show) ─────────
if [ ! -d ".venv" ]; then
  echo "  Setting up the environment (one time)…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
NEED_INSTALL=0
python3 -c "import flask"   2>/dev/null || NEED_INSTALL=1
python3 -c "import webview" 2>/dev/null || NEED_INSTALL=1
if [ "$NEED_INSTALL" -eq 1 ]; then
  echo "  Installing dependencies…"
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
fi
deactivate 2>/dev/null || true

# ── Build the wrapper app on the Desktop ─────────────────────────────────────
APP="$HOME/Desktop/MedSearch.app"
echo "  Building $APP …"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Icon
[ -f "$SCRIPT_DIR/icon.icns" ] && cp "$SCRIPT_DIR/icon.icns" "$APP/Contents/Resources/MedSearch.icns"

# Info.plist — names the app, its icon, and marks it high-res.
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>MedSearch</string>
  <key>CFBundleDisplayName</key><string>MedSearch</string>
  <key>CFBundleExecutable</key><string>MedSearch</string>
  <key>CFBundleIconFile</key><string>MedSearch</string>
  <key>CFBundleIdentifier</key><string>com.riccardonevoso.medsearch.launcher</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# Executable — launches the app from THIS clone, replacing itself with Python so
# the Dock icon and app identity are MedSearch's. No terminal is ever shown.
cat > "$APP/Contents/MacOS/MedSearch" <<LAUNCH
#!/bin/bash
# A double-clicked app inherits only a minimal PATH, which can hide 'git' from
# the in-app Update button. Add the usual git locations (Apple CLT + Homebrew)
# so auto-update works regardless of how git was installed.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:\$PATH"
cd "$SCRIPT_DIR"
if [ ! -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
  osascript -e 'display alert "MedSearch needs setup" message "Re-run \"Create Desktop App.command\" in the MedSearch folder."' >/dev/null 2>&1 || true
  exit 1
fi
exec "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/app.py"
LAUNCH
chmod +x "$APP/Contents/MacOS/MedSearch"

# Nudge Finder/LaunchServices to pick up the new bundle + icon.
touch "$APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP" 2>/dev/null || true

echo ""
echo "  ✓ Done. Double-click the MedSearch icon on the Desktop to start —"
echo "    no terminal, just the app."

#!/bin/bash
# MedSearch for iOS — build this app, signed with YOUR Apple ID, and put it on
# YOUR iPhone or iPad. Copyright 2026 Riccardo Nevoso. Apache License 2.0.
#
# Needs a Mac with Xcode (free, from the App Store), your Apple ID added once
# under Xcode › Settings › Accounts, and the iPhone plugged in (or on the same
# Wi-Fi after the first time), unlocked, with Developer Mode on.
#
#   ios/build-for-my-iphone.sh                  build, install, open, and keep it renewed
#   ios/build-for-my-iphone.sh --team ID        which of your Xcode teams signs it
#   ios/build-for-my-iphone.sh --device UDID    which iPhone or iPad, when several are paired
#   ios/build-for-my-iphone.sh --no-renewal     don't set up the automatic renewal
#   ios/build-for-my-iphone.sh --remove-renewal stop the automatic renewal
#   ios/build-for-my-iphone.sh --renew          what the renewal runs: build and install, quietly
#
# A free Apple ID signs an app for seven days. The renewal (a small job in
# ~/Library/LaunchAgents, checking at login, 09:00 and 21:00) builds and
# installs it again when less than about a day is left, after you confirm
# with Touch ID. The app's ID is com.halbarad.medsearch.<your team>: Apple
# lets each ID belong to one team only. MEDSEARCH_BUNDLE_ID sets another.
set -euo pipefail

IOS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIEFCASE_VERSION="0.4.6"                 # the version this app is built and tested with
SUPPORT="$HOME/Library/Application Support/MedSearch Builder"
CONFIG="$SUPPORT/config"
AGENT_LABEL="com.halbarad.medsearch.renew-iphone"
AGENT="$HOME/Library/LaunchAgents/$AGENT_LABEL.plist"
XCODEPROJ="$IOS/build/medsearch/ios/xcode/MedSearch.xcodeproj"
DERIVED="$IOS/build/derived"
LOG="$IOS/build/build-for-my-iphone.log"

say()  { printf '%s\n' "$*"; }
step() { printf '\n▸ %s\n' "$*"; }
fail() { printf '\n✗ %s\n' "$*" >&2; exit 1; }

TEAM=""; DEVICE=""; RENEWAL=1; QUIET=0
while [ $# -gt 0 ]; do
  case "$1" in
    --team) TEAM="${2:-}"; shift 2 ;;
    --device) DEVICE="${2:-}"; shift 2 ;;
    --no-renewal) RENEWAL=0; shift ;;
    --renew) QUIET=1; RENEWAL=0; shift ;;
    --remove-renewal)
      launchctl bootout "gui/$(id -u)/$AGENT_LABEL" 2>/dev/null || true
      rm -f "$AGENT"
      say "The automatic renewal is off. The app stays on the iPhone until its signing runs out."
      exit 0 ;;
    -h|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "Unknown option: $1 (see --help)" ;;
  esac
done

# The renewal runs with what the first build found.
if [ -f "$CONFIG" ]; then
  # shellcheck disable=SC1090
  . "$CONFIG"
  TEAM="${TEAM:-${SAVED_TEAM:-}}"; DEVICE="${DEVICE:-${SAVED_DEVICE:-}}"
fi

[ "$(uname -s)" = Darwin ] || fail "This needs a Mac: Apple builds iPhone apps only with Xcode, on macOS."

# ── Xcode ────────────────────────────────────────────────────────────────
step "Checking Xcode"
DEV_DIR="$(xcode-select -p 2>/dev/null || true)"
case "$DEV_DIR" in
  *.app/Contents/Developer) ;;
  *) fail "Xcode is not installed, or not the one in use. Install Xcode from the App Store, open it once,
  then run:  sudo xcode-select -s /Applications/Xcode.app" ;;
esac
xcodebuild -version >/dev/null 2>&1 || fail "Xcode is not ready. Open Xcode once and accept its licence (or run: sudo xcodebuild -license accept)."
if ! xcodebuild -showsdks 2>/dev/null | grep -q iphoneos; then
  fail "Xcode has no iOS platform yet. Install it from Xcode › Settings › Components,
  or run:  xcodebuild -downloadPlatform iOS"
fi
say "$(xcodebuild -version | head -1)"

# ── Python and Briefcase ─────────────────────────────────────────────────
step "Checking Python and Briefcase"
PY=""
for c in python3.14 python3.13 python3.12 python3; do
  p="$(command -v "$c" 2>/dev/null || true)"
  [ -n "$p" ] || continue
  if "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then PY="$p"; break; fi
done
[ -n "$PY" ] || fail "Python 3.12 or newer is needed (3.14 is what this app is tested with).
  Install it from https://www.python.org/downloads/macos/ and run this again."
if [ ! -x "$IOS/.venv/bin/briefcase" ] || ! "$IOS/.venv/bin/briefcase" --version 2>/dev/null | grep -q "$BRIEFCASE_VERSION"; then
  say "Setting up Briefcase $BRIEFCASE_VERSION in ios/.venv (once)…"
  "$PY" -m venv "$IOS/.venv"
  "$IOS/.venv/bin/pip" install --quiet --upgrade pip
  "$IOS/.venv/bin/pip" install --quiet "briefcase==$BRIEFCASE_VERSION"
fi
say "$("$IOS/.venv/bin/python" --version), Briefcase $BRIEFCASE_VERSION"

# ── Your team ────────────────────────────────────────────────────────────
step "Finding your signing team"
TEAMS="$(defaults export com.apple.dt.Xcode - 2>/dev/null | /usr/bin/python3 -I -c '
import plistlib, sys
try:
    d = plistlib.loads(sys.stdin.buffer.read())
except Exception:
    sys.exit(0)
for teams in (d.get("IDEProvisioningTeamByIdentifier") or {}).values():
    for t in teams:
        print("%s\t%s" % (t.get("teamID", ""), t.get("teamName", "")))
' | sort -u)"
if [ -z "$TEAM" ]; then
  n="$(printf '%s' "$TEAMS" | grep -c . || true)"
  if [ "$n" = 0 ]; then
    fail "Xcode knows no Apple ID yet. Open Xcode › Settings › Accounts, press + and add your Apple ID
  (a free one works), then run this again."
  elif [ "$n" -gt 1 ]; then
    say "Xcode has several teams:"; printf '%s\n' "$TEAMS" | sed 's/^/  /'
    fail "Pick one with --team <ID>, the code in the first column."
  fi
  TEAM="$(printf '%s' "$TEAMS" | cut -f1)"
fi
say "Team $TEAM $(printf '%s' "$TEAMS" | awk -F'\t' -v t="$TEAM" '$1==t {print "(" $2 ")"}')"
BUNDLE="${MEDSEARCH_BUNDLE_ID:-}"
if [ -z "$BUNDLE" ] && [ "$TEAM" = "${SAVED_TEAM:-}" ]; then BUNDLE="${SAVED_BUNDLE:-}"; fi
BUNDLE="${BUNDLE:-com.halbarad.medsearch.$(printf '%s' "$TEAM" | tr '[:upper:]' '[:lower:]')}"

# ── Your iPhone ──────────────────────────────────────────────────────────
step "Finding your iPhone"
mkdir -p "$IOS/build"
JSON="$(mktemp -t medsearch-devices)"
trap 'rm -f "$JSON"' EXIT
xcrun devicectl list devices --json-output "$JSON" >/dev/null 2>&1 || true
DEVICES="$(/usr/bin/python3 -I - "$JSON" <<'PY'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
for d in data.get("result", {}).get("devices", []):
    hw = d.get("hardwareProperties", {})
    if hw.get("reality") != "physical" or hw.get("platform") != "iOS":
        continue
    state = d.get("connectionProperties", {}).get("tunnelState", "")
    print("%s\t%s\t%s" % (hw.get("udid", ""), d.get("deviceProperties", {}).get("name", "?"), state))
PY
)"
if [ -z "$DEVICE" ]; then
  n="$(printf '%s' "$DEVICES" | grep -c . || true)"
  if [ "$n" = 0 ]; then
    fail "No iPhone or iPad is paired with this Mac. Plug it in with a cable, unlock it and tap Trust.
  The first time, also turn on Settings › Privacy & Security › Developer Mode on it (it restarts)."
  elif [ "$n" -gt 1 ]; then
    say "Several are paired:"; printf '%s\n' "$DEVICES" | cut -f1,2 | sed 's/^/  /'
    fail "Pick one with --device <UDID>, the code in the first column."
  fi
  DEVICE="$(printf '%s' "$DEVICES" | cut -f1)"
fi
say "$(printf '%s' "$DEVICES" | awk -F'\t' -v u="$DEVICE" '$1==u {print $2}') ($DEVICE)"

# ── The Xcode project ────────────────────────────────────────────────────
step "Preparing the app"
cd "$IOS"
if [ ! -d "$XCODEPROJ" ]; then
  say "Creating the Xcode project (once; it downloads Python for iOS)…"
  .venv/bin/briefcase create iOS --no-input >"$LOG" 2>&1 || { tail -20 "$LOG"; fail "briefcase create failed (full log: $LOG)"; }
else
  .venv/bin/briefcase update iOS --no-input >"$LOG" 2>&1 || { tail -20 "$LOG"; fail "briefcase update failed (full log: $LOG)"; }
fi
"$IOS/.venv/bin/python" "$IOS/patch_xcode.py" >>"$LOG" 2>&1 || { tail -20 "$LOG"; fail "patch_xcode.py failed (full log: $LOG)"; }

# ── Build, sign, install, open ───────────────────────────────────────────
step "Building and signing (a few minutes the first time)"
if ! xcodebuild -project "$XCODEPROJ" -scheme MedSearch -configuration Debug \
      -destination "id=$DEVICE" -derivedDataPath "$DERIVED" \
      -allowProvisioningUpdates -allowProvisioningDeviceRegistration \
      DEVELOPMENT_TEAM="$TEAM" CODE_SIGN_STYLE=Automatic PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE" \
      build >>"$LOG" 2>&1; then
  grep -E "error:|Unable to find a destination|not available|No Account|No profiles" "$LOG" | tail -8 >&2 || tail -20 "$LOG" >&2
  fail "The build failed (full log: $LOG). Is the iPhone unlocked and nearby? If Xcode says the
  Apple ID needs attention, open Xcode › Settings › Accounts and sign in again."
fi
APP="$DERIVED/Build/Products/Debug-iphoneos/MedSearch.app"
[ -d "$APP" ] || fail "The build left no app at $APP (full log: $LOG)."

step "Installing on the iPhone"
if ! out="$(xcrun devicectl device install app --device "$DEVICE" "$APP" 2>&1)"; then
  printf '%s\n' "$out" | tail -6 >&2
  case "$out" in
    *[Dd]eveloper\ [Mm]ode*) fail "Turn on Developer Mode on the iPhone: Settings › Privacy & Security › Developer Mode (it restarts), then run this again." ;;
    *) fail "The install failed. Unlock the iPhone, keep it nearby (or plug it in), and run this again." ;;
  esac
fi
say "Installed: MedSearch ($BUNDLE)"

# What the renewal will use.
mkdir -p "$SUPPORT"
cat > "$CONFIG" <<EOF
SAVED_TEAM="$TEAM"
SAVED_DEVICE="$DEVICE"
SAVED_BUNDLE="$BUNDLE"
SAVED_REPO="$(cd "$IOS/.." && pwd)"
EOF

if [ "$QUIET" = 0 ]; then
  step "Opening it"
  if ! xcrun devicectl device process launch --terminate-existing --device "$DEVICE" "$BUNDLE" >/dev/null 2>&1; then
    say "It didn't open by itself: the iPhone may be locked. Unlock it and tap MedSearch."
    say "If iOS says the developer isn't trusted (the first time only): Settings › General ›"
    say "VPN & Device Management › your Apple ID › Trust, then tap MedSearch again."
  fi
fi

# ── The renewal ──────────────────────────────────────────────────────────
if [ "$RENEWAL" = 1 ]; then
  step "Setting up the automatic renewal"
  cp "$IOS/renew/renew.sh" "$SUPPORT/renew.sh"; chmod +x "$SUPPORT/renew.sh"
  if [ ! -x "$SUPPORT/touchid" ] || [ "$IOS/renew/touchid.swift" -nt "$SUPPORT/touchid" ]; then
    xcrun swiftc -O -o "$SUPPORT/touchid" "$IOS/renew/touchid.swift" >>"$LOG" 2>&1 \
      || fail "Couldn't build the Touch ID check (full log: $LOG). Rerun with --no-renewal to skip the renewal."
  fi
  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
  cat > "$AGENT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$AGENT_LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$SUPPORT/renew.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/medsearch-renew-iphone.log</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/$AGENT_LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$AGENT" 2>/dev/null || true
  say "On. Twice a day it checks; about a day before the signing runs out it asks for Touch ID"
  say "and installs MedSearch again (iPhone unlocked, on this Mac's Wi-Fi or plugged in)."
  say "Status: \"$SUPPORT/renew.sh\" --status   Off: ios/build-for-my-iphone.sh --remove-renewal"
fi

step "Done"

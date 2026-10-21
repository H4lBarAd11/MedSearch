#!/bin/bash
# MedSearch — sign MedSearch.app with the developer's own team, for iCloud Keychain.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
#
#   MEDSEARCH_TEAM=<team id> packaging/sign-mac.sh [dist/MedSearch.app]
#
# WHY. The iPhone app keeps its API keys as iCloud Keychain items; a Mac app
# may share them only if it is signed by the same team with the
# keychain-access-groups entitlement, and that entitlement needs a
# provisioning profile. Xcode makes one ("Mac Team Provisioning Profile:
# com.halbarad.medsearch") when it builds the probe in packaging/macsign,
# and this script embeds it in the real app and signs the app to match.
# The public download is not signed this way (that takes a paid Developer ID;
# a personal team's profile lasts seven days and is renewed by building the
# probe again, which this script does when the profile is missing or has a
# day left). Without the signature MedSearch keeps its keys in the login
# keychain as before (secrets_store.py).
#
# Needs: Xcode with the Apple ID signed in (its Personal Team is the team),
# Briefcase for the probe (BRIEFCASE names it; default ios/.venv/bin/briefcase).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${1:-$ROOT/dist/MedSearch.app}"
TEAM="${MEDSEARCH_TEAM:?set MEDSEARCH_TEAM to the team id (Xcode › Settings › Accounts)}"
IDENTITY="${MEDSEARCH_SIGN_IDENTITY:-Apple Development}"
BRIEFCASE="${BRIEFCASE:-$ROOT/ios/.venv/bin/briefcase}"
BUNDLE="com.halbarad.medsearch"
PROFILES="$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles"
PROBE="$ROOT/packaging/macsign"

[ -d "$APP" ] || { echo "no app at $APP (packaging/build-mac.sh first)"; exit 1; }

profile_for() {           # the newest profile Xcode made for the bundle, if any
  ls -t "$PROFILES"/*.provisionprofile 2>/dev/null | while read -r f; do
    if [ "$(security cms -D -i "$f" 2>/dev/null | plutil -extract Name raw - 2>/dev/null)" = "Mac Team Provisioning Profile: $BUNDLE" ]; then
      echo "$f"; return
    fi
  done
}
profile_valid() {         # not run out
  local exp; exp="$(security cms -D -i "$1" 2>/dev/null | plutil -extract ExpirationDate raw - 2>/dev/null)"
  [ -n "$exp" ] || return 1
  [ "$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$exp" "+%s" 2>/dev/null || echo 0)" -gt "$(date +%s)" ]
}
profile_fresh() {         # more than a day left
  local exp; exp="$(security cms -D -i "$1" 2>/dev/null | plutil -extract ExpirationDate raw - 2>/dev/null)"
  [ -n "$exp" ] || return 1
  local exp_s; exp_s="$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$exp" "+%s" 2>/dev/null || echo 0)"
  [ "$exp_s" -gt "$(( $(date +%s) + 86400 ))" ]
}

PROFILE="$(profile_for || true)"
# MEDSEARCH_RENEW=1: ask Xcode again even with a day or more left (the
# renewal automation does, about a day before the profile runs out).
if [ -z "$PROFILE" ] || [ "${MEDSEARCH_RENEW:-0}" = 1 ] || ! profile_fresh "$PROFILE"; then
  echo "Making the provisioning profile (the probe in packaging/macsign)..."
  [ -x "$BRIEFCASE" ] || { echo "no Briefcase at $BRIEFCASE (BRIEFCASE=...)"; exit 1; }
  ( cd "$PROBE" && [ -d build/medsearch/macos/xcode ] || "$BRIEFCASE" create macOS Xcode --no-input >/dev/null )
  xcodebuild -project "$PROBE/build/medsearch/macos/xcode/MedSearch.xcodeproj" -scheme MedSearch \
    -allowProvisioningUpdates DEVELOPMENT_TEAM="$TEAM" CODE_SIGN_STYLE=Automatic \
    CODE_SIGN_IDENTITY="$IDENTITY" MACOSX_DEPLOYMENT_TARGET=12.0 build 2>&1 | grep -E "error:|BUILD" || true
  PROFILE="$(profile_for || true)"
  [ -n "$PROFILE" ] || { echo "Xcode made no profile for $BUNDLE under team $TEAM"; exit 1; }
  # A failed probe build leaves the old profile as the newest: never sign
  # with one that has run out (the app would then refuse to open).
  profile_valid "$PROFILE" || { echo "Xcode could not renew the profile, and the one it has has run out"; exit 1; }
fi
echo "Profile: $(basename "$PROFILE"), expires $(security cms -D -i "$PROFILE" | plutil -extract ExpirationDate raw -)"

ENT="$(mktemp -t medsearch-entitlements)"   # the file mktemp made, so the trap removes it
trap 'rm -f "$ENT"' EXIT
cat > "$ENT" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>com.apple.application-identifier</key><string>$TEAM.$BUNDLE</string>
  <key>com.apple.developer.team-identifier</key><string>$TEAM</string>
  <key>keychain-access-groups</key><array><string>$TEAM.$BUNDLE</string></array>
</dict></plist>
PLIST

cp "$PROFILE" "$APP/Contents/embedded.provisionprofile"

# Inside out: every Mach-O the bundle carries, then the frameworks, then
# the app itself with the entitlements (only the app needs them).
MAIN="$APP/Contents/MacOS/$(basename "$APP" .app)"
find "$APP/Contents" -type f ! -path "$MAIN" | while read -r f; do
  case "$(file -b "$f")" in Mach-O*) codesign --force --sign "$IDENTITY" "$f" 2>/dev/null || true;; esac
done
find "$APP/Contents" -type d -name "*.framework" | while read -r fw; do
  codesign --force --sign "$IDENTITY" "$fw" 2>/dev/null || true
done
codesign --force --sign "$IDENTITY" --entitlements "$ENT" "$APP"
codesign --verify --deep --strict "$APP"
codesign -d --entitlements - "$APP" 2>&1 | grep -q "keychain-access-groups" && echo "Signed $APP for iCloud Keychain (team $TEAM)"

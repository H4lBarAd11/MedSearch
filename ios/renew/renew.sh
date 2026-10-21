#!/bin/bash
# MedSearch for iOS — the automatic renewal set up by ios/build-for-my-iphone.sh.
# Copyright 2026 Riccardo Nevoso. Apache License 2.0.
#
# A free Apple ID's signing lasts seven days; then the app stops opening.
# Run from ~/Library/LaunchAgents at login, 09:00 and 21:00, this does nothing
# until less than RENEW_HOURS are left. Then it posts a notification, asks for
# Touch ID, and builds and installs MedSearch again (build-for-my-iphone.sh
# --renew), with the iPhone unlocked and on the Mac's Wi-Fi or plugged in.
# Afterwards a notification says until when; when Xcode kept the old profile,
# or the iPhone wasn't reachable, the next check tries again.
#
#   renew.sh           the scheduled check
#   renew.sh --now     renew now (asks for Touch ID)
#   renew.sh --status  how long the signing has left; renews nothing
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$HERE/config"
RENEW_HOURS=30
PROFILES="$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles"
LOG="$HOME/Library/Logs/medsearch-renew-iphone.log"
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$PATH"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
notify() {    # title, text
  /usr/bin/osascript - "$1" "$2" <<'OSA' >/dev/null 2>&1
on run argv
  display notification (item 2 of argv) with title (item 1 of argv)
end run
OSA
}

[ -f "$CONFIG" ] || { log "no config: run ios/build-for-my-iphone.sh once"; exit 0; }
# shellcheck disable=SC1090
. "$CONFIG"
BUILDER="$SAVED_REPO/ios/build-for-my-iphone.sh"

# The newest profile Xcode holds for the app, and when it runs out (epoch).
expiry() {
  local want="iOS Team Provisioning Profile: $SAVED_BUNDLE" best=0 f plist name exp e
  for f in "$PROFILES"/*.mobileprovision; do
    [ -e "$f" ] || continue
    plist="$(security cms -D -i "$f" 2>/dev/null)" || continue
    name="$(printf '%s' "$plist" | plutil -extract Name raw - 2>/dev/null)"
    [ "$name" = "$want" ] || continue
    exp="$(printf '%s' "$plist" | plutil -extract ExpirationDate raw - 2>/dev/null)"
    e="$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$exp" "+%s" 2>/dev/null || echo 0)"
    [ "$e" -gt "$best" ] && best="$e"
  done
  echo "$best"
}
day_of() { date -r "$1" "+%a %d %b, %H:%M"; }

mode="${1:-check}"
exp="$(expiry)"
now="$(date +%s)"
if [ "$exp" = 0 ]; then
  status="no signing found for $SAVED_BUNDLE"
  left=0
else
  left=$(( (exp - now) / 3600 ))
  status="signed until $(day_of "$exp") (${left} h left)"
fi

if [ "$mode" = "--status" ]; then echo "MedSearch (iPhone): $status"; exit 0; fi
if [ ! -x "$BUILDER" ]; then
  log "the MedSearch folder has moved or gone ($SAVED_REPO); run ios/build-for-my-iphone.sh from its new place"
  notify "MedSearch can't be renewed" "Its folder has moved. Run ios/build-for-my-iphone.sh from where it is now."
  exit 0
fi
if [ "$mode" != "--now" ] && [ "$exp" != 0 ] && [ "$left" -ge "$RENEW_HOURS" ]; then
  log "nothing due: $status"; exit 0
fi

log "due: $status"
notify "MedSearch's signing runs out soon" "Confirm with Touch ID to install it again on your iPhone."
if ! "$HERE/touchid" "install MedSearch on your iPhone again"; then
  log "not confirmed"
  notify "MedSearch not renewed" "Not confirmed. I'll ask again at the next check."
  exit 0
fi

if "$BUILDER" --renew >> "$LOG" 2>&1; then
  after="$(expiry)"
  if [ "$after" -gt "$exp" ]; then
    msg="Installed again, signed until $(day_of "$after")."
  else
    msg="Installed, but Xcode kept the signing ending $(day_of "$after"). I'll try again at the next check."
  fi
else
  msg="Not installed: is the iPhone unlocked, and on this Mac's Wi-Fi or plugged in? I'll try again at the next check."
fi
notify "MedSearch renewal" "$msg"
log "done: $msg"

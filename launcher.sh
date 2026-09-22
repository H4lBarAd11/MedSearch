#!/bin/bash
# MedSearch — how the installed MedSearch.app starts the app.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
#
# The MedSearch.app on the Desktop (or in /Applications) is a two-line stub that
# runs THIS file, which is part of the git clone. So how MedSearch starts is
# updated by the in-app update like everything else; the stub never has to be
# rebuilt. Called as:  launcher.sh <path of MedSearch.app> [app.py arguments…]
#
# MEDSEARCH, NOT "PYTHON". Handing over to the virtual environment's python3
# ends in Homebrew's Python.app, so macOS filed the running app under "Python":
# its name in the Dock, the app switcher and the menu bar, and its icon. Instead
# the interpreter runs from a copy of that same small executable placed INSIDE
# MedSearch.app, so the process belongs to MedSearch's bundle.
#
# SPAWNED, NOT EXEC'D, and this is not a style choice. Measured 20 Sep on macOS
# 27: a process that IS the one LaunchServices launched for the app is refused a
# menu bar slot — its NSStatusItem is created, reports itself present and
# visible, and is never placed (x stays 0, for as long as the app runs). The
# same interpreter, same bundle, same code, started any other way is placed in
# under a second. Eleven runs, split cleanly down that line, with an empty forty
# line app bundle showing the same thing, so it is nothing about MedSearch. So
# the stub starts the app and steps out of the way: what LaunchServices launched
# exits immediately, and MedSearch runs on as its child. It keeps the bundle's
# interpreter, so it is still MedSearch in the Dock and the app switcher — and
# it gets its icon in the menu bar.
# __PYVENV_LAUNCHER__ tells it which virtual environment it belongs to, exactly
# as Python's own launcher does. The copy is refreshed whenever its original
# changes, since a Homebrew update replaces it.
#
# APPLE'S PYTHON NEEDS ONE MORE STEP. The python3 of Apple's Command Line Tools
# (what a Mac without Homebrew or python.org has, like the Monterey iMac) finds
# its library by a path relative to itself (@executable_path/../../../../Python3),
# so a copy moved into MedSearch.app cannot load and dies on the spot. Such
# paths are rewritten to where the original found them, and the copy re-signed
# (ad hoc) since the rewrite breaks Apple's signature. The copy is tried once
# before it is used; if it cannot run, or anything is missing, MedSearch starts
# the plain way: it still opens, just filed under "Python" or "python3".

BUNDLE="$1"; shift
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1

# A double-clicked app inherits only a minimal PATH, which can hide git from the
# in-app update. Add the usual git locations (Apple CLT + Homebrew).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

VENV_PY="$DIR/.venv/bin/python3"
if [ ! -x "$VENV_PY" ]; then
  osascript -e 'display alert "MedSearch needs setup" message "Run \"Create Desktop App.command\" in the MedSearch folder."' >/dev/null 2>&1 || true
  exit 1
fi

GUI_PY="$("$VENV_PY" -c 'import os, sys
p = os.path.join(sys.base_prefix, "Resources", "Python.app", "Contents", "MacOS", "Python")
print(p if os.path.isfile(p) else "")' 2>/dev/null)"
OWN="$BUNDLE/Contents/MacOS/MedSearch-python"
FROM="$BUNDLE/Contents/Resources/MedSearch-python.from"   # which original the copy is of

# Runs, and inside the virtual environment (a copy that cannot load dies here).
own_runs() { ( "$OWN" -c 'import sys; sys.exit(sys.prefix == sys.base_prefix)' ) >/dev/null 2>&1; }

own_python() {
  local lib
  cp -f "$GUI_PY" "$OWN" 2>/dev/null || return 1
  if ! own_runs; then
    for lib in $(otool -L "$OWN" 2>/dev/null | awk 'NR > 1 && $1 ~ /^@(executable|loader)_path\// { print $1 }' | sort -u); do
      install_name_tool -change "$lib" "$(dirname "$GUI_PY")/${lib#@*_path/}" "$OWN" 2>/dev/null || return 1
    done
    codesign -f -s - "$OWN" >/dev/null 2>&1 && own_runs || return 1
  fi
  echo "$STAMP" > "$FROM"
}

if [ -n "$GUI_PY" ] && [ -d "$BUNDLE/Contents/MacOS" ]; then
  export __PYVENV_LAUNCHER__="$VENV_PY"
  STAMP="$GUI_PY $(stat -f '%m %z' "$GUI_PY")"
  if { [ -x "$OWN" ] && [ "$(cat "$FROM" 2>/dev/null)" = "$STAMP" ]; } || own_python; then
    nohup "$OWN" "$DIR/app.py" "$@" >/dev/null 2>&1 &
    exit 0
  fi
  rm -f "$OWN" "$FROM"
  unset __PYVENV_LAUNCHER__
fi
nohup "$VENV_PY" "$DIR/app.py" "$@" >/dev/null 2>&1 &
exit 0

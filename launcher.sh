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
# __PYVENV_LAUNCHER__ tells it which virtual environment it belongs to, exactly
# as Python's own launcher does. The copy is refreshed whenever it differs, since
# a Homebrew update replaces the original. If anything is missing, it falls
# back to the plain start: MedSearch still opens, just filed under "Python".

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

if [ -n "$GUI_PY" ] && [ -d "$BUNDLE/Contents/MacOS" ]; then
  cmp -s "$GUI_PY" "$OWN" || cp -f "$GUI_PY" "$OWN" 2>/dev/null
  if [ -x "$OWN" ]; then
    export __PYVENV_LAUNCHER__="$VENV_PY"
    exec "$OWN" "$DIR/app.py" "$@"
  fi
fi
exec "$VENV_PY" "$DIR/app.py" "$@"

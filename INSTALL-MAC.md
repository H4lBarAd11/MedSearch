# MedSearch — macOS install (neurosurgery iMac)

Goal: a Desktop icon that launches MedSearch like a normal Mac app — **no
Terminal window, ever** — while still updating itself when the app offers
**Update now**. Works on any Mac (Intel or Apple Silicon).

**Prerequisite:** Python 3.8+ and Git (pre-installed on macOS, or from
[python.org](https://python.org) / `xcode-select --install`).

## Setup (do once, by whoever installs it)

1. **Clone the repo** somewhere permanent (e.g. the home folder):
   ```bash
   git clone https://github.com/H4lBarAd11/MedSearch.git
   cd MedSearch
   ```

2. **Double-click `Create Desktop App.command`.** A Terminal window appears *just
   for this one-time step* — it sets up the environment, installs dependencies,
   and builds a **MedSearch** app onto the Desktop. When it says "Done", close
   that Terminal window.
   > If macOS blocks it ("unidentified developer"): right-click ▸ **Open** ▸
   > **Open**, once.

That's the whole install.

## Daily use (what the doctors do)

**Double-click the MedSearch icon on the Desktop.** The app opens in its own
window — no Terminal, no black window, nothing else to see or close.

**Closing the window does not quit MedSearch:** it keeps running in the menu bar
(the small book-and-magnifier icon at the top of the screen), so a search can be
started from anywhere. That menu has the quick search, the recent searches, the
default database, *Open MedSearch window*, and *Quit MedSearch*. To quit for
real: that Quit, or ⌘Q.

**Optional:** *Settings ▸ Open at login* makes MedSearch start with the Mac,
window closed, waiting in the menu bar.

## Notes

- The Desktop app is a thin launcher that runs MedSearch from this git clone, so
  the in-app **Update now** prompt still works (it does a `git pull`). One app,
  one update: the menu bar item is part of MedSearch, not a second program.
  (Up to 1.3 it was a separate "MedSearch Menu Bar.app". If that is still
  installed on a machine, delete it from `/Applications` and remove it from
  **System Settings ▸ General ▸ Login Items**.)
- **Updating from 1.3 or earlier:** the first start after the update rewrites
  the Desktop launcher, so that macOS shows the app as *MedSearch* rather than
  *Python*, and gives it the current icon. macOS may ask once whether Python may
  access the Desktop folder — that request is this rewrite; allowing it is the
  simplest answer, and re-running `Create Desktop App.command` does the same
  job if it was refused.
- Keep the cloned folder in a fixed location. If you ever **move or rename** it,
  re-run `Create Desktop App.command` to rebuild the Desktop app against the new
  path.
- `MedSearch.command` is still in the folder as a plain (Terminal-visible)
  launcher for troubleshooting, but day-to-day nobody needs it.
- Everything runs locally; the only change to the machine is the Python packages,
  which live inside the folder's `.venv`.

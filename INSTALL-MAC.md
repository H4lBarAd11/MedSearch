# MedSearch — macOS install (neurosurgery iMac)

Goal: a Desktop icon that launches MedSearch like a normal Mac app — **no
Terminal window, ever** — while still updating itself when the app offers
**Update now**. Works on any Mac (Intel or Apple Silicon).

**Prerequisite:** Python 3.8+ and Git (pre-installed on macOS, or from
[python.org](https://python.org) / `xcode-select --install`).

## Setup (do once, by whoever installs it)

1. **Clone the repo** somewhere permanent (e.g. the home folder):
   ```bash
   git clone https://github.com/H4lBarAd11/MedSearch-by-RN.git
   cd MedSearch-by-RN
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
window — no Terminal, no black window, nothing else to see or close. Quit it like
any app (⌘Q or close the window).

## Notes

- The Desktop app is a thin launcher that runs MedSearch from this git clone, so
  the in-app **Update now** prompt still works (it does a `git pull`).
- Keep the cloned folder in a fixed location. If you ever **move or rename** it,
  re-run `Create Desktop App.command` to rebuild the Desktop app against the new
  path.
- `MedSearch.command` is still in the folder as a plain (Terminal-visible)
  launcher for troubleshooting, but day-to-day nobody needs it.
- Everything runs locally; the only change to the machine is the Python packages,
  which live inside the folder's `.venv`.

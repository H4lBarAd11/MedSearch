# MedSearch — macOS install (neurosurgery iMac)

A double-clickable setup: a launcher that sets itself up on first run, plus a
Desktop icon to start it. Works on any Mac (Intel or Apple Silicon) and keeps
the in-app **Update** button working, because it runs from a git clone.

**Prerequisite:** Python 3.8+ and Git (both are pre-installed on macOS, or from
[python.org](https://python.org) / `xcode-select --install`).

## Steps (do these on the iMac)

1. **Clone the repo** somewhere permanent (e.g. your home folder):
   ```bash
   git clone https://github.com/H4lBarAd11/MedSearch-by-RN.git
   cd MedSearch-by-RN
   ```

2. **First launch.** Double-click **`MedSearch.command`** in the folder. On first
   run it creates a local environment and installs dependencies (one time,
   ~1 min), then the MedSearch window opens.
   > If macOS blocks it ("unidentified developer"): right-click
   > `MedSearch.command` ▸ **Open** ▸ **Open**. Only needed once.

3. **Create the Desktop icon.** Double-click **`Create Desktop Alias.command`**
   once. A **MedSearch** icon (with the app's own icon) appears on the Desktop —
   a Finder alias to the launcher. From then on, just double-click that.
   > The first time, macOS may ask to let Terminal control Finder — click **OK**.

That's it. To update later, use the **Update** button inside the app (or
`git pull` in the folder).

## Notes

- Keep the folder in a fixed location. If you move it, re-run
  `Create Desktop Alias.command` to refresh the alias.
- Everything runs locally; the only system-wide change is the Python packages,
  which live inside the folder's `.venv`.

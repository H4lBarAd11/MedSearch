# MedSearch — Windows install (neurosurgery iMac)

A double-clickable setup that mirrors the macOS `MedSearch.command`: a launcher
that sets itself up on first run, plus a Desktop icon to start it.

**Prerequisite:** Python 3.8+ on PATH (already installed on this machine).
Optional: [Git for Windows](https://git-scm.com/download/win) — only needed if
you want the in-app **Update** button to work (it runs `git pull`).

## Steps (do these on the iMac)

1. **Get the folder onto the iMac.**
   - *With Git (recommended, keeps auto-update):*
     ```bat
     git clone https://github.com/H4lBarAd11/MedSearch-by-RN.git
     ```
   - *Without Git:* download the repo ZIP from GitHub (green **Code ▸ Download
     ZIP**) and extract it somewhere permanent (e.g. `C:\MedSearch`). The app
     still runs; only the in-app Update button is unavailable.

2. **First launch.** Open the folder and **double-click `MedSearch.bat`**.
   A console window appears while it creates a local environment and installs
   dependencies (one time, ~1 min), then the MedSearch window opens.

3. **Create the Desktop icon.** Double-click **`Create Desktop Shortcut.vbs`**
   once. A **MedSearch** icon appears on the Desktop, pointing at the launcher
   with the app icon. From then on, day-to-day you just double-click that icon.

That's it. To update later (if you cloned with Git), use the **Update** button
inside the app, or run `git pull` in the folder.

## Notes

- Keep the folder in a fixed location. If you move it, re-run
  `Create Desktop Shortcut.vbs` to refresh the shortcut's path.
- The app runs entirely locally; nothing is installed system-wide except the
  Python packages, which live inside the folder's `.venv`.
- If `python` isn't found, reinstall Python from python.org with
  **"Add Python to PATH"** ticked, then double-click `MedSearch.bat` again.

# MedSearch — how the installers' MedSearch is built (PyInstaller).
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""The app the installers carry: Python, Flask, pywebview and MedSearch's own
files in one MedSearch.app, so a user needs neither Python nor git.

BUILT, NOT RUN FROM SOURCE. `python3 app.py` in a clone of the code is for
development; this is what the Releases hold.

ONE FOLDER, NOT ONE FILE. PyInstaller's one-file mode unpacks itself into a
temporary folder on every start, which costs seconds and leaves the app's
files somewhere new each time. The folder mode starts at once.

THE IDENTIFIER IS com.halbarad.medsearch, app.py's APP_ID: Open at login goes
through it, so it comes back as this MedSearch.

ON WINDOWS the same spec makes dist/MedSearch/MedSearch.exe, which the Setup
program (MedSearch.iss) installs.

Build it with packaging/build-mac.sh or packaging/build-windows.ps1.
"""
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
VERSION = (ROOT / "VERSION").read_text().strip()
WINDOWS = sys.platform == "win32"

datas = [
    (str(ROOT / "templates"), "templates"),
    (str(ROOT / "static"), "static"),
    (str(ROOT / "VERSION"), "."),
]
if WINDOWS:
    datas.append((str(ROOT / "icon.ico"), "."))          # the tray and the windows
    # Imported only inside functions that run on Windows.
    hidden = ["tray", "splash_win", "webview.platforms.winforms",
              "webview.platforms.edgechromium"]
else:
    datas.append((str(ROOT / "menubar_icon.png"), "."))
    # Imported only inside functions that run on the Mac.
    hidden = ["statusbar", "splash", "webview.platforms.cocoa"]

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hidden,
    # MarkupSafe's compiled speed-up is built for one kind of Mac only, which a
    # universal app cannot hold; without it MarkupSafe runs as plain Python.
    excludes=["tkinter", "PIL", "pytest", "markupsafe._speedups"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MedSearch",
    console=False,
    upx=False,
    argv_emulation=False,
    # "universal2" for the Release (Intel and Apple silicon Macs in one app);
    # otherwise the build machine's own kind.
    target_arch=os.environ.get("MEDSEARCH_TARGET_ARCH") or None,
    icon=str(ROOT / "icon.ico") if WINDOWS else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MedSearch", upx=False)

if not WINDOWS:
    app = BUNDLE(
        coll,
        name="MedSearch.app",
        icon=str(ROOT / "icon.icns"),
        bundle_identifier="com.halbarad.medsearch",
        version=VERSION,
        info_plist={
            "CFBundleName": "MedSearch",
            "CFBundleDisplayName": "MedSearch",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        },
    )

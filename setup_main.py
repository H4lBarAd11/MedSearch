# Copyright 2026 Riccardo Nevoso
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
py2app build script for the MAIN MedSearch app (the search window).

This makes MedSearch.app fully self-contained: Python, Flask, pywebview, the
templates, and the icon are all embedded. Unlike the old shell-launcher build,
it doesn't depend on your project folder staying put or on which `python3`
resolves — you can move it anywhere, including /Applications.

BUILD (on your Mac, with the Homebrew Python that has flask + pywebview + py2app):
    /opt/homebrew/bin/python3 -m pip install py2app --break-system-packages
    /opt/homebrew/bin/python3 setup_main.py py2app

The finished app appears in  ./dist/MedSearch.app
Move it to /Applications.

NOTE: build with the Homebrew python3 directly, NOT from inside a virtualenv
(py2app has known issues with venvs).

The menu bar item is part of this app (statusbar.py); there is no second bundle.
"""
from setuptools import setup

APP = ['app.py']

# Bundle the template(s), the VERSION file, and the icon source into the app so
# the frozen build can find them at runtime (app.py is py2app-aware and looks in
# Contents/Resources).
DATA_FILES = [
    ('templates', ['templates/index.html']),
    # Fonts and the PDF viewer ship with the app so it works offline and on
    # networks that block CDNs.
    ('static/fonts', ['static/fonts/dm-sans-400.woff2', 'static/fonts/dm-sans-500.woff2',
                      'static/fonts/dm-sans-700.woff2', 'static/fonts/dm-sans-800.woff2',
                      'static/fonts/OFL.txt']),
    ('static/css', ['static/css/app.css']),
    ('static/js', ['static/js/boot.js', 'static/js/app.js']),
    ('static/vendor/pdfjs', ['static/vendor/pdfjs/pdf.min.js',
                             'static/vendor/pdfjs/pdf.worker.min.js',
                             'static/vendor/pdfjs/LICENSE']),
    'VERSION',
    'menubar_icon.png',          # the menu bar item's glyph
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleName': 'MedSearch',
        'CFBundleDisplayName': 'MedSearch',
        'CFBundleIdentifier': 'com.halbarad.medsearch',
        'CFBundleShortVersionString': '1.4',
        'CFBundleVersion': '1.4',
        'LSMinimumSystemVersion': '10.13',
        # The main app is a normal windowed app: it SHOULD have a Dock icon and
        # appear in the app switcher, so we do NOT set LSUIElement here.
        'NSHighResolutionCapable': True,
    },
    # Everything the app imports at runtime. pywebview + flask are the big ones;
    # we name pyobjc bits pywebview uses on macOS so they're pulled in.
    'packages': ['flask', 'webview', 'jinja2', 'werkzeug', 'click',
                 'markupsafe', 'itsdangerous'],
    'includes': ['statusbar', 'PyObjCTools.AppHelper',
                 'webview.platforms.cocoa', 'objc', 'AppKit', 'Foundation',
                 'WebKit', 'urllib.request', 'urllib.parse', 'xml.etree.ElementTree',
                 'ipaddress', 'secrets', 'hmac'],
}

setup(
    app=APP,
    name='MedSearch',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
)

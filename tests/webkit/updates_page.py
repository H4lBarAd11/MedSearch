"""The update check in the real MedSearch page, in WebKit, without a window.

Run by tests/test_routes.py in a process of its own, or directly:
    .venv/bin/python tests/webkit/updates_page.py

NO WINDOW, NO DOCK ICON, NO NETWORK. MedSearch's own server runs here on a free
127.0.0.1 port, with HOME in a temporary folder and GitHub faked, and the page is
loaded into a web view that is never put in a window. Prints one PASS/FAIL line
per check and exits 1 if any failed.
"""
import atexit
import logging
import os
import shutil
import socket
import sys
import tempfile
import threading
from pathlib import Path

HOME = tempfile.mkdtemp(prefix="medsearch-updates-")
atexit.register(shutil.rmtree, HOME, ignore_errors=True)
os.environ["HOME"] = HOME
os.environ["MEDSEARCH_KEYCHAIN"] = "0"
for var in ("ANTHROPIC_API_KEY", "NCBI_API_KEY", "SCOPUS_API_KEY", "WOS_API_KEY", "UNPAYWALL_EMAIL"):
    os.environ.pop(var, None)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from AppKit import NSApplication                                    # noqa: E402
from Foundation import NSRunLoop, NSDate, NSURL, NSURLRequest, NSMakeRect  # noqa: E402
import WebKit                                                       # noqa: E402
from werkzeug.serving import make_server                            # noqa: E402

NSApplication.sharedApplication().setActivationPolicy_(2)          # no Dock icon

import app as A                                                     # noqa: E402

# What GitHub has published; None = GitHub out of reach. Every question to it is
# counted, and nothing else may leave this machine.
published = {"version": "9.9"}
asked = []


def published_commit():
    asked.append("which commit")
    return None if published["version"] is None else "c0ffee"


def github_file(name, commit):
    asked.append(name)
    if name == "VERSION":
        return published["version"] + "\n"
    return f"## {published['version']}\n\n- Something new.\n"


A._published_commit = published_commit
A._github_file = github_file
A.http_get = lambda *a, **k: (None, 0)
A.CONFIG["onboarding_seen"] = True

# NEVER the real update or restart here: the update resets this very folder to
# GitHub's main, and a restart starts a real MedSearch. The update fails, as
# one can; a restart is refused.
A.app.view_functions["update_apply"] = lambda: A.jsonify(
    {"ok": False, "message": "The update could not be downloaded (test)."})
A.app.view_functions["app_restart"] = lambda: (A.jsonify({"ok": False}), 403)

with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    PORT = s.getsockname()[1]
logging.getLogger("werkzeug").setLevel(logging.ERROR)
server = make_server("127.0.0.1", PORT, A.app, threaded=True)
threading.Thread(target=server.serve_forever, daemon=True).start()

config = WebKit.WKWebViewConfiguration.alloc().init()
config.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
web = WebKit.WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, 1100, 800), config)


def spin(seconds=0.05):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))


def js(source):
    box = {}

    def done(result, error):
        box["result"] = result
    web.evaluateJavaScript_completionHandler_(source, done)
    for _ in range(100):
        spin()
        if box:
            break
    return box.get("result")


def until(test, seconds=5.0):
    for _ in range(int(seconds / 0.05)):
        if test():
            return True
        spin()
    return False


def is_open(overlay):
    return bool(js(f"document.getElementById('{overlay}').classList.contains('open')"))


def offered():
    return js("document.getElementById('updateText').textContent") or ""


def window_comes_back(throttled=False):
    """What WebKit does when the window is shown again, as far as the page sees it."""
    if not throttled:
        js("_lastUpdateCheck = 0; 1")
    js("window.dispatchEvent(new Event('focus')); 1")


failed = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        failed.append(name)


web.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(f"http://127.0.0.1:{PORT}/")))
# Not document.readyState alone: the blank page before the load is "complete" too.
check("the page loads", until(lambda: js("document.readyState === 'complete'"
                                         " && typeof autoCheckForUpdate === 'function'"), 20))
# Outside a window WebKit never advances an animation, so a dialog would never
# finish closing: run without them, as the page does under Reduce motion.
js("Element.prototype.animate = null; 1")

# ── by itself ───────────────────────────────────────────────────────────────
check("at launch, a newer version is offered", until(lambda: is_open("updateOverlay")))
check("with what it changes", "9.9" in offered() and "Something new." in offered())

js("document.querySelector('#updateActions .btn-secondary').click(); 1")
check("Later closes the offer", not is_open("updateOverlay"))
check("and is kept, for today", until(
    lambda: A.CONFIG.get("update_later") == {"version": "9.9", "day": A._today()}))

before = len(asked)
window_comes_back()
until(lambda: len(asked) > before)
spin(0.3)
check("the window coming back asks GitHub again", len(asked) > before)
check("and says nothing about the version put off today", not is_open("updateOverlay"))

published["version"] = "9.10"
js("_lastUpdateCheck = 0;"
   " Object.defineProperty(document, 'visibilityState', {value: 'visible', configurable: true});"
   " document.dispatchEvent(new Event('visibilitychange')); 1")
check("a newer version than the one put off is offered at once", until(lambda: is_open("updateOverlay")))
check("the newer one", "9.10" in offered())
js("closeTopDialog(); 1")
check("Escape puts it off too", until(
    lambda: (A.CONFIG.get("update_later") or {}).get("version") == "9.10"))

before = len(asked)
window_comes_back(throttled=True)
spin(0.5)
check("within a minute of the last check, GitHub is not asked again", len(asked) == before)

published["version"] = "9.20"
window_comes_back()
until(lambda: is_open("updateOverlay"))
js("document.getElementById('updateNowBtn').click(); 1")
check("an update that fails says so", until(
    lambda: js("document.getElementById('updateTitle').textContent") == "Update failed"))
js("document.querySelector('#updateActions .btn-secondary').click(); 1")
check("closing its message puts the offer off, as Later does", until(
    lambda: (A.CONFIG.get("update_later") or {}).get("version") == "9.20"))

published["version"] = "9.30"
js("document.getElementById('pdfOverlay').classList.add('open'); 1")
before = len(asked)
window_comes_back()
spin(0.5)
check("the window coming back never offers over a PDF being read",
      len(asked) == before and not is_open("updateOverlay"))
js("document.getElementById('pdfOverlay').classList.remove('open'); 1")

# ── Settings ▸ Check for updates ────────────────────────────────────────────
js("openSettings(); 1")
until(lambda: is_open("settingsOverlay"))
line = js("document.querySelector('.settings-version').textContent") or ""
check("Settings says which version this is", line == f"This is MedSearch {A.get_local_version()}.")

published["version"] = "9.11"
before = len(asked)
window_comes_back()
spin(0.5)
check("the window coming back never asks over an open dialog",
      len(asked) == before and not is_open("updateOverlay"))

# A failed update earlier in the session leaves its own title and button behind.
js("document.getElementById('updateTitle').textContent = 'Update failed';"
   " document.getElementById('updateActions').innerHTML ="
   " '<button class=\"btn-secondary\" onclick=\"closeUpdate()\">Close</button>'; 1")
js("document.getElementById('updateCheckBtn').click(); 1")
check("it offers even a version put off today", until(lambda: is_open("updateOverlay")))
check("as a fresh offer, whatever an earlier update left behind",
      js("document.getElementById('updateTitle').textContent") == "Update available"
      and bool(js("!!document.getElementById('updateNowBtn')")))
check("over Settings, which stays open", is_open("settingsOverlay"))
js("closeUpdate(); 1")
until(lambda: js("!document.getElementById('updateCheckBtn').disabled"))

published["version"] = A.get_local_version()
js("document.getElementById('updateCheckBtn').click(); 1")
check("it says so when this is the latest version", until(
    lambda: js("document.getElementById('toast').textContent")
    == f"MedSearch {A.get_local_version()} is the latest version."))
check("as a toast, not a popup", not is_open("updateOverlay") and not is_open("failOverlay"))

published["version"] = None
js("document.getElementById('updateCheckBtn').click(); 1")
check("GitHub out of reach is a popup", until(lambda: is_open("failOverlay")))
check("that says what failed",
      js("document.getElementById('failTitle').textContent") == "Couldn't check for updates")
check("the button is ready again after each check", until(
    lambda: js("[document.getElementById('updateCheckBtn').disabled,"
               " document.getElementById('updateCheckBtn').textContent].join('|')")
    == "false|Check for updates"))

server.shutdown()
print("ALL PASS" if not failed else f"{len(failed)} FAILED")
sys.exit(1 if failed else 0)

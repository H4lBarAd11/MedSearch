"""An article window's new tabs and files, in a real WebKit page, without a window.

Run by tests/test_article_windows.py in a process of its own, or directly:
    .venv/bin/python tests/webkit/article_windows_page.py

NO WINDOW, NO DOCK ICON, NOTHING BUT THIS MACHINE. The pages and files come from a
small server on 127.0.0.1 started here; every other address is refused and written
down. Downloads land in a temporary folder, and "open in Preview", "show in Finder"
and the failure dialog are recorded instead of done. Prints one PASS/FAIL line per
check and exits 1 if any failed.
"""
import http.server
import shutil
import socket
import sys
import tempfile
import threading
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from AppKit import NSApplication                                    # noqa: E402
from Foundation import NSObject, NSRunLoop, NSDate, NSURL, NSMakeRect, NSURLRequest  # noqa: E402
import WebKit                                                       # noqa: E402

NSApplication.sharedApplication().setActivationPolicy_(2)          # no Dock icon

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class Files(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype, name=None, length=None):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        if name:
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(length or len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/page":
            self._send(PAGE.encode(), "text/html")
        elif self.path == "/file":
            self._send(PDF, "application/octet-stream", "paper.pdf")
        elif self.path == "/nameless":
            self._send(PDF, "application/octet-stream")
        elif self.path == "/supplement":
            self._send(b"PK\x03\x04 not really a zip", "application/zip", "supplement.zip")
        elif self.path == "/inline.pdf":
            self._send(PDF, "application/pdf")
        elif self.path == "/broken":
            self._send(PDF[:10], "application/octet-stream", "broken.pdf", length=100000)
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_RDWR)
        else:
            self.send_error(404)


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Files)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_port}"
PAGE = """<!doctype html><html><body>
<a id="tab" target="_blank" href="https://publisher.example/article/pdf">PDF (new tab)</a>
<button id="script" onclick="window.open('https://publisher.example/pdfft?x=1')">PDF (script)</button>
<button id="blank" onclick="window.open('')">blank</button>
<a id="file" href="/file">file</a>
<a id="nameless" href="/nameless">nameless</a>
<a id="supplement" href="/supplement">supplement</a>
<a id="inline" href="/inline.pdf">inline</a>
<a id="broken" href="/broken">broken</a>
<button id="built" onclick="window.open(window.URL.createObjectURL(new Blob(['%PDF-1.4'], {type: 'application/pdf'})))">built</button>
</body></html>"""

log = {"nav": [], "base_popup": 0, "finished": 0}


class PywebviewDelegate(NSObject):
    """pywebview's page delegate, reduced to what article_windows builds on."""

    def webView_didFinishNavigation_(self, web, nav):
        log["finished"] += 1

    def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
            self, web, config, action, features):
        log["base_popup"] += 1                     # pywebview: off to Safari
        return None

    def webView_decidePolicyForNavigationAction_decisionHandler_(self, web, action, handler):
        url = str(action.request().URL().absoluteString())
        # A new tab is asked about here first, with no frame yet; pywebview lets it
        # through, and the window itself is then asked for (createWebView…).
        if url.startswith((BASE, "blob:")) or action.targetFrame() is None:
            handler(WebKit.WKNavigationActionPolicyAllow)
        else:
            log["nav"].append(url)
            handler(WebKit.WKNavigationActionPolicyCancel)

    def webView_decidePolicyForNavigationResponse_decisionHandler_(self, web, response, handler):
        handler(WebKit.WKNavigationResponsePolicyAllow if response.canShowMIMEType()
                else WebKit.WKNavigationResponsePolicyCancel)


class _Window:
    kind = "article"


class _Instance:
    uid = "w"
    pywebview_window = _Window


class BrowserView:
    BrowserDelegate = PywebviewDelegate

    @staticmethod
    def get_instance(attr, value):
        return _Instance


for name in ("webview", "webview.platforms", "webview.platforms.cocoa"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["webview.platforms.cocoa"].BrowserView = BrowserView

import article_windows  # noqa: E402

DOWNLOADS = Path(tempfile.mkdtemp(prefix="medsearch-downloads-"))
(DOWNLOADS / "paper.pdf").write_bytes(b"already here")          # must not be replaced
opened, revealed, failed_with, windows = [], [], [], []
article_windows.install(lambda w: w.kind == "article", windows.append, downloads=DOWNLOADS,
                        reveal=revealed.append, open_file=opened.append,
                        fail=lambda window, reason: failed_with.append(reason))

config = WebKit.WKWebViewConfiguration.alloc().init()
config.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
# A click here is a script's, not a person's: let it open windows as a click would.
config.preferences().setJavaScriptCanOpenWindowsAutomatically_(True)
delegate = BrowserView.BrowserDelegate.alloc().init()
web = WebKit.WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, 800, 600), config)
web.setNavigationDelegate_(delegate)
web.setUIDelegate_(delegate)


def spin(seconds=0.05):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))


def until(cond, seconds=5.0):
    for _ in range(int(seconds / 0.05)):
        if cond():
            return True
        spin()
    return cond()


def load_page():
    before = log["finished"]
    web.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(BASE + "/page")))
    until(lambda: log["finished"] > before)


def click(element_id):
    web.evaluateJavaScript_completionHandler_(
        f"document.getElementById('{element_id}').click(); 1", None)


failed = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        failed.append(name)


load_page()
click("tab")
check("a new-tab link opens a MedSearch window",
      until(lambda: windows == ["https://publisher.example/article/pdf"]))
click("script")
check("a window opened by a script opens a MedSearch window",
      until(lambda: windows[-1:] == ["https://publisher.example/pdfft?x=1"]))
click("blank")
spin(0.5)
check("a blank window to be written into opens nothing", len(windows) == 2)
check("nothing went to Safari", log["base_popup"] == 0)

click("file")
check("a PDF sent as a file is opened in Preview",
      until(lambda: [p.name for p in opened] == ["paper (2).pdf"]))
check("it did not replace a file already in Downloads",
      (DOWNLOADS / "paper.pdf").read_bytes() == b"already here")
check("what was saved is the PDF, with the sign-in's session",
      (DOWNLOADS / "paper (2).pdf").read_bytes() == PDF)

load_page()
click("nameless")
check("a PDF sent without a name is named .pdf and opened",
      until(lambda: [p.name for p in opened][-1:] == ["nameless.pdf"]))

load_page()
click("supplement")
check("any other file is shown in the Finder, not opened",
      until(lambda: [p.name for p in revealed] == ["supplement.zip"]) and len(opened) == 2)

load_page()
click("broken")
check("a download that breaks off says so", until(lambda: len(failed_with) == 1, 15))
check("and nothing half-downloaded is opened", len(opened) == 2)
check("or left in Downloads", not (DOWNLOADS / "broken.pdf").exists())

load_page()
finished = log["finished"]
click("inline")
check("a PDF the page can show is shown, not downloaded",
      until(lambda: log["finished"] > finished) and len(opened) == 2
      and str(web.URL().absoluteString()).endswith("/inline.pdf"))

load_page()
finished = log["finished"]
click("built")
check("a PDF the page built itself is shown in the same window",
      until(lambda: str(web.URL().absoluteString()).startswith("blob:")) and len(windows) == 2)

# The main window keeps pywebview's own behaviour.
_Window.kind = "main"
load_page()
click("tab")
check("the main window's new-tab link still goes pywebview's way",
      until(lambda: log["base_popup"] == 1) and len(windows) == 2)

server.shutdown()
shutil.rmtree(DOWNLOADS, ignore_errors=True)
print("ALL PASS" if not failed else f"{len(failed)} FAILED")
sys.exit(1 if failed else 0)

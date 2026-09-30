"""Search by DOI in the real MedSearch page, in WebKit, without a window.

Run by tests/test_doi_search.py in a process of its own, or directly:
    .venv/bin/python tests/webkit/doi_search_page.py

NO WINDOW, NO DOCK ICON, NO NETWORK. MedSearch's own server runs here on a free
127.0.0.1 port, with HOME in a temporary folder, the databases and Crossref
faked, and the page is loaded into a web view that is never put in a window.
Prints one PASS/FAIL line per check and exits 1 if any failed.
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

HOME = tempfile.mkdtemp(prefix="medsearch-doi-")
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

# PubMed has 10.1000/found, and any ordinary search finds one paper; Crossref
# has 10.1000/crossref and has never heard of 10.1000/typo.
def pubmed(query, max_r, y_from, y_to, **kw):
    if '"10.1000/found"[AID]' in query or not query.startswith('"'):
        return [A._article(title="Found in PubMed", doi="10.1000/found", source="PubMed",
                           access_kind="none")], 1
    return [], 0


def crossref_records(dois, report=None):
    report["unknown"] = [d for d in dois if d == "10.1000/typo"]
    report["failed"] = []
    return [A._article(title="Found at Crossref", doi=d, source="Crossref", access_kind="none")
            for d in dois if d == "10.1000/crossref"], 0


def nothing(query, max_r, y_from, y_to, **kw):
    return [], 0


A.SOURCES = [(k, l, pubmed if k == "pubmed" else nothing, s) for k, l, f, s in A.SOURCES]
A.crossref_records = crossref_records
A.get_mesh = lambda q: []
A.enrich_access = lambda arts: arts
A.http_get = lambda *a, **k: (None, 0)
A.fetch_json = lambda *a, **k: (None, 0)
A._published_commit = lambda: None          # GitHub out of reach: no update offer
A.CONFIG["onboarding_seen"] = True
A.CONFIG["search_sources"] = ["pubmed", "clinicaltrials"]

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


def search(query):
    """Type `query` in the box, press Search, and wait for the search to end."""
    js("if (document.getElementById('failOverlay').classList.contains('open')) closeFail(); 1")
    js(f"document.getElementById('searchInput').value = {query!r};"
       " document.getElementById('searchBtn').click(); 1")
    return until(lambda: js("searchRunning === false && !!document.getElementById('sourceGroups')"
                            " && !document.querySelector('.source-spinner')"), 10)


def text(selector):
    return js(f"(document.querySelector({selector!r}) || {{}}).textContent || ''") or ""


def is_open(overlay):
    return bool(js(f"document.getElementById('{overlay}').classList.contains('open')"))


failed = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        failed.append(name)


web.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(f"http://127.0.0.1:{PORT}/")))
# Not document.readyState alone: the blank page before the load is "complete" too.
check("the page loads", until(lambda: js("document.readyState === 'complete'"
                                         " && typeof runSearch === 'function'"), 20))
# Outside a window WebKit never advances an animation, so a dialog would never
# finish closing: run without them, as the page does under Reduce motion.
js("Element.prototype.animate = null; 1")

# ── One DOI a ticked database has, one only Crossref has ────────────────────
check("a DOI search runs to the end", search("10.1000/found, https://doi.org/10.1000/crossref"))
check("both papers are shown", js("document.querySelectorAll('.article-card').length") == 2)
check("the one no database had, in a Crossref group",
      "Found at Crossref" in text("#grp_Crossref .source-body"))
check("ClinicalTrials.gov says it can't be searched by DOI",
      text("#grp_ClinicalTrialsgov .source-body").strip() == "Can't be searched by DOI.")
check("which is a note, not a failure: no dialog", not is_open("failOverlay"))
check("there is no Find more after a DOI search", not js("!!document.getElementById('loadMoreWrap')"))

# ── A DOI nobody knows ──────────────────────────────────────────────────────
search("10.1000/typo")
check("a DOI nobody knows opens a dialog", until(lambda: is_open("failOverlay")))
check("titled DOI not found", text("#failTitle") == "DOI not found")
check("that names it and asks for a typo check",
      "10.1000/typo" in text("#failText") and "check it for a typo" in text("#failText"))
check("the empty list asks for the DOI to be checked, not the dates",
      text(".empty-sub") == "Check the DOI for a typo.")

# ── An ordinary search afterwards is ordinary again ─────────────────────────
search("glioma")
check("an ordinary search after a DOI search offers Find more",
      js("!!document.getElementById('loadMoreWrap')") and not is_open("failOverlay"))

server.shutdown()
print("ALL PASS" if not failed else f"{len(failed)} FAILED")
sys.exit(1 if failed else 0)

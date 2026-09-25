# MedSearch — what an article window does with new tabs and files.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""Article windows keep your library sign-in for the PDF too.

WHAT WENT WRONG. pywebview sends a link that opens a new tab to Safari, which
has none of the session the article window signed in with, so the library asked
for the login again. A button that opens its new window from a script got no
window at all, and a PDF the site hands over as a file rather than a page to
show was dropped without a word. Most publishers' "PDF" buttons do one of the
three, so the PDF "never opened".

OVID TOOK THREE MORE TRIES, and the PDF-button log is what settled it. Its button
opens the PDF's address in a new window. Opened as a separate pywebview window,
that address was first never shown at all (pywebview builds nothing when asked
from the main thread, where WebKit asks), and then, once shown, Ovid sent it
straight back to the article: a window the article page did not open itself is
not one Ovid serves the PDF to.

WHAT THEY DO NOW (his choices). Every new tab or window a page asks for gets the
window WebKit asked for: MedSearch builds it on WebKit's own configuration and
hands it back, and WebKit loads it as the page meant, as Safari does, with the
page as its opener and the same sign-in (every window shares the cookies); the
article stays open behind it. A PDF the page built itself is shown in place. A
file is saved to Downloads by WebKit itself, so with the same sign-in; a PDF is
then opened in the Mac's PDF app (Preview), anything else is shown in the
Finder, never opened on its own. A download that fails says so in a dialog on
that window, and leaves no half a file behind.

ONLY ARTICLE WINDOWS. MedSearch's own window keeps pywebview's behaviour: its
plain DOI and PubMed links are meant to open in the browser.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

#: The first bytes of every PDF.
PDF_MAGIC = b"%PDF-"
#: What marks a window MedSearch built itself for a page, so the menu bar item
#: counts it as open (statusbar.py), like pywebview's own windows.
WINDOW_ID = "medsearch.article"


def safe_name(suggested: str) -> str:
    """A file name the server suggested, reduced to a plain name: no folders, no
    leading dots, nothing empty."""
    name = os.path.basename((suggested or "").replace("\\", "/")).strip().lstrip(".")
    name = "".join(c for c in name if c >= " " and c not in ':/"')
    return name or "download"


def free_path(folder: Path, name: str) -> Path:
    """`name` in `folder`, or "name (2).ext", "name (3).ext"… if it is taken:
    a download never replaces a file already there."""
    path = folder / name
    stem, ext = os.path.splitext(name)
    n = 2
    while path.exists():
        path = folder / f"{stem} ({n}){ext}"
        n += 1
    return path


def is_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(len(PDF_MAGIC)) == PDF_MAGIC
    except OSError:
        return False


def finished(path: Path) -> tuple[Path, bool]:
    """A finished download: (where it is, whether it is a PDF). A PDF sent under
    another name ("download", "file.bin") is given .pdf, so Preview opens it."""
    pdf = is_pdf(path)
    if pdf and path.suffix.lower() != ".pdf":
        target = free_path(path.parent, path.name + ".pdf")
        try:
            path.rename(target)
            path = target
        except OSError:
            pass
    return path, pdf


def loads_in_place(url: str) -> bool:
    """A new tab whose content only exists for the page that made it (a PDF the
    page built itself): shown in the same window, where that content lives."""
    return url.lower().startswith(("blob:", "data:"))


# ── TEMPORARY: the PDF-button log ───────────────────────────────────────────
# Asked for 25 Sep, to see what Ovid's PDF button does after two fixes did not
# reach it. Remove this section, its hooks below (marked "diagnostic") and the
# log_path argument in app.py once Ovid's PDF opens.
#
# WHAT IS WRITTEN, AND WHAT NOT. Only the 20 s after a click on something that
# says PDF: what was clicked (its markup, link, script, form), and every page,
# window and file the article windows then ask for, with WebKit's own errors.
# Every value in an address is cut to its first 8 characters, so a session in
# the address is never written whole. The file stays on this Mac, readable only
# by its owner.
DIAG_ARM_S = 20
DIAG_MAX_BYTES = 2_000_000

_QUERY_VALUE = re.compile(r"([?&;][A-Za-z0-9_.\-]+=)([^&;\"'\s<>]{8})[^&;\"'\s<>]+")


def short(text: str) -> str:
    """Addresses in `text` with every query value cut to 8 characters."""
    return _QUERY_VALUE.sub(lambda m: m.group(1) + m.group(2) + "…", str(text or ""))


class DiagLog:
    def __init__(self, path):
        self.path, self.armed_until = Path(path), 0.0

    def write(self, kind, **fields):
        now = time.time()
        if kind == "click":
            self.armed_until = now + DIAG_ARM_S
        elif now > self.armed_until:
            return
        fields = {k: short(v) if isinstance(v, str) else v for k, v in fields.items()}
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {kind}  {json.dumps(fields, ensure_ascii=False)}\n"
        try:
            if self.path.exists() and self.path.stat().st_size > DIAG_MAX_BYTES:
                self.path.write_text("")
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass


#: Runs in every frame of an article window: reports a click on something that
#: says PDF, and what the page then does with windows and forms.
DIAG_SCRIPT = """
(function () {
  if (window.__medsearchDiag) return;
  window.__medsearchDiag = true;
  function post(o) {
    o.frame = location.href;
    try { window.webkit.messageHandlers.browserDelegate.postMessage({ medsearchDiag: o }); } catch (e) {}
  }
  function says(x) {
    if (!x || !x.getAttribute || /^(BODY|HTML)$/.test(x.tagName)) return false;
    var label = String(x.innerText || x.value || '');
    if (label.length > 60) label = '';           // a container, not a button
    var t = label + ' ' + (x.getAttribute('title') || '') + ' '
          + (x.getAttribute('aria-label') || '') + ' ' + (x.getAttribute('href') || '')
          + ' ' + (x.getAttribute('class') || '') + ' ' + (x.getAttribute('id') || '');
    return /pdf/i.test(t);
  }
  document.addEventListener('click', function (e) {
    for (var x = e.target, n = 0; x && n < 6; x = x.parentElement, n++) {
      if (says(x)) {
        var f = x.form || (x.closest && x.closest('form'));
        post({ kind: 'click', tag: x.tagName, html: (x.outerHTML || '').slice(0, 1500),
               href: x.href || '', target: x.target || '',
               onclick: (x.getAttribute('onclick') || '').slice(0, 600),
               form: f ? { action: f.action, method: f.method, target: f.target,
                           fields: Array.prototype.map.call(f.elements, function (i) { return i.name; }).join(',') } : null });
        return;
      }
    }
  }, true);
  var open = window.open;
  window.open = function (u, name, features) {
    var w = open.apply(this, arguments);
    post({ kind: 'window.open', url: String(u || ''), name: String(name || ''),
           features: String(features || ''), got: w ? 'a window' : 'null' });
    return w;
  };
  var submit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function () {
    post({ kind: 'form.submit', action: this.action, method: this.method, target: this.target });
    return submit.apply(this, arguments);
  };
  window.addEventListener('error', function (ev) {
    post({ kind: 'script error', message: String(ev.message), at: String(ev.filename) + ':' + ev.lineno });
  });
  window.addEventListener('unhandledrejection', function (ev) {
    post({ kind: 'script error', message: 'unhandled: ' + String(ev.reason) });
  });
})();
"""


def install(is_article, on_page=None, downloads=None, reveal=None,
            open_file=None, fail=None, present=None, log_path=None) -> None:
    """Teach every article window pywebview builds from now on to keep new tabs
    and files inside MedSearch. `is_article(window)` tells an article window from
    the main one; `on_page(web)`, if given, runs on every page a window of
    MedSearch's own finishes loading (the library sign-in). `downloads`, `reveal`, `open_file`, `fail` and `present` are
    the Downloads folder, "show in Finder", "open in its app", the failure dialog
    and putting a new window on screen, replaceable for the tests. `log_path`,
    if given, is where the temporary PDF-button log is written (diagnostic)."""
    import objc
    import WebKit
    from AppKit import NSAlert, NSApplication, NSBackingStoreBuffered, NSWindow, NSWorkspace
    from Foundation import NSMakeRect, NSObject, NSURL
    from webview.platforms.cocoa import BrowserView

    base = BrowserView.BrowserDelegate
    folder = Path(downloads) if downloads else Path.home() / "Downloads"
    reveal = reveal or (lambda p: NSWorkspace.sharedWorkspace()
                        .activateFileViewerSelectingURLs_([NSURL.fileURLWithPath_(str(p))]))
    open_file = open_file or (lambda p: NSWorkspace.sharedWorkspace()
                              .openURL_(NSURL.fileURLWithPath_(str(p))))
    as_download = getattr(WebKit, "WKNavigationResponsePolicyDownload", None)   # macOS 11.3+

    def tell(window, reason):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("The file couldn't be downloaded")
        alert.setInformativeText_(reason)
        if window is not None:
            alert.beginSheetModalForWindow_completionHandler_(window, None)
        else:
            alert.runModal()
    fail = fail or tell
    keep = set()                      # downloads in flight, and their delegates
    diag = DiagLog(log_path) if log_path else None                           # diagnostic
    watched = set()                   # content controllers that have the script (diagnostic)
    from WebKit import WKUserScript

    def watch(web):                                                          # diagnostic
        """The PDF-button script in every frame of this window from now on, and in
        the page already there."""
        if diag is None:
            return
        controller = web.configuration().userContentController()
        if id(controller) not in watched:
            watched.add(id(controller))
            controller.addUserScript_(WKUserScript.alloc()
                                      .initWithSource_injectionTime_forMainFrameOnly_(
                                          DIAG_SCRIPT, 1, False))   # at document end, all frames
        web.evaluateJavaScript_completionHandler_(DIAG_SCRIPT, None)

    def note(kind, **fields):                                                # diagnostic
        if diag is not None:
            diag.write(kind, **fields)

    def note_action(web, action):                                           # diagnostic
        if diag is None:
            return
        request, frame = action.request(), action.targetFrame()
        note("navigate", url=str(request.URL().absoluteString() or "") if request.URL() else "",
             method=str(request.HTTPMethod() or ""), type=int(action.navigationType()),
             frame="new window" if frame is None else ("main" if frame.isMainFrame() else "sub"))

    def note_response(response):                                            # diagnostic
        if diag is None:
            return
        r = response.response()
        headers = dict(r.allHeaderFields()) if hasattr(r, "allHeaderFields") else {}
        note("response", url=str(r.URL().absoluteString() or ""), mime=str(r.MIMEType() or ""),
             status=int(r.statusCode()) if hasattr(r, "statusCode") else 0,
             shown=bool(response.canShowMIMEType()), main=bool(response.isForMainFrame()),
             disposition=str(headers.get("Content-Disposition", "")))

    def note_failure(web, error):                                           # diagnostic
        if diag is not None and error is not None:
            note("failed", url=str(web.URL().absoluteString() or "") if web.URL() else "",
                 error=str(error.localizedDescription()), domain=str(error.domain()),
                 code=int(error.code()))

    def note_message(body):                                                 # diagnostic
        """True if the page's message was the script's report."""
        if not (hasattr(body, "get") and "medsearchDiag" in body):
            return False
        got = body["medsearchDiag"]
        fields = {str(k): (dict(v) if hasattr(v, "keys") else (str(v) if v is not None else None))
                  for k, v in dict(got).items()}
        kind = fields.pop("kind", "page")
        note(kind, **{k: (json.dumps({str(a): str(b) for a, b in v.items()}) if isinstance(v, dict) else v)
                      for k, v in fields.items()})
        return True

    def article(web):
        inst = BrowserView.get_instance("webview", web)
        return inst is not None and bool(is_article(inst.pywebview_window))

    class Download(NSObject):
        def download_decideDestinationUsingResponse_suggestedFilename_completionHandler_(
                self, download, response, suggested, handler):
            try:
                folder.mkdir(parents=True, exist_ok=True)
                self.path = free_path(folder, safe_name(str(suggested or "")))
                handler(NSURL.fileURLWithPath_(str(self.path)))
            except Exception as e:
                print(f"  (download not saved: {e})")
                self.path = None
                handler(None)

        def downloadDidFinish_(self, download):
            keep.discard(self)
            if getattr(self, "path", None) is None:
                return
            path, pdf = finished(self.path)
            try:
                (open_file if pdf else reveal)(path)
            except Exception as e:
                print(f"  (download saved to {path}, not opened: {e})")

        def download_didFailWithError_resumeData_(self, download, error, resume):
            keep.discard(self)
            # What arrived before it broke off is not a file anyone can open.
            path = getattr(self, "path", None)
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            web = download.webView() if hasattr(download, "webView") else None
            reason = str(error.localizedDescription()) if error is not None else "unknown reason"
            print(f"  (download failed: {reason})")
            try:
                fail(web.window() if web is not None else None, reason)
            except Exception:
                pass

    def attach(download):
        d = Download.alloc().init()
        keep.add(d)
        download.setDelegate_(d)

    def show(window):
        window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    present = present or show
    windows = set()                   # MedSearch's own windows for a page's new tab

    def new_tab(web, config, action):
        """What a page's new tab or window becomes (see the module's docstring)."""
        request = action.request()
        url = str(request.URL().absoluteString() or "") if request.URL() else ""
        note("new window", url=url, method=str(request.HTTPMethod() or ""),       # diagnostic
             type=int(action.navigationType()))
        if loads_in_place(url):
            # Only the page may open what it built: WebKit ignores a blob
            # address loaded from outside, so the page is asked to go there.
            web.evaluateJavaScript_completionHandler_(
                "location.assign(%s)" % json.dumps(url), None)
            return None
        return own_window(web, config)

    def own_window(opener, config):
        """The new window WebKit asked for, built on its own configuration and
        handed back: WebKit then loads it as the page meant, a plain address, a
        form's reply or an empty window the page fills in, with the page as its
        opener and the same sign-in."""
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 1100, 860), 1 | 2 | 4 | 8, NSBackingStoreBuffered, False)
        window.setReleasedWhenClosed_(False)
        window.setTitle_("MedSearch — Article")
        window.setMinSize_((800, 600))
        window.setIdentifier_(WINDOW_ID)
        there = opener.window() if opener is not None else None
        if there is not None:
            f = there.frame()
            window.cascadeTopLeftFromPoint_((f.origin.x, f.origin.y + f.size.height))
        else:
            window.center()
        web = WebKit.WKWebView.alloc().initWithFrame_configuration_(
            window.contentView().bounds(), config)
        web.setAutoresizingMask_(2 | 16)          # width and height follow the window
        pages, closer = OwnPages.alloc().init(), Closer.alloc().init()
        web.setNavigationDelegate_(pages)
        web.setUIDelegate_(pages)
        window.setContentView_(web)
        window.setDelegate_(closer)
        closer.held = (window, web, pages, closer)
        windows.add(closer.held)
        present(window)
        return web

    class Closer(NSObject):
        def windowWillClose_(self, note):
            held = getattr(self, "held", None)
            if held is not None:
                windows.discard(held)
                held[1].setNavigationDelegate_(None)
                held[1].setUIDelegate_(None)

    class OwnPages(NSObject):
        """The pages of a window MedSearch built itself: everything allowed, files
        downloaded as in any article window, the page may close its window, and
        its alerts and questions are shown."""

        def webView_decidePolicyForNavigationAction_decisionHandler_(self, web, action, handler):
            note_action(web, action)                                         # diagnostic
            handler(WebKit.WKNavigationActionPolicyAllow)

        def webView_decidePolicyForNavigationResponse_decisionHandler_(self, web, response, handler):
            note_response(response)                                          # diagnostic
            if response.canShowMIMEType():
                handler(WebKit.WKNavigationResponsePolicyAllow)
            elif as_download is not None:
                handler(as_download)
            else:
                handler(WebKit.WKNavigationResponsePolicyCancel)

        def webView_navigationResponse_didBecomeDownload_(self, web, response, download):
            attach(download)

        def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
                self, web, config, action, features):
            return new_tab(web, config, action)

        def webView_didReceiveServerRedirectForProvisionalNavigation_(self, web, nav):
            note("redirected", to=str(web.URL().absoluteString() or "") if web.URL() else "")  # diagnostic

        def webView_didFailProvisionalNavigation_withError_(self, web, nav, error):
            note_failure(web, error)                                         # diagnostic

        def webView_didFailNavigation_withError_(self, web, nav, error):
            note_failure(web, error)                                         # diagnostic

        def webView_didFinishNavigation_(self, web, nav):
            watch(web)                                                       # diagnostic
            if on_page is not None:
                try:
                    on_page(web)
                except Exception as e:
                    print(f"  (sign-in fill skipped: {e})")

        def webViewWebContentProcessDidTerminate_(self, web):
            web.reload()

        def webViewDidClose_(self, web):
            if web.window() is not None:
                web.window().close()

        def webView_runJavaScriptAlertPanelWithMessage_initiatedByFrame_completionHandler_(
                self, web, message, frame, handler):
            alert = NSAlert.alloc().init()
            alert.setMessageText_(str(message))
            alert.runModal()
            handler()

        def webView_runJavaScriptConfirmPanelWithMessage_initiatedByFrame_completionHandler_(
                self, web, message, frame, handler):
            alert = NSAlert.alloc().init()
            alert.setMessageText_(str(message))
            alert.addButtonWithTitle_("OK")
            alert.addButtonWithTitle_("Cancel")
            handler(alert.runModal() == 1000)     # the first button

    class MedSearchArticleDelegate(base):
        def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
                self, web, config, action, features):
            if not article(web):
                return objc.super(MedSearchArticleDelegate, self) \
                    .webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
                        web, config, action, features)
            return new_tab(web, config, action)

        def webView_decidePolicyForNavigationAction_decisionHandler_(self, web, action, handler):
            if article(web):
                note_action(web, action)                                     # diagnostic
            return objc.super(MedSearchArticleDelegate, self) \
                .webView_decidePolicyForNavigationAction_decisionHandler_(web, action, handler)

        def webView_didReceiveServerRedirectForProvisionalNavigation_(self, web, nav):
            if article(web):                                                 # diagnostic
                note("redirected", to=str(web.URL().absoluteString() or "") if web.URL() else "")

        def webView_didFailProvisionalNavigation_withError_(self, web, nav, error):
            if article(web):
                note_failure(web, error)                                     # diagnostic

        def webView_didFailNavigation_withError_(self, web, nav, error):
            if article(web):
                note_failure(web, error)                                     # diagnostic

        def webView_didFinishNavigation_(self, web, nav):
            objc.super(MedSearchArticleDelegate, self).webView_didFinishNavigation_(web, nav)
            if article(web):
                watch(web)                                                   # diagnostic

        def userContentController_didReceiveScriptMessage_(self, controller, message):
            if note_message(message.body()):                                 # diagnostic
                return
            objc.super(MedSearchArticleDelegate, self) \
                .userContentController_didReceiveScriptMessage_(controller, message)

        def webView_decidePolicyForNavigationResponse_decisionHandler_(self, web, response, handler):
            if article(web):
                note_response(response)                                      # diagnostic
            if as_download is None or response.canShowMIMEType() or not article(web):
                return objc.super(MedSearchArticleDelegate, self) \
                    .webView_decidePolicyForNavigationResponse_decisionHandler_(web, response, handler)
            handler(as_download)

        def webView_navigationResponse_didBecomeDownload_(self, web, response, download):
            attach(download)

    BrowserView.BrowserDelegate = MedSearchArticleDelegate

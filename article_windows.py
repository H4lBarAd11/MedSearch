# MedSearch — what an article window does with new tabs and files.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""Article windows keep your library sign-in for the PDF too.

WHAT WENT WRONG. pywebview sends a link that opens a new tab to Safari, which
has none of the session the article window signed in with, so the library asked
for the login again. A button that opens its new window from a script got no
window at all, and a PDF the site hands over as a file rather than a page to
show was dropped without a word. Most publishers' "PDF" buttons do one of the
three, so the PDF "never opened".

OVID TOOK THREE MORE TRIES, settled by a temporary log of what its button did.
Its button opens the PDF's address in a new window. Opened as a separate
pywebview window, that address was first never shown at all (pywebview builds
nothing when asked from the main thread, where WebKit asks), and then, once
shown, Ovid sent it straight back to the article: a window the article page did
not open itself is not one Ovid serves the PDF to.

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


def install(is_article, on_page=None, downloads=None, reveal=None,
            open_file=None, fail=None, present=None) -> None:
    """Teach every article window pywebview builds from now on to keep new tabs
    and files inside MedSearch. `is_article(window)` tells an article window from
    the main one; `on_page(web)`, if given, runs on every page a window of
    MedSearch's own finishes loading (the library sign-in). `downloads`, `reveal`, `open_file`, `fail` and `present` are
    the Downloads folder, "show in Finder", "open in its app", the failure dialog
    and putting a new window on screen, replaceable for the tests."""
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
            handler(WebKit.WKNavigationActionPolicyAllow)

        def webView_decidePolicyForNavigationResponse_decisionHandler_(self, web, response, handler):
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

        def webView_didFinishNavigation_(self, web, nav):
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

        def webView_decidePolicyForNavigationResponse_decisionHandler_(self, web, response, handler):
            if as_download is None or response.canShowMIMEType() or not article(web):
                return objc.super(MedSearchArticleDelegate, self) \
                    .webView_decidePolicyForNavigationResponse_decisionHandler_(web, response, handler)
            handler(as_download)

        def webView_navigationResponse_didBecomeDownload_(self, web, response, download):
            attach(download)

    BrowserView.BrowserDelegate = MedSearchArticleDelegate

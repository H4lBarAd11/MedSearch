# MedSearch — what an article window does with new tabs and files.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""Article windows keep your library sign-in for the PDF too.

WHAT WENT WRONG. pywebview sends a link that opens a new tab to Safari, which
has none of the session the article window signed in with, so the library asked
for the login again. A button that opens its new window from a script got no
window at all, and a PDF the site hands over as a file rather than a page to
show was dropped without a word. Most publishers' "PDF" buttons do one of the
three, so the PDF "never opened".

WHAT THEY DO NOW (his choices). A new tab opens as a new MedSearch window, which
shares the sign-in (every window uses the same cookies), with the article left
open behind it. A file is saved to Downloads by WebKit itself, so with the same
sign-in; a PDF is then opened in the Mac's PDF app (Preview), anything else is
shown in the Finder, never opened on its own. A download that fails says so in
a dialog on that window, and leaves no half a file behind.

ONLY ARTICLE WINDOWS. MedSearch's own window keeps pywebview's behaviour: its
plain DOI and PubMed links are meant to open in the browser.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

#: The first bytes of every PDF.
PDF_MAGIC = b"%PDF-"


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


def opens_as_window(url: str, method: str) -> bool:
    """A new tab that becomes a new MedSearch window: an ordinary web address
    asked for plainly. A blank page to be written into, or a form's reply, has
    no address to open again, so it is not."""
    return (method or "GET").upper() == "GET" and url.lower().startswith(("http://", "https://"))


def loads_in_place(url: str) -> bool:
    """A new tab whose content only exists for the page that made it (a PDF the
    page built itself): shown in the same window, where that content lives."""
    return url.lower().startswith(("blob:", "data:"))


def install(is_article, open_window, downloads=None, reveal=None, open_file=None,
            fail=None) -> None:
    """Teach every article window pywebview builds from now on to keep new tabs
    and files inside MedSearch. `is_article(window)` tells an article window from
    the main one; `open_window(url)` opens a new article window. `downloads`,
    `reveal`, `open_file` and `fail` are the Downloads folder, "show in Finder",
    "open in its app" and the failure dialog, replaceable for the tests."""
    import objc
    import WebKit
    from AppKit import NSAlert, NSWorkspace
    from Foundation import NSObject, NSURL
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

    class MedSearchArticleDelegate(base):
        def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
                self, web, config, action, features):
            if not article(web):
                return objc.super(MedSearchArticleDelegate, self) \
                    .webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(
                        web, config, action, features)
            request = action.request()
            url = str(request.URL().absoluteString() or "") if request.URL() else ""
            if opens_as_window(url, str(request.HTTPMethod() or "GET")):
                open_window(url)
            elif loads_in_place(url):
                # Only the page may open what it built: WebKit ignores a blob
                # address loaded from outside, so the page is asked to go there.
                web.evaluateJavaScript_completionHandler_(
                    "location.assign(%s)" % json.dumps(url), None)
            return None

        def webView_decidePolicyForNavigationResponse_decisionHandler_(self, web, response, handler):
            if as_download is None or response.canShowMIMEType() or not article(web):
                return objc.super(MedSearchArticleDelegate, self) \
                    .webView_decidePolicyForNavigationResponse_decisionHandler_(web, response, handler)
            handler(as_download)

        def webView_navigationResponse_didBecomeDownload_(self, web, response, download):
            d = Download.alloc().init()
            keep.add(d)
            download.setDelegate_(d)

    BrowserView.BrowserDelegate = MedSearchArticleDelegate

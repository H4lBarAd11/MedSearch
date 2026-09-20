# MedSearch — the menu bar item.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""MedSearch's icon in the macOS menu bar, drawn by MedSearch itself.

ONE APP, NOT TWO. This used to be a separate application (menubar.py, built with
py2app). It was frozen at build time, so it never received an update and drifted
away from the app it drove. It is now part of the main process: the same code, the
same update, and no second thing to install.

NATIVE, ON PURPOSE. A real NSStatusItem and NSMenu, with no custom colours or fonts,
so the system draws them in its own style (Liquid Glass on Tahoe, the classic menu on
older macOS). The app's own look stays in its window.

CLOSING THE WINDOW HIDES IT (his choice, 19 Sep). MedSearch keeps running in the
menu bar, ready for a quick search. While the window is hidden, the Dock icon goes
away too, as it does for any menu bar app. Quitting (the menu's Quit, ⌘Q, the Dock,
logging out) still quits, see `closing` below.

Everything here runs on the main thread: AppKit requires it. The page is driven
through pywebview from a worker thread, because evaluate_js waits on the main
thread for its answer.
"""
import inspect
import json
import threading

import objc
from AppKit import (NSAlert, NSAlertFirstButtonReturn, NSApp, NSImage, NSMenu,
                    NSMenuItem, NSStatusBar, NSTextField, NSVariableStatusItemLength)
from Foundation import NSMakeRect, NSObject, NSSize
from PyObjCTools import AppHelper

# NSApplicationActivationPolicy: Regular shows a Dock icon, Accessory does not.
_REGULAR, _ACCESSORY = 0, 1

# The sources a quick search can target (key, label), in the order the menu lists them.
SOURCES = [
    ("pubmed",         "PubMed"),
    ("guidelines",     "Guidelines"),
    ("cochrane",       "Cochrane"),
    ("clinicaltrials", "ClinicalTrials.gov"),
    ("arxiv",          "arXiv"),
    ("scopus",         "Scopus"),
    ("wos",            "Web of Science"),
    ("all",            "All sources"),
]
_LABELS = dict(SOURCES)
_RECENTS_SHOWN = 6

_host = None   # the one StatusBar; module-level so nothing collects it


class _Target(NSObject):
    """The Objective-C side of the menu: every item's action lands here."""

    def initWithHost_(self, host):
        self = objc.super(_Target, self).init()
        if self is None:
            return None
        self.host = host
        return self

    def search_(self, sender):
        self.host.quick_search()

    def recent_(self, sender):
        self.host.run(str(sender.representedObject()))

    def source_(self, sender):
        self.host.set_source(str(sender.representedObject()))

    def openWindow_(self, sender):
        self.host.show()

    def quit_(self, sender):
        NSApp.terminate_(None)

    # NSMenuDelegate: rebuilt each time it opens, so recents are never stale.
    def menuNeedsUpdate_(self, menu):
        self.host.fill(menu)


class StatusBar:
    def __init__(self, window, *, icon_path, recent_searches, get_source, set_source):
        self.window = window                    # the pywebview main window
        self.recent_searches = recent_searches  # () -> [query, ...], newest first
        self.get_source = get_source            # () -> source key
        self.save_source = set_source           # (key) -> None
        self.target = _Target.alloc().initWithHost_(self)

        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength)
        image = NSImage.alloc().initWithContentsOfFile_(str(icon_path)) if icon_path else None
        if image is not None:
            image.setTemplate_(True)            # the system tints it for light and dark
            image.setSize_(NSSize(18, 18))
            self.item.button().setImage_(image)
        else:
            self.item.button().setTitle_("MedSearch")
        self.item.button().setToolTip_("MedSearch")

        self.menu = NSMenu.alloc().init()
        self.menu.setDelegate_(self.target)
        self.menu.setAutoenablesItems_(False)
        self.fill(self.menu)
        self.item.setMenu_(self.menu)

    # ── the menu ────────────────────────────────────────────────────────────
    def _add(self, menu, title, action=None, obj=None, checked=False):
        mi = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
        if action:
            mi.setTarget_(self.target)
        if obj is not None:
            mi.setRepresentedObject_(obj)
        if checked:
            mi.setState_(1)
        menu.addItem_(mi)
        return mi

    def fill(self, menu):
        menu.removeAllItems()
        self._add(menu, "Search MedSearch…", "search:")
        menu.addItem_(NSMenuItem.separatorItem())

        recents = self.recent_searches()[:_RECENTS_SHOWN]
        if recents:
            sub = NSMenu.alloc().init()
            sub.setAutoenablesItems_(False)
            for q in recents:
                self._add(sub, q if len(q) <= 60 else q[:57] + "…", "recent:", q)
            self._add(menu, "Recent searches").setSubmenu_(sub)

        sub = NSMenu.alloc().init()
        sub.setAutoenablesItems_(False)
        current = self.get_source()
        for key, label in SOURCES:
            self._add(sub, label, "source:", key, checked=(key == current))
        self._add(menu, "Default source").setSubmenu_(sub)

        menu.addItem_(NSMenuItem.separatorItem())
        self._add(menu, "Open MedSearch window", "openWindow:")
        menu.addItem_(NSMenuItem.separatorItem())
        self._add(menu, "Quit MedSearch", "quit:")

    # ── actions ─────────────────────────────────────────────────────────────
    def _ns_window(self):
        try:
            from webview.platforms.cocoa import BrowserView
            inst = BrowserView.instances.get(self.window.uid)
            return inst.window if inst else None
        except Exception:
            return None

    def show(self):
        """Bring the window back from wherever it is: hidden in the menu bar,
        minimised in the Dock, or merely behind something else."""
        NSApp.setActivationPolicy_(_REGULAR)
        w = self._ns_window()
        if w is not None:
            # makeKeyAndOrderFront: does NOT restore a minimised window, so a
            # window minimised to the Dock would stay there (this is exactly
            # what a second launch asks /focus to undo).
            if w.isMiniaturized():
                w.deminiaturize_(None)
            w.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        return w is not None

    def hide(self):
        w = self._ns_window()
        if w is not None:
            w.orderOut_(None)
        # No Dock icon while nothing is on screen: MedSearch lives in the menu bar.
        # An article window still open keeps it, so that window stays reachable.
        # pywebview's own list, not NSApp.windows(): that one also holds the
        # status item's menu and other AppKit windows, and any of them would
        # look like "something is still on screen".
        if not self._other_windows_visible():
            NSApp.setActivationPolicy_(_ACCESSORY)

    def _other_windows_visible(self):
        try:
            import webview
            from webview.platforms.cocoa import BrowserView
            for win in list(webview.windows):
                if win is self.window:
                    continue
                inst = BrowserView.instances.get(win.uid)
                if inst is not None and inst.window.isVisible():
                    return True
        except Exception:
            pass
        return False

    def run(self, query, source=None):
        """Show the window and run the search in it, as the page's own Search does."""
        self.show()
        src = source or self.get_source()
        js = f"runSearchWithSource({json.dumps(query)}, {json.dumps(src)}, 0)"
        threading.Thread(target=lambda: self.window.evaluate_js(js), daemon=True).start()

    def set_source(self, key):
        self.save_source(key)

    def quick_search(self):
        NSApp.activateIgnoringOtherApps_(True)
        alert = NSAlert.alloc().init()
        alert.setMessageText_("MedSearch quick search")
        alert.setInformativeText_(
            f"Search {_LABELS.get(self.get_source(), 'PubMed')} "
            "(change the source under Default source in this menu).")
        alert.addButtonWithTitle_("Search")
        alert.addButtonWithTitle_("Cancel")
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 320, 24))
        alert.setAccessoryView_(field)
        alert.window().setInitialFirstResponder_(field)
        if alert.runModal() == NSAlertFirstButtonReturn:
            query = str(field.stringValue()).strip()
            if query:
                self.run(query)

    # ── closing the window hides it; quitting still quits ──────────────────
    def closing(self):
        """pywebview's `closing` handler for the main window. Returning False keeps
        the window open (and here hides it instead); anything else lets it close.

        The same event fires for a real quit: ⌘Q, Quit in the Dock, logging out or
        shutting down all reach applicationShouldTerminate_, which asks every window
        whether it may close. Refusing there would stop the Mac from shutting down.
        The handler runs synchronously inside that call, so the call stack says
        which case this is."""
        if any(f.function == "applicationShouldTerminate_" for f in inspect.stack()):
            return True
        AppHelper.callAfter(self.hide)
        return False


def install(window, *, background=False, **kwargs):
    """Create the menu bar item. Call on the main thread, once the window exists.
    `background` starts with the window hidden (MedSearch opened at login)."""
    global _host
    _host = StatusBar(window, **kwargs)
    window.events.closing += _host.closing
    if background:
        _host.hide()
    return _host

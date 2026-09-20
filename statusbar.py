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

THE DOCK ICON COMES AND GOES BY CHANGING THE ACTIVATION POLICY, and AppKit can take
the menu bar item off the bar along with it: the app carries on running with no icon
to click, which is what closing and reopening the window kept doing. So the policy is
changed in one place (`_set_policy`), never when it is already what we want, and the
item is checked afterwards and built again if it went. Re-seating an item that is
still there would make it flicker, so the check has to be the thing that decides.

Everything here runs on the main thread: AppKit requires it. The page is driven
through pywebview from a worker thread, because evaluate_js waits on the main
thread for its answer.
"""
import datetime
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
_CHECK_EVERY = 3.0     # seconds between "is the item still on the bar?"
_REBUILD_LIMIT = 10    # after this many, stop fighting whatever is removing it

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
    def __init__(self, window, *, icon_path, recent_searches, get_source, set_source,
                 log_path=None):
        self.window = window                    # the pywebview main window
        self.recent_searches = recent_searches  # () -> [query, ...], newest first
        self.get_source = get_source            # () -> source key
        self.save_source = set_source           # (key) -> None
        self.icon_path = icon_path              # kept: the item may be built again
        self.log_path = log_path                # where a disappearance is recorded
        self.target = _Target.alloc().initWithHost_(self)
        self.item = None
        self._last_state = None
        self._misses = 0                        # consecutive checks that found it gone
        self.rebuilds = 0                       # how often it has had to be put back
        self._make_item()
        self._watch()

    # ── the item on the bar ─────────────────────────────────────────────────
    def _make_item(self):
        """Put MedSearch on the menu bar. Called again if AppKit takes it off."""
        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength)
        image = (NSImage.alloc().initWithContentsOfFile_(str(self.icon_path))
                 if self.icon_path else None)
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

    def on_the_bar(self):
        """Is the item actually on the menu bar?

        Measured, not assumed: an item the status bar has let go still answers
        every obvious question as though nothing happened — it keeps its button,
        the button keeps its window, `isVisible` stays true and the length is
        unchanged. The one thing that flips is the window it draws in, which
        stops being visible. That is the test, because it is the only one that
        is true of an item on the bar and false of an item that has left it."""
        try:
            if self.item is None:
                return False
            button = self.item.button()
            window = button.window() if button is not None else None
            return window is not None and bool(window.isVisible())
        except Exception:
            return False

    def _reseat(self):
        """Build the item again, but only if it really went."""
        if self.on_the_bar():
            return
        old, self.item = self.item, None
        if old is not None:
            try:
                NSStatusBar.systemStatusBar().removeStatusItem_(old)
            except Exception:
                pass
        self._make_item()

    def _set_policy(self, policy):
        """Show or hide the Dock icon, and keep the menu bar item through it.

        Setting the policy it already has is not free — it is one of the things
        that drops the item — so it is not done. After a real change the item is
        checked twice: once the run loop has turned (AppKit removes it on its own
        time, not inside the call), and once more half a second later, which is
        the one that catches a slow transition."""
        try:
            if NSApp.activationPolicy() == policy:
                return
            NSApp.setActivationPolicy_(policy)
        except Exception:
            return
        AppHelper.callAfter(self._reseat)
        AppHelper.callLater(0.5, self._reseat)

    # ── the item disappearing, watched and written down ─────────────────────
    def _log(self, line):
        """A line in ~/.medsearch/menubar.log. The item going is the sort of
        thing that happens while nobody is looking at a terminal, and it has to
        be possible to say afterwards WHEN it went and what the app was doing."""
        if not self.log_path:
            return
        try:
            with open(self.log_path, "a") as fh:
                fh.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {line}\n")
        except Exception:
            pass

    def _state(self):
        """(on the bar, the item's own idea of visible, the activation policy).
        Two questions, not one: AppKit taking the item off the bar and macOS
        hiding it are different failures, and only one of them has a button
        with no window. Logging both is what tells them apart afterwards."""
        visible, policy = "?", "?"
        try:
            if self.item is not None and hasattr(self.item, "isVisible"):
                visible = bool(self.item.isVisible())
        except Exception:
            pass
        try:
            policy = NSApp.activationPolicy()
        except Exception:
            pass
        return self.on_the_bar(), visible, policy

    def _watch(self):
        """Every few seconds: still there? If not, put it back.

        TWICE IN A ROW before rebuilding: a single miss can be the bar in the
        middle of something (a display waking, a space switching), and an item
        rebuilt for no reason can land in a different place on the bar, which
        would be its own small annoyance.

        AND NOT FOREVER: if macOS is the one hiding it — a full menu bar is the
        usual reason — rebuilding cannot win, and an app quietly fighting the
        system every three seconds is worse than an app that says so. After
        `_REBUILD_LIMIT` it stops rebuilding and keeps only the record.

        Only changes are written down, so a quiet day leaves a line or two and
        the day it goes leaves the moment it went."""
        try:
            state = self._state()
            if state != self._last_state:
                self._log("on bar=%s  visible=%s  policy=%s" % state)
                self._last_state = state
            if state[0]:
                self._misses = 0
            else:
                self._misses += 1
                if self._misses >= 2 and self.rebuilds < _REBUILD_LIMIT:
                    self.rebuilds += 1
                    self._log(f"not on the bar — building it again (#{self.rebuilds})")
                    self._reseat()
                    self._misses = 0
                    self._last_state = self._state()
                    self._log("rebuilt: on bar=%s  visible=%s  policy=%s" % self._last_state)
                elif self._misses == 2:
                    self._log(f"not on the bar, and {_REBUILD_LIMIT} rebuilds have not "
                              "helped — leaving it alone. A full menu bar does this.")
        except Exception as e:
            self._log(f"the check itself failed: {e}")
        AppHelper.callLater(_CHECK_EVERY, self._watch)

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
        self._set_policy(_REGULAR)
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
            self._set_policy(_ACCESSORY)

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

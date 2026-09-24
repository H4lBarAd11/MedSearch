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
logging out) still quits, see `closing` below. With the PDF viewer or a dialog open
in the page, closing closes that instead and the window stays (his choice, 24 Sep).

WHEN THE ICON DISAPPEARS IT IS USUALLY STILL THERE (measured 20 Sep, on a MacBook Air
with a notch). An item macOS has no room for is simply never placed: it keeps its
button, keeps its window, keeps answering `isVisible` with true and keeps its length.
The only thing that gives it away is that it sits at x=0. Filling the bar with 26 items
and reading them back is what showed this — eleven were placed, fifteen sat at x=0, and
every one of them called itself visible. That is why `_x` is logged: it is the single
number that separates "it was never given a place" from "it had one and lost it".

AND AN ITEM REFUSED AT BIRTH IS REFUSED FOR GOOD. macOS never comes back to it: the bar
can empty completely and the item stays at x=0 for the life of the app. This is what was
actually happening — quitting MedSearch and starting it again immediately means the new
copy asks for a slot while the old copy still holds one, is refused, and never shows an
icon again however long it runs. So the item asks once more, up to `_REBUILD_LIMIT`
times, and a new item does get a place: reproduced 20 Sep against a deliberately
saturated bar, refused four times, and placed three seconds after a slot came free.

`setAutosaveName_` is a smaller thing alongside: an item with a name is put back where it
was last left, so a place he ⌘-drags it to stays his, across relaunches and rebuilds.

THE ACTIVATION POLICY is set in one place (`_set_policy`) and never set to what it
already is. That is tidiness rather than a cure: it was the first suspect and it was
wrong, and the window being hidden or shown is checked in the same breath.

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
_PAGE_ANSWER_WAIT = 1.0  # seconds a close waits for the page to say it closed a dialog

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

    # The "reopen" Apple event, see `_answer_reopen`.
    @objc.typedSelector(b"v@:@@")
    def reopen_withReplyEvent_(self, event, reply):
        self.host.show()

    # MedSearch came to the front or left it, or its window was minimised or
    # brought back: all four change whether the icon belongs on the bar.
    def frontChanged_(self, note):
        self.host._sync_item()

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
        self._noroom = 0                        # consecutive checks that found no slot
        self.rebuilds = 0                       # how often it has had to be put back
        self._tucked = False                    # off the bar on purpose, see `_sync_item`
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
        # WHERE IT SITS IS HIS TO CHOOSE. ⌘-dragging an item along the menu bar
        # moves it, but only an item with an autosave name is put back where it
        # was left — without one every launch returns it to the newest, leftmost
        # slot, which on a full bar is the first slot macOS hides. It also keeps
        # the place when the item has to be built again.
        try:
            self.item.setAutosaveName_("MedSearch")
        except Exception:
            pass

        self.menu = NSMenu.alloc().init()
        self.menu.setDelegate_(self.target)
        self.menu.setAutoenablesItems_(False)
        self.fill(self.menu)
        self.item.setMenu_(self.menu)
        if self._tucked:
            self.item.setVisible_(False)

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

    def _reseat(self, force=False):
        """Build the item again. Only if it really went, unless forced — an item
        that was refused a slot is still "there", and asking again is the only
        way to get one."""
        if not force and (self._tucked or self.on_the_bar()):
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

    def _x(self):
        """Where the item sits along the menu bar, or -1 if it cannot be asked.

        THIS IS THE ONE THAT TELLS THE TRUTH. An item macOS has no room for is
        never placed: it keeps its window, keeps calling itself visible, and
        sits at x=0. A real place on the bar is a real x."""
        try:
            return int(self.item.button().window().frame().origin.x)
        except Exception:
            return -1

    def _state(self):
        """(on the bar, where, the item's own idea of visible, the policy).

        Three different ways to be missing, and they need telling apart: AppKit
        letting the item go (the window stops being visible), macOS having no
        room for it (x=0, everything else unchanged), and the app simply having
        no Dock icon (the policy). Only the log can say which one happened."""
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
        return self.on_the_bar(), self._x(), visible, policy

    def _watch(self):
        """Every few seconds: still there? If not, put it back.

        TWO WAYS TO BE MISSING, and they are counted separately: the bar can let
        the item go (its window stops being visible), or it can refuse it a slot
        at the moment it was made, which leaves it at x=0 for good. Both end in
        asking for the item's place again; only the log says which happened.

        TWICE IN A ROW before doing anything: a single bad reading is often the
        bar mid-move — a display waking, a space switching — and the first check
        of all runs before AppKit has laid the new item out, so an app that
        believed one reading would shout at every launch.

        Only changes are written down, so a quiet day leaves a line or two and
        the day it goes leaves the moment it went."""
        if self._tucked:                         # away on purpose: nothing to put back
            self._misses = self._noroom = 0
            AppHelper.callLater(_CHECK_EVERY, self._watch)
            return
        try:
            state = self._state()
            on_bar, x = state[0], state[1]
            if state != self._last_state:
                self._log("on bar=%s  x=%s  visible=%s  policy=%s" % state)
                self._last_state = state

            if on_bar and x > 0:                 # placed, drawn, nothing to do
                self._misses = self._noroom = 0
            elif not on_bar:                     # the bar let the item go
                self._misses += 1
                if self._misses >= 2:
                    self._try_again("it is not on the bar")
            else:                                # on the bar, never given a slot
                self._noroom += 1
                if self._noroom >= 2:
                    self._try_again("it has no slot (x=0)")
        except Exception as e:
            self._log(f"the check itself failed: {e}")
        AppHelper.callLater(_CHECK_EVERY, self._watch)

    def _try_again(self, why):
        """Ask the bar for the item's place again, up to a point.

        WORTH ASKING AGAIN, because the usual reason for having no slot is that
        the slot was taken at the moment MedSearch started — by the copy of
        MedSearch it was replacing, most often — and macOS does not come back to
        an item it once refused. The slot is free seconds later and a new item
        takes it, so this is the difference between an icon that is missing for
        the life of the app and one that is missing for six seconds.

        UP TO A POINT, because if the menu bar is genuinely full no number of
        attempts will conjure room, and an app that keeps asking forever is
        worse than one that says so once."""
        self._misses = self._noroom = 0
        if self.rebuilds >= _REBUILD_LIMIT:
            if self.rebuilds == _REBUILD_LIMIT:
                self.rebuilds += 1               # say this once, then stop
                self._log(f"{why}, and {_REBUILD_LIMIT} attempts have not helped — "
                          "leaving it be. A menu bar with no room left does this; "
                          "closing one other menu bar app is what frees a slot.")
            return
        self.rebuilds += 1
        self._log(f"{why} — asking for a place again (#{self.rebuilds})")
        self._reseat(force=True)
        self._last_state = self._state()
        self._log("   -> on bar=%s  x=%s  visible=%s  policy=%s" % self._last_state)

    # ── off the bar while MedSearch is the app in front ─────────────────────
    def _in_front(self):
        """MedSearch is the active app AND its window is there to be used. Active
        alone is not enough: the quick-search box makes MedSearch active with the
        window still hidden, and that is exactly when the icon is the only way in."""
        try:
            w = self._ns_window()
            return bool(NSApp.isActive() and w is not None
                        and w.isVisible() and not w.isMiniaturized())
        except Exception:
            return False

    def _sync_item(self):
        """The icon leaves the bar while MedSearch is in front, and returns when it
        is not (his choice, 21 Sep: in front, not merely open — with the window open
        behind another app the icon is there).

        `setVisible_`, not remove-and-rebuild: the same item, its menu and its
        autosave name stay, so it comes back where he left it. It still gives the
        slot up, and coming back is a fresh request that a full bar can refuse —
        that case is not handled here; `_watch` picks it up as it does at launch
        (x=0, asks again). While it is away on purpose the watcher and `_reseat`
        stand down, or they would "rescue" it every three seconds."""
        want = self._in_front()
        if want == self._tucked or self.item is None:
            return
        self._tucked = want
        self._misses = self._noroom = 0
        try:
            self.item.setVisible_(not want)
        except Exception as e:
            self._tucked = False
            self._log(f"could not {'hide' if want else 'show'} the item: {e}")

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
        AppHelper.callAfter(self._sync_item)
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
        self._sync_item()

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
        which case this is.

        Any other close is refused here and decided by `_close_dialog_or_hide`: the
        page has to be asked, and evaluate_js needs this (main) thread to be free."""
        if any(f.function == "applicationShouldTerminate_" for f in inspect.stack()):
            return True
        threading.Thread(target=self._close_dialog_or_hide, daemon=True).start()
        return False

    def _close_dialog_or_hide(self):
        """Close the page's top dialog if one is open, otherwise hide the window.

        THE PDF VIEWER IS NOT A WINDOW (seen 24 Sep). It is a panel inside the
        MedSearch window, so its natural close, the window's red button or ⌘W, hid
        the whole app in the menu bar. With a dialog or the viewer open, closing now
        closes only that, as Escape does (`closeTopDialog` in app.js).

        The page is asked rather than tracked from here: only the page knows what is
        open. An answer that is not a plain yes (no answer within
        `_PAGE_ANSWER_WAIT`, a blank or reloading page, an error) counts as nothing
        open, so the window can always be closed."""
        answer = []

        def ask():
            try:
                answer.append(self.window.evaluate_js(
                    "typeof closeTopDialog === 'function' && closeTopDialog() === true"))
            except Exception:
                pass

        t = threading.Thread(target=ask, daemon=True)
        t.start()
        t.join(_PAGE_ANSWER_WAIT)
        if not (answer and answer[0] is True):
            AppHelper.callAfter(self.hide)


def _fourcc(code):
    return int.from_bytes(code.encode("ascii"), "big")


def _answer_reopen(target):
    """Opening MedSearch while it is already running brings the window back.

    A SECOND LAUNCH NEVER REACHES launcher.sh (seen 21 Sep). The running process
    lives inside MedSearch.app, so LaunchServices knows it as that app — lsappinfo
    lists it under the launcher's bundle id — and opening the app again from
    Spotlight, Launchpad or Finder does not start anything: macOS sends the running
    copy a "reopen" Apple event and considers the job done. The /focus handoff in
    app.py is only reached by a start that bypasses LaunchServices (a terminal).
    Nothing answered the event, because pywebview's app delegate has no
    applicationShouldHandleReopen, so with the window hidden in the menu bar
    nothing happened at all.

    The event is answered directly rather than by adding a method to pywebview's
    delegate class, which is theirs to change. Installed after launch, so it
    replaces the handler AppKit registered for the same event; `show` does what
    that one did (un-minimise, bring forward) and also undoes a hide."""
    from Foundation import NSAppleEventManager
    NSAppleEventManager.sharedAppleEventManager() \
        .setEventHandler_andSelector_forEventClass_andEventID_(
            target, b"reopen:withReplyEvent:", _fourcc("aevt"), _fourcc("rapp"))


def _hear_front_changes(host):
    """Tell `_sync_item` whenever the answer to "is MedSearch in front?" can change."""
    from Foundation import NSNotificationCenter
    center = NSNotificationCenter.defaultCenter()
    for name in ("NSApplicationDidBecomeActiveNotification",
                 "NSApplicationDidResignActiveNotification"):
        center.addObserver_selector_name_object_(host.target, b"frontChanged:", name, None)
    window = host._ns_window()
    for name in ("NSWindowDidMiniaturizeNotification",
                 "NSWindowDidDeminiaturizeNotification"):
        center.addObserver_selector_name_object_(host.target, b"frontChanged:", name, window)


def install(window, *, background=False, **kwargs):
    """Create the menu bar item. Call on the main thread, once the window exists.
    `background` starts with the window hidden (MedSearch opened at login)."""
    global _host
    _host = StatusBar(window, **kwargs)
    window.events.closing += _host.closing
    try:
        _answer_reopen(_host.target)
    except Exception as e:                       # the item still works without it
        _host._log(f"reopen handler not installed: {e}")
    try:
        _hear_front_changes(_host)
    except Exception as e:                       # then the icon simply stays
        _host._log(f"front/back notifications not installed: {e}")
    if background:
        _host.hide()
    _host._sync_item()          # it may already be in front: that notification has gone
    return _host

"""The menu bar item, and the thing it kept doing: leaving the bar.

None of this creates a real status item — that would need the window server and
would put an icon on the bar of whoever is running the tests. What is tested is
the part that has to be right: recognising that the item has gone, and what is
done about it.
"""
import pytest

pytest.importorskip("AppKit", reason="the menu bar item is macOS only")
import statusbar as SB  # noqa: E402


class _Frame:
    def __init__(self, x): self.origin = type("o", (), {"x": x})()


class _Window:
    def __init__(self, visible=True, x=1113.0):
        self.visible, self._frame = visible, _Frame(x)
    def isVisible(self): return self.visible
    def frame(self): return self._frame


class _Button:
    def __init__(self, window): self._window = window
    def window(self): return self._window


class _Item:
    """An NSStatusItem, including the two ways it lies: an item that has left the
    bar still has its button and still calls itself visible, and an item macOS
    never found room for reports exactly the same — except for x."""
    def __init__(self, on_bar=True, x=1113.0): self.button_ = _Button(_Window(on_bar, x))
    def button(self): return self.button_
    def isVisible(self): return True
    def setVisible_(self, on): self.button_._window.visible = bool(on)   # what AppKit does
    def leave_the_bar(self): self.button_._window.visible = False
    def find_no_room(self): self.button_._window._frame.origin.x = 0


class _Host:
    """A StatusBar with the AppKit parts replaced, driven by the real methods."""
    def __init__(self, on_bar=True, x=1113.0):
        self.item, self.log_path = _Item(on_bar, x), None
        self._last_state, self._misses, self._noroom, self.rebuilds = None, 0, 0, 0
        self.lines, self.made = [], 0
        self._tucked, self.front = False, False

    # the real ones under test
    on_the_bar = SB.StatusBar.on_the_bar
    _state = SB.StatusBar._state
    _x = SB.StatusBar._x
    _watch = SB.StatusBar._watch
    _try_again = SB.StatusBar._try_again
    _sync_item = SB.StatusBar._sync_item
    def _in_front(self): return self.front

    def _log(self, line): self.lines.append(line)
    def _make_item(self): self.made += 1; self.item = _Item(True)   # a new item gets a slot
    def _reseat(self, force=False):
        if force or not self.on_the_bar():
            self._make_item()


@pytest.fixture(autouse=True)
def no_scheduling(monkeypatch):
    """_watch schedules itself; the test calls it by hand instead."""
    monkeypatch.setattr(SB.AppHelper, "callLater", lambda *a, **k: None)
    monkeypatch.setattr(SB.AppHelper, "callAfter", lambda *a, **k: None)


def test_an_item_that_has_left_the_bar_is_recognised():
    """The whole bug in one assertion: every obvious signal says the item is
    fine — it has a button, the button has a window, isVisible is true. Only
    the window it draws in stops being visible."""
    host = _Host()
    assert host.on_the_bar() is True
    host.item.leave_the_bar()
    assert host.item.button() is not None      # still answers
    assert host.item.isVisible() is True       # still claims to be visible
    assert host.on_the_bar() is False          # and is still gone


def test_the_item_is_put_back_after_it_goes():
    host = _Host()
    host._watch()                              # healthy
    assert host.made == 0
    host.item.leave_the_bar()
    host._watch()                              # first miss: noticed, not acted on
    assert host.made == 0
    host._watch()                              # second: put back
    assert host.made == 1 and host.on_the_bar() is True


def test_one_bad_check_alone_does_not_rebuild_it():
    """A rebuilt item can land somewhere else on the bar, so a single miss —
    a display waking, a space switching — is not enough."""
    host = _Host()
    host.item.leave_the_bar()
    host._watch()
    host.item.button_._window.visible = True   # it was only passing
    host._watch()
    assert host.made == 0


def test_it_stops_asking_rather_than_fight_a_full_bar():
    """If the menu bar genuinely has no room, no number of attempts conjures a
    slot, and an app that keeps asking forever is worse than one that says so."""
    host = _Host()
    host.rebuilds = SB._REBUILD_LIMIT
    host.item.leave_the_bar()
    host._watch(); host._watch()
    assert host.made == 0
    assert any("leaving it be" in line for line in host.lines)


def test_what_it_writes_down_is_only_what_changed():
    host = _Host()
    host._watch(); host._watch(); host._watch()
    assert len(host.lines) == 1                # one line while nothing changes
    host.item.leave_the_bar()
    host._watch()
    assert len(host.lines) == 2 and "on bar=False" in host.lines[1]


def test_an_item_refused_a_slot_asks_again_and_gets_one():
    """THE REAL CASE, 20 Sep. Quitting and relaunching starts the new copy while
    the old one still holds the only free slot, so the new item is refused and
    left at x=0 — for the life of the app, because macOS never returns to an
    item it once refused. Seconds later the old copy is gone and the slot is
    free, so asking again is the whole fix."""
    host = _Host(x=0)                                   # started with no slot
    assert host.on_the_bar() is True                    # and AppKit says it is fine
    host._watch()                                       # first reading: too early to judge
    assert host.made == 0
    host._watch()                                       # second: ask for a place again
    assert host.made == 1
    assert host._x() > 0                                # and this time it has one
    assert any("no slot (x=0)" in line for line in host.lines)


def test_the_first_reading_of_all_is_never_believed():
    """A brand new item reads x=0 until AppKit lays it out. Acting on that would
    have every launch rebuilding an item that was about to be placed anyway."""
    host = _Host(x=0)
    host._watch()
    assert host.made == 0
    host.item.button_._window._frame.origin.x = 1113    # laid out, as it would be
    host._watch()
    assert host.made == 0


# ── opening the app again while it runs ─────────────────────────────────────

def test_a_reopen_event_shows_the_window():
    shown = []
    target = SB._Target.alloc().initWithHost_(type("Host", (), {"show": lambda self: shown.append(1)})())
    target.reopen_withReplyEvent_(None, None)
    assert shown == [1]


def test_the_handler_is_registered_for_the_reopen_event(monkeypatch):
    import Foundation
    calls = []

    class _Manager:
        @classmethod
        def sharedAppleEventManager(cls): return cls()
        def setEventHandler_andSelector_forEventClass_andEventID_(self, target, sel, cls, eid):
            calls.append((target, sel, cls, eid))

    # The name, not the class: an Objective-C class method cannot be patched.
    monkeypatch.setattr(Foundation, "NSAppleEventManager", _Manager)
    target = SB._Target.alloc().initWithHost_(object())
    SB._answer_reopen(target)
    # kCoreEventClass 'aevt' and kAEReopenApplication 'rapp', as four-char codes.
    assert calls == [(target, b"reopen:withReplyEvent:", 0x61657674, 0x72617070)]
    assert target.respondsToSelector_(b"reopen:withReplyEvent:")


# ── off the bar while MedSearch is the app in front ─────────────────────────

def test_the_icon_leaves_when_medsearch_is_in_front_and_returns_after():
    host = _Host()
    host.front = True;  host._sync_item()
    assert host._tucked and host.on_the_bar() is False
    host.front = False; host._sync_item()
    assert not host._tucked and host.on_the_bar() is True
    assert host.made == 0                      # the same item throughout, never rebuilt


def test_an_icon_away_on_purpose_is_not_rescued():
    """Off the bar is exactly what the watcher exists to undo. Without standing
    down it would rebuild the item three seconds after every switch to MedSearch."""
    host = _Host()
    host.front = True; host._sync_item()
    for _ in range(5):
        host._watch()
    assert host.made == 0 and host.lines == []


def test_a_refused_return_is_still_noticed():
    """Coming back is a fresh request for a slot. If macOS refuses it (x=0) the
    watcher must pick that up as it does at launch."""
    host = _Host()
    host.front = True;  host._sync_item()
    host.front = False; host._sync_item()
    host.item.find_no_room()
    host._watch(); host._watch()
    assert host.made == 1


# ── closing the window with the PDF viewer or a dialog open ─────────────────

class _Page:
    """The pywebview window: evaluate_js answers as the page would."""
    def __init__(self, answer=None, raises=False, delay=0.0):
        self.answer, self.raises, self.delay, self.asked = answer, raises, delay, []
    def evaluate_js(self, js):
        import time
        self.asked.append(js)
        if self.delay:
            time.sleep(self.delay)
        if self.raises:
            raise RuntimeError("the page is gone")
        return self.answer


class _Closer:
    """A StatusBar with only the closing path real."""
    closing = SB.StatusBar.closing
    _close_dialog_or_hide = SB.StatusBar._close_dialog_or_hide
    def __init__(self, page): self.window, self.hidden = page, 0
    def hide(self): self.hidden += 1


@pytest.fixture
def run_now(monkeypatch):
    """Hiding is scheduled on the main thread; here it runs at once."""
    monkeypatch.setattr(SB.AppHelper, "callAfter", lambda f, *a, **k: f(*a, **k))


def test_closing_with_a_dialog_open_closes_the_dialog_and_keeps_the_window(run_now):
    """The fault of 24 Sep: the PDF viewer is a panel inside the window, and its
    natural close (red button, ⌘W) hid the whole app in the menu bar."""
    host = _Closer(_Page(answer=True))
    host._close_dialog_or_hide()
    assert host.hidden == 0
    assert "closeTopDialog()" in host.window.asked[0]


def test_closing_with_nothing_open_still_hides_the_window(run_now):
    host = _Closer(_Page(answer=False))
    host._close_dialog_or_hide()
    assert host.hidden == 1


@pytest.mark.parametrize("page", [
    _Page(answer=None),                         # no closeTopDialog, or a blank page
    _Page(answer="true"),                       # anything but a plain yes
    _Page(raises=True),                         # the page process is gone
    _Page(answer=True, delay=SB._PAGE_ANSWER_WAIT + 0.5),   # no answer in time
])
def test_a_page_that_does_not_say_yes_never_keeps_the_window_open(run_now, page):
    host = _Closer(page)
    host._close_dialog_or_hide()
    assert host.hidden == 1


def test_closing_refuses_the_close_and_asks_the_page_off_the_main_thread(run_now, monkeypatch):
    """evaluate_js waits for the main thread, which is inside this handler: asking
    from here would hang the app. The handler hands the question to a thread."""
    started = []

    class _Thread:
        def __init__(self, target, daemon=None): self.target = target
        def start(self): started.append(self.target)

    monkeypatch.setattr(SB.threading, "Thread", _Thread)
    host = _Closer(_Page(answer=True))
    assert host.closing() is False
    assert host.window.asked == []                    # not asked on this thread
    assert [t.__name__ for t in started] == ["_close_dialog_or_hide"]
    assert host.hidden == 0


def test_a_real_quit_is_never_held_up_by_the_page(run_now):
    """⌘Q, logging out and shutting down ask every window through
    applicationShouldTerminate_; that answer must stay an immediate yes."""
    host = _Closer(_Page(answer=True))

    def applicationShouldTerminate_():
        return host.closing()

    assert applicationShouldTerminate_() is True
    assert host.window.asked == [] and host.hidden == 0

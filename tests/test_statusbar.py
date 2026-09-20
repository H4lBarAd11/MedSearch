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
    def leave_the_bar(self): self.button_._window.visible = False
    def find_no_room(self): self.button_._window._frame.origin.x = 0


class _Host:
    """A StatusBar with the AppKit parts replaced, driven by the real methods."""
    def __init__(self, on_bar=True, x=1113.0):
        self.item, self.log_path = _Item(on_bar, x), None
        self._last_state, self._misses, self._noroom, self.rebuilds = None, 0, 0, 0
        self.lines, self.made = [], 0

    # the real ones under test
    on_the_bar = SB.StatusBar.on_the_bar
    _state = SB.StatusBar._state
    _x = SB.StatusBar._x
    _watch = SB.StatusBar._watch
    _try_again = SB.StatusBar._try_again

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

"""The menu bar item, and the thing it kept doing: leaving the bar.

None of this creates a real status item — that would need the window server and
would put an icon on the bar of whoever is running the tests. What is tested is
the part that has to be right: recognising that the item has gone, and what is
done about it.
"""
import pytest

pytest.importorskip("AppKit", reason="the menu bar item is macOS only")
import statusbar as SB  # noqa: E402


class _Window:
    def __init__(self, visible=True): self.visible = visible
    def isVisible(self): return self.visible


class _Button:
    def __init__(self, window): self._window = window
    def window(self): return self._window


class _Item:
    """An NSStatusItem, including the way it lies: an item that has left the bar
    still has its button, and still calls itself visible."""
    def __init__(self, on_bar=True): self.button_ = _Button(_Window(on_bar))
    def button(self): return self.button_
    def isVisible(self): return True
    def leave_the_bar(self): self.button_._window.visible = False


class _Host:
    """A StatusBar with the AppKit parts replaced, driven by the real methods."""
    def __init__(self, on_bar=True):
        self.item, self.log_path = _Item(on_bar), None
        self._last_state, self._misses, self.rebuilds = None, 0, 0
        self.lines, self.made = [], 0

    # the real ones under test
    on_the_bar = SB.StatusBar.on_the_bar
    _state = SB.StatusBar._state
    _watch = SB.StatusBar._watch

    def _log(self, line): self.lines.append(line)
    def _make_item(self): self.made += 1; self.item = _Item(True)
    def _reseat(self):
        if not self.on_the_bar():
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


def test_it_stops_rebuilding_rather_than_fight_the_system():
    """If something else is taking the item off — a full menu bar is the usual
    reason — rebuilding every three seconds does not win."""
    host = _Host()
    host.rebuilds = SB._REBUILD_LIMIT
    host.item.leave_the_bar()
    host._watch(); host._watch()
    assert host.made == 0
    assert any("leaving it alone" in line for line in host.lines)


def test_what_it_writes_down_is_only_what_changed():
    host = _Host()
    host._watch(); host._watch(); host._watch()
    assert len(host.lines) == 1                # one line while nothing changes
    host.item.leave_the_bar()
    host._watch()
    assert len(host.lines) == 2 and "on bar=False" in host.lines[1]

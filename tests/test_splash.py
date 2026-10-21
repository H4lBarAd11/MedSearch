"""The splash: what it draws, its clock, and that MedSearch opens whatever the
splash does. No window is opened here; the hand-over runs against a stand-in
for the main window, with the main-thread calls made inline.
"""
import inspect
import math
import re
from pathlib import Path

import pytest

import splash as S

ROOT = Path(__file__).resolve().parent.parent


def _tokens(theme):
    css = (ROOT / "static" / "css" / "app.css").read_text(encoding="utf-8")
    light, dark = css.split(":root[data-theme=\"dark\"] {", 1)
    part = light if theme == "light" else dark
    return {m.group(1): tuple(int(m.group(2)[i:i + 2], 16) for i in (0, 2, 4))
            for m in re.finditer(r"--([a-z0-9-]+):\s*#([0-9A-Fa-f]{6})", part)}


# ── what it draws ────────────────────────────────────────────────────────────

def test_the_colours_are_the_interfaces_own():
    light, dark = _tokens("light"), _tokens("dark")
    assert S.SAGE == light["accent"]
    assert S.CARAMEL == light["yellow"]
    assert S.GROUND == {"light": light["bg"], "dark": dark["bg"]}


def test_the_drawing_is_the_icons_drawing():
    icon = (ROOT / "render_icon.py").read_text(encoding="utf-8")
    assert "line_w, thin_w = int(30 * u), int(22 * u)" in icon
    assert (S.BOOK_W, S.TEXT_W) == (30, 22)
    assert "cx, cy, r = 648 * u, 520 * u, 96 * u" in icon and S.RING == (648, 520, 96)
    assert "handle_w = int(44 * u)" in icon and S.HANDLE_W == 44
    assert "(802 * u, 674 * u)" in icon and S.HANDLE_END == (802, 674)
    assert "for i, length in enumerate((120, 120, 84))" in icon
    assert "y = (404 + i * 70) * u" in icon
    lines = [p[0][2] for p in S.PHASES[2:5]]
    assert [(steps[0][2], steps[1][1] - steps[0][1]) for steps in lines] == \
        [(404, 120), (474, 120), (544, 84)]


def test_the_pen_goes_spine_pages_lines_ring_handle():
    kinds = [[(w, c) for w, c, _ in phase] for phase in S.PHASES]
    assert kinds == [[(30, S.SAGE)], [(30, S.SAGE)] * 2, [(22, S.SAGE)], [(22, S.SAGE)],
                     [(22, S.SAGE)], [(34, S.CARAMEL)], [(44, S.CARAMEL)]]


def test_the_ring_ends_where_the_handle_begins():
    ring, handle = S.PHASES[5][0][2], S.PHASES[6][0][2]
    assert math.dist(ring[-1][1:], handle[0][1:]) < 1e-6
    assert math.dist(ring[0][1:], ring[-1][1:]) < 1e-6          # a whole circle


def test_both_pages_leave_from_the_top_of_the_spine_and_come_back_to_its_foot():
    spine = S.PHASES[0][0][2]
    for _, _, page in S.PHASES[1]:
        assert page[0][1:] == spine[0][1:]
        assert page[-1][-2:] == spine[-1][1:]


def test_the_drawing_is_as_wide_as_bidss_word():
    left, top, right, bottom = S.bounds()
    assert S.WIDTH_PT == 480
    assert right - left > bottom - top > 0


# ── the clock ────────────────────────────────────────────────────────────────

def test_the_phases_share_the_pen_end_to_end():
    spans = S.spans()
    assert len(spans) == len(S.PHASES)
    assert spans[0][0] == 0 and spans[-1][1] == 1
    for (a, b), (c, _) in zip(spans, spans[1:]):
        assert a < b == c


def test_one_even_pen_a_phase_lasts_as_its_longest_stroke():
    spans = S.spans()
    speed = [(b - a) / max(S.path_length(p) for _, _, p in phase)
             for (a, b), phase in zip(spans, S.PHASES)]
    assert max(speed) == pytest.approx(min(speed))


def test_the_pen_starts_late_ends_on_time_and_never_goes_back():
    assert S.pen(0) == 0 and S.pen(S.BLOOM_START) == 0
    assert S.pen(S.BLOOM_START + S.BLOOM_TIME) == pytest.approx(1)
    assert S.pen(100) == 1
    samples = [S.pen(t / 100) for t in range(400)]
    assert samples == sorted(samples)


@pytest.mark.parametrize("progress,drawn", [(0.0, 0), (0.2, 0), (0.25, 0), (0.3, 0.5),
                                            (0.35, 1), (0.9, 1)])
def test_a_stroke_is_drawn_only_inside_its_phase(progress, drawn):
    assert S.stroke_at(progress, (0.25, 0.35)) == pytest.approx(drawn)


def test_the_window_opens_only_once_the_drawing_is_done_and_served_its_time():
    assert S.leave_at() >= S.BLOOM_START + S.BLOOM_TIME
    assert S.leave_at() + S.SPLASH_OUT == pytest.approx(S.SPLASH_MIN)


def test_the_disc_ends_as_the_whole_window():
    x, y, r = S.disc((100, 50, 1280, 888), 740, 494)
    assert (x, y) == (640, 444)
    assert r >= math.hypot(640, 444)
    # A drawing outside the window's frame: the disc still starts on the window.
    x, y, r = S.disc((100, 50, 1280, 888), 0, 2000)
    assert (x, y) == (0, 888)
    assert r >= math.hypot(1280, 888)


# ── the hand-over ────────────────────────────────────────────────────────────

class _NS:
    def __init__(self):
        self.alpha, self.visible, self.calls = 1.0, False, []

    def setAlphaValue_(self, a):
        self.alpha = a

    def makeKeyAndOrderFront_(self, _):
        self.visible = True

    def isVisible(self):
        return self.visible

    def frame(self):
        return _Rect(100, 50, 1280, 888)

    def contentRectForFrameRect_(self, f):
        return _Rect(f.origin.x, f.origin.y, f.size.width, f.size.height - 28)


class _Rect:
    def __init__(self, x, y, w, h):
        self.origin = type("P", (), {"x": x, "y": y})()
        self.size = type("S", (), {"width": w, "height": h})()


class _Main:
    def __init__(self):
        self.native, self.shown = _NS(), 0

    def show(self):
        self.shown += 1
        self.native.visible = True


class _Panel:
    """The splash's own window as `open` leaves it: ordered in, unseen. On the
    Space in front or not, as `here` says look after look (its last answer
    repeats); what is done to it is written down in `log`."""
    def __init__(self, here=(True,)):
        self.here, self.alpha, self.log = list(here), 0.0, []

    def isOnActiveSpace(self):
        self.log.append("asked")
        return self.here.pop(0) if len(self.here) > 1 else self.here[0]

    def setAlphaValue_(self, a):
        self.alpha = a
        self.log.append(f"alpha {a:g}")

    def orderOut_(self, _):
        self.log.append("out")

    def close(self):
        self.log.append("closed")


@pytest.fixture
def inline(monkeypatch):
    """Main-thread calls made on the spot, and no real waiting."""
    slept = []
    monkeypatch.setattr(S, "_on_main_wait", lambda fn, timeout=2.0: fn())

    def on_main(fn, otherwise=None):
        try:
            fn()
        except Exception:
            if otherwise:
                otherwise()
    monkeypatch.setattr(S, "_on_main", on_main)
    monkeypatch.setattr(S.time, "sleep", slept.append)
    monkeypatch.setattr(S.Splash, "_start_pen", lambda self: self._window.log.append("pen"))
    monkeypatch.setattr(S.Splash, "_place_unseen",
                        lambda self, main: (main.native.setAlphaValue_(0.0),
                                            main.native.makeKeyAndOrderFront_(None)))
    monkeypatch.setattr(S.Splash, "_finish", lambda self, main: S._show_plainly(main))
    return slept


class _Clock:
    """splash.py's `time`: sleeping moves it on, and nothing really waits."""
    def __init__(self):
        self.now, self.slept = 1000.0, []

    def monotonic(self):
        return self.now

    def sleep(self, s):
        self.slept.append(s)
        self.now += s


@pytest.fixture
def clock(inline, monkeypatch):
    c = _Clock()
    monkeypatch.setattr(S, "time", c)
    return c


def _opened(monkeypatch, opened_out, here=(True,)):
    sp = S.Splash()
    sp._window, sp._screen = _Panel(here), _Rect(0, 0, 1728, 1117)
    monkeypatch.setattr(S.Splash, "_open_out", lambda self, rect: opened_out.append(rect))
    return sp


def test_the_window_opens_out_of_the_splash_and_is_left_opaque(inline, monkeypatch):
    opened = []
    sp, main = _opened(monkeypatch, opened), _Main()
    sp.ready.set()
    sp.hand_over(main)
    assert opened == [(100, 50, 1280, 888, 28)]
    assert main.native.alpha == 1.0 and main.native.visible


def test_it_waits_out_the_drawing_before_opening(inline, monkeypatch):
    opened = []
    sp, main = _opened(monkeypatch, opened), _Main()
    sp.ready.set()
    sp.hand_over(main)
    waited = [s for s in inline if s not in (S.PLACED_S, S.SETTLE_PLACE_S, S.SPLASH_OUT)]
    assert waited and waited[0] == pytest.approx(S.leave_at(), abs=0.1)


def test_the_window_waits_for_the_page(inline, monkeypatch):
    import threading
    import time as real_time
    events = []
    sp, main = _opened(monkeypatch, []), _Main()
    monkeypatch.setattr(S.Splash, "_open_out", lambda self, rect: events.append("opened"))
    monkeypatch.setattr(S.Splash, "_place_unseen", lambda self, m: events.append("placed"))

    def page_answers():
        events.append("ready")
        sp.ready.set()
    threading.Timer(0.2, page_answers).start()
    t0 = real_time.monotonic()
    sp.hand_over(main)
    assert events == ["ready", "placed", "opened"]
    assert real_time.monotonic() - t0 >= 0.19


def test_a_splash_that_never_opened_still_shows_the_window(inline):
    sp, main = S.Splash(), _Main()
    sp.ready.set()
    sp.hand_over(main)
    assert main.native.alpha == 1.0 and main.native.visible and main.shown == 1


def test_a_page_that_never_says_ready_does_not_keep_medsearch_shut(inline, monkeypatch):
    monkeypatch.setattr(S, "READY_TIMEOUT_S", 0.01)
    opened = []
    sp, main = _opened(monkeypatch, opened), _Main()
    sp.hand_over(main)
    assert opened and main.native.alpha == 1.0 and main.native.visible


def test_a_failure_while_opening_out_still_shows_the_window(inline, monkeypatch):
    sp, main = _opened(monkeypatch, []), _Main()

    def broken(self, rect):
        raise RuntimeError("the window server said no")
    monkeypatch.setattr(S.Splash, "_open_out", broken)
    sp.ready.set()
    with pytest.raises(RuntimeError):
        sp.hand_over(main)
    assert main.native.alpha == 1.0 and main.native.visible


def test_showing_plainly_survives_a_window_without_its_native_half():
    class Bare:
        shown = 0

        def show(self):
            self.shown += 1
    bare = Bare()
    S._show_plainly(bare)
    assert bare.shown == 1


# ── where it plays ───────────────────────────────────────────────────────────

def test_the_splash_stays_on_one_space():
    """On every Space, or on whichever is in front, the drawing is shown over an
    app in full screen, while the window opens on a desktop out of sight."""
    every, to_front, managed, transient, stationary, cycle, auxiliary = (
        1 << 0, 1 << 1, 1 << 2, 1 << 3, 1 << 4, 1 << 6, 1 << 8)
    assert S.ONE_SPACE & managed and S.ONE_SPACE & cycle
    assert not S.ONE_SPACE & (every | to_front | transient | stationary | auxiliary)
    assert "setCollectionBehavior_(ONE_SPACE)" in inspect.getsource(S.Splash.open)


def test_the_splash_comes_forward_unseen_and_its_pen_waits():
    src = inspect.getsource(S.Splash.open)
    assert src.index("setAlphaValue_(0.0)") < src.index("orderFrontRegardless()") \
        < src.index("activateIgnoringOtherApps_(True)")
    assert "_start_pen" not in src and "_t0" not in src


def test_on_the_space_in_front_the_pen_sets_out_once_the_window_is_placed(clock, monkeypatch):
    opened = []
    sp, main = _opened(monkeypatch, opened), _Main()
    sp.ready.set()
    sp.hand_over(main)
    assert clock.slept[:2] == [S.PLACED_S, S.SETTLE_PLACE_S]
    assert sp._window.log == ["asked", "pen", "alpha 1"]
    assert sp._t0 == pytest.approx(1000 + S.PLACED_S)
    assert opened and main.native.alpha == 1.0 and main.native.visible


def test_from_an_app_in_full_screen_the_pen_waits_for_the_user_to_arrive(clock, monkeypatch):
    """Placed on a desktop, the splash stays unseen until the switch there is
    done, and only then does its clock start."""
    opened = []
    sp, main = _opened(monkeypatch, opened, here=[False] * 8 + [True]), _Main()
    sp.ready.set()
    sp.hand_over(main)
    assert sp._window.log == ["asked"] * 9 + ["pen", "alpha 1"]
    assert clock.slept[:10] == [S.PLACED_S] + [S.ARRIVAL_POLL_S] * 8 + [S.SLIDE_S]
    assert sp._t0 == pytest.approx(1000 + S.PLACED_S + 8 * S.ARRIVAL_POLL_S + S.SLIDE_S)
    assert opened and main.native.alpha == 1.0 and main.native.visible


def test_the_waits_count_from_the_run_loop(clock, monkeypatch):
    """The drawing goes up before the run loop turns, and macOS places it only
    once MedSearch has finished launching: the first wait is for the main
    thread, as long as the page is given, and the clock starts after it."""
    events = []

    def on_main_wait(fn, timeout=2.0):
        events.append(("main", timeout))
        return fn()
    monkeypatch.setattr(S, "_on_main_wait", on_main_wait)
    monkeypatch.setattr(clock, "sleep", lambda s: (events.append(("sleep", s)), _Clock.sleep(clock, s)))
    sp, main = _opened(monkeypatch, []), _Main()
    sp.ready.set()
    sp.hand_over(main)
    assert events[:2] == [("main", S.READY_TIMEOUT_S), ("sleep", S.PLACED_S)]


def test_a_main_thread_that_never_answers_still_opens_the_window(clock, monkeypatch):
    monkeypatch.setattr(S, "_on_main_wait", lambda fn, timeout=2.0: None)
    opened = []
    sp, main = _opened(monkeypatch, opened), _Main()
    sp.ready.set()
    sp.hand_over(main)
    assert sp._t0 is None and S.PLACED_S not in clock.slept and not opened
    assert main.native.alpha == 1.0 and main.native.visible


def test_a_space_never_reached_opens_the_window_without_the_splash(clock, monkeypatch):
    opened = []
    sp, main = _opened(monkeypatch, opened, here=[False]), _Main()
    panel = sp._window
    sp.ready.set()
    sp.hand_over(main)
    assert panel.log[-2:] == ["out", "closed"] and sp._window is None
    assert "pen" not in panel.log and panel.alpha == 0.0
    looks = round(S.ARRIVAL_S / S.ARRIVAL_POLL_S)               # the whole wait, and no more
    assert looks <= clock.slept.count(S.ARRIVAL_POLL_S) <= looks + 1
    assert S.SLIDE_S not in clock.slept and not opened
    assert main.native.alpha == 1.0 and main.native.visible and main.shown == 1


def test_a_splash_that_could_not_be_shown_opens_nothing_out(clock, monkeypatch):
    """The main thread's calls fail quietly, as `_on_main_wait` makes them."""
    def quietly(fn, timeout=2.0):
        try:
            return fn()
        except Exception:
            return None
    monkeypatch.setattr(S, "_on_main_wait", quietly)

    def broken(self):
        raise RuntimeError("the window server said no")
    monkeypatch.setattr(S.Splash, "_start_pen", broken)
    opened = []
    sp, main = _opened(monkeypatch, opened), _Main()
    sp.ready.set()
    sp.hand_over(main)
    assert not opened and sp._window.alpha == 0.0
    assert main.native.alpha == 1.0 and main.native.visible


# ── the page's side ──────────────────────────────────────────────────────────

def test_the_page_tells_the_window_it_is_ready():
    js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "window.pywebview.api.page_ready()" in js
    assert "addEventListener('pywebviewready', tellWindowReady" in js
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "_SPLASH.ready.set()" in app
    assert "hidden=_args.background or _SPLASH is not None" in app

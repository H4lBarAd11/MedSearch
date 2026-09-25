"""The splash: what it draws, its clock, and that MedSearch opens whatever the
splash does. No window is opened here; the hand-over runs against a stand-in
for the main window, with the main-thread calls made inline.
"""
import math
import re
from pathlib import Path

import pytest

import splash as S

ROOT = Path(__file__).resolve().parent.parent


def _tokens(theme):
    css = (ROOT / "static" / "css" / "app.css").read_text()
    light, dark = css.split("@media (prefers-color-scheme: dark)", 1)
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
    icon = (ROOT / "render_icon.py").read_text()
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
    monkeypatch.setattr(S.Splash, "_place_unseen",
                        lambda self, main: (main.native.setAlphaValue_(0.0),
                                            main.native.makeKeyAndOrderFront_(None)))
    monkeypatch.setattr(S.Splash, "_finish", lambda self, main: S._show_plainly(main))
    return slept


def _opened(monkeypatch, opened_out):
    sp = S.Splash()
    sp._window, sp._screen, sp._t0 = object(), _Rect(0, 0, 1728, 1117), S.time.monotonic()
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
    waited = [s for s in inline if s not in (S.SETTLE_PLACE_S, S.SPLASH_OUT)]
    assert waited and waited[0] == pytest.approx(S.leave_at(), abs=0.1)


def test_the_window_waits_for_the_page(inline, monkeypatch):
    import threading
    import time as real_time
    events = []
    sp, main = S.Splash(), _Main()
    sp._window, sp._screen, sp._t0 = object(), _Rect(0, 0, 1728, 1117), S.time.monotonic()
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
    sp, main = S.Splash(), _Main()
    sp._window, sp._screen, sp._t0 = object(), _Rect(0, 0, 1728, 1117), S.time.monotonic()

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


# ── the page's side ──────────────────────────────────────────────────────────

def test_the_page_tells_the_window_it_is_ready():
    js = (ROOT / "static" / "js" / "app.js").read_text()
    assert "window.pywebview.api.page_ready()" in js
    assert "addEventListener('pywebviewready', tellWindowReady" in js
    app = (ROOT / "app.py").read_text()
    assert "_SPLASH.ready.set()" in app
    assert "hidden=_args.background or _SPLASH is not None" in app

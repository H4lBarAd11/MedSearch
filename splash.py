# MedSearch — the splash.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""The splash: the icon's open book and magnifier drawn in, alone in the middle
of the screen while MedSearch loads, and the hand-over to the main window.

WHAT IT DRAWS (his choice). The icon's drawing without its tile, traced by a pen:
the spine, both pages at once, the three lines of text, then the magnifier's
ring and its handle. The book is in the tile's sage, because the icon's ivory
would vanish on a light desktop; the magnifier keeps its caramel. A faint dark
halo under the lines holds them on any wallpaper. The drawing is written on its
own clock, as BIDS writes its word, and waits finished if MedSearch is not ready.

THE WINDOW GROWS OUT OF IT, AS IN BIDS. When the page is ready, a disc of the
window, title bar and all, grows from the middle of the drawing to the main
window's whole frame, swallowing the lines as they spread beneath it. Only then
is the real window made visible underneath, identical, while the splash fades
off. Resizing the real window instead would lay the page out on every frame.

DRAWN BY CORE ANIMATION, NOT IN A WEB PAGE. BIDS's splash is a page in a
transparent window. MedSearch's cannot be: about a second after its launcher
stub exits, macOS's loginwindow ends the web helper processes the app has
running at that moment (see `_reload_when_the_page_dies` in app.py), which is
exactly while a splash is on screen. Layers drawn by the app's own process and
the window server are not touched by that, so the splash is layers.

Nothing here decides when MedSearch is ready: the page says so (`ready`, set by
app.py's `page_ready`).
"""
from __future__ import annotations

import math
import platform
import threading
import time

# ── the drawing: the icon's own construction (render_icon.py) ────────────────
# In the icon's units: a 1024 canvas, y downwards. Each stroke is (width, colour,
# path), the path a list of ("M"|"L", x, y) and ("Q", cx, cy, x, y) steps.
BOOK_W, TEXT_W, RING_W, HANDLE_W = 30, 22, 34, 44
RING = (648, 520, 96)                         # the magnifier's centre and radius
HANDLE_END = (802, 674)

SAGE = (0x6E, 0x8B, 0x6E)                     # app.css --accent, the icon's tile
CARAMEL = (0x9A, 0x66, 0x36)                  # app.css --yellow, the magnifier
HALO = (27, 26, 23)                           # BIDS's halo: a faint charcoal …
HALO_ALPHA = 0.22                             # … at this strength
HALO_EXTRA = 20                               # wider than the line by this much

#: How wide the drawing is on screen, in points, lines included (BIDS's word: 480).
WIDTH_PT = 480


def _page(side):
    """One page as a single stroke: out along the top from the spine, down the
    outer edge, back along the bottom to the spine."""
    outer = 512 + side * 262
    return [("M", 512, 322), ("Q", 512 + side * 150, 286, outer, 306),
            ("L", outer, 700), ("Q", 512 + side * 150, 690, 512, 726)]


def _ring():
    """Round from where the handle joins it, so the pen goes on into the handle."""
    cx, cy, r = RING
    steps = 120
    start = math.pi / 4
    pts = [(cx + r * math.cos(start + 2 * math.pi * i / steps),
            cy + r * math.sin(start + 2 * math.pi * i / steps)) for i in range(steps + 1)]
    return [("M", *pts[0])] + [("L", x, y) for x, y in pts[1:]]


def _handle():
    cx, cy, r = RING
    a = math.pi / 4
    return [("M", cx + r * math.cos(a), cy + r * math.sin(a)), ("L", *HANDLE_END)]


def _line(y, length):
    return [("M", 330, y), ("L", 330 + length, y)]


#: The pen's order (his preview): spine ▸ pages ▸ text lines ▸ ring ▸ handle.
#: Each entry is one moment of the pen; strokes in the same entry are drawn together.
PHASES = [
    [(BOOK_W, SAGE, [("M", 512, 322), ("L", 512, 726)])],
    [(BOOK_W, SAGE, _page(-1)), (BOOK_W, SAGE, _page(1))],
    [(TEXT_W, SAGE, _line(404, 120))],
    [(TEXT_W, SAGE, _line(474, 120))],
    [(TEXT_W, SAGE, _line(544, 84))],
    [(RING_W, CARAMEL, _ring())],
    [(HANDLE_W, CARAMEL, _handle())],
]


def path_length(path) -> float:
    """A path's length, the curves measured finely enough for timing."""
    total, here = 0.0, (0.0, 0.0)
    for step in path:
        if step[0] == "M":
            here = step[1:]
        elif step[0] == "L":
            total += math.dist(here, step[1:])
            here = step[1:]
        else:
            (cx, cy, x, y), n, prev = step[1:], 64, here
            for i in range(1, n + 1):
                t = i / n
                p = ((1 - t) ** 2 * here[0] + 2 * (1 - t) * t * cx + t * t * x,
                     (1 - t) ** 2 * here[1] + 2 * (1 - t) * t * cy + t * t * y)
                total += math.dist(prev, p)
                prev = p
            here = (x, y)
    return total


def bounds():
    """(left, top, right, bottom) of the drawing, lines and halo included."""
    xs, ys = [], []
    for phase in PHASES:
        for width, _, path in phase:
            pad = (width + HALO_EXTRA) / 2
            for step in path:
                for x, y in zip(step[1::2], step[2::2]):
                    xs += [x - pad, x + pad]
                    ys += [y - pad, y + pad]
    return min(xs), min(ys), max(xs), max(ys)


def spans():
    """The share of the pen's travel each phase takes, as (start, end) in 0..1.
    One even pen: a phase lasts as long as its longest stroke."""
    lengths = [max(path_length(p) for _, _, p in phase) for phase in PHASES]
    total, out, at = sum(lengths), [], 0.0
    for n in lengths:
        out.append((at / total, (at + n) / total))
        at += n
    out[-1] = (out[-1][0], 1.0)
    return out


# ── the clock (BIDS's, unchanged) ────────────────────────────────────────────
BLOOM_START = 0.08            # s before the pen sets out
BLOOM_TIME = 3.2              # s: the drawing is finished at BLOOM_START + BLOOM_TIME
SPLASH_OUT = 0.55             # s: the window opening out of the drawing
SPLASH_MIN = 3.9              # s: the least the splash is on screen, opening included
SETTLE_S = 0.2                # s: the splash fading off the real window
SETTLE_PLACE_S = 0.15         # s given to the system to place the window before it is read
READY_TIMEOUT_S = 12.0        # a page that never says it is ready does not keep MedSearch shut
FADE_IN = 14                  # icon units: a line fades in over its first few, not a dot popping
SAMPLES = 96                  # keyframes of the pen


def pen(elapsed: float) -> float:
    """How far along its whole travel the pen is, `elapsed` s in: one even clock,
    eased in and out, and nothing else paces it."""
    t = min(max((elapsed - BLOOM_START) / BLOOM_TIME, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def stroke_at(progress: float, span) -> float:
    """How much of a stroke in the phase `span` is drawn at pen `progress`."""
    a, b = span
    return min(max((progress - a) / (b - a), 0.0), 1.0)


def leave_at() -> float:
    """The earliest moment, from the start, at which the window may open out:
    the drawing finished, and the least time on screen served."""
    return max(BLOOM_START + BLOOM_TIME, SPLASH_MIN - SPLASH_OUT)


def disc(rect, cx, cy):
    """The disc the window grows as: its centre is the drawing's, kept inside the
    window's rectangle (x, y, w, h), in that rectangle's own coordinates; its last
    radius reaches the farthest corner, so that it ends as the whole window."""
    x0, y0, w, h = rect
    x = min(max(cx, x0), x0 + w) - x0
    y = min(max(cy, y0), y0 + h) - y0
    far = max(math.hypot(x, y), math.hypot(w - x, y),
              math.hypot(x, h - y), math.hypot(w - x, h - y))
    return x, y, math.ceil(far) + 1


# ── the window's look, for the pane that becomes it ──────────────────────────
TITLE_BAR = {"light": (0xE8, 0xE7, 0xE4), "dark": (0x33, 0x35, 0x31)}   # measured for BIDS
GROUND = {"light": (0xF9, 0xF8, 0xEF), "dark": (0x1B, 0x1A, 0x17)}      # app.css --bg


def corner_radius() -> float:
    """A window's corners: rounder from macOS 26 on."""
    try:
        major = int(platform.mac_ver()[0].split(".")[0])
    except Exception:
        major = 0
    return 16.0 if major >= 26 else 10.0


class Splash:
    """The drawing's window, and the hand-over from it to the main window."""

    def __init__(self):
        self.ready = threading.Event()          # set by the page, through app.py
        self._window = None
        self._layers = {}
        self._t0 = None
        self._reduced = False

    # ── on screen ────────────────────────────────────────────────────────────
    def open(self) -> None:
        """Put the drawing up and start the pen. On the main thread."""
        from AppKit import (NSApplication, NSBackingStoreBuffered, NSColor, NSFloatingWindowLevel,
                            NSScreen, NSView, NSWindow, NSWorkspace)
        from Quartz import CALayer, CATransaction

        NSApplication.sharedApplication()
        screen = NSScreen.mainScreen() or NSScreen.screens()[0]
        frame = screen.frame()
        w = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, 0, NSBackingStoreBuffered, False)          # borderless
        w.setReleasedWhenClosed_(False)
        w.setOpaque_(False)
        w.setBackgroundColor_(NSColor.clearColor())
        w.setHasShadow_(False)
        # Over everything, and never in the way of a click: a splash that caught
        # the mouse would be an invisible pane over the desktop.
        w.setIgnoresMouseEvents_(True)
        w.setLevel_(NSFloatingWindowLevel)
        w.setCollectionBehavior_(1 | 16 | 64)   # every Space, stationary, not in ⌘`
        try:
            self._reduced = bool(NSWorkspace.sharedWorkspace()
                                 .accessibilityDisplayShouldReduceMotion())
        except Exception:
            self._reduced = False

        view = NSView.alloc().initWithFrame_(((0, 0), (frame.size.width, frame.size.height)))
        root = CALayer.layer()
        view.setLayer_(root)                    # layer-hosting: these layers are ours
        view.setWantsLayer_(True)
        w.setContentView_(view)
        scale = w.backingScaleFactor() or 2.0

        CATransaction.begin()
        CATransaction.setDisableActions_(True)
        stage = CALayer.layer()
        stage.setFrame_(root.bounds())
        root.addSublayer_(stage)
        art, strokes, size = self._drawing(scale)
        art.setPosition_((frame.size.width / 2, frame.size.height / 2))
        stage.addSublayer_(art)
        CATransaction.commit()

        self._window, self._screen = w, frame
        self._layers = {"root": root, "stage": stage, "art": art, "strokes": strokes,
                        "size": size}
        w.orderFrontRegardless()
        self._t0 = time.monotonic()
        self._start_pen()
        CATransaction.flush()

    def _drawing(self, scale):
        """The drawing as layers in the icon's units, scaled to WIDTH_PT: halos
        under all the lines, then the lines. Core Animation counts y upwards and
        the icon downwards, so each point is turned over as it is laid down."""
        from Quartz import (CALayer, CAShapeLayer, CATransform3DMakeScale, CGPathAddLineToPoint,
                            CGPathAddQuadCurveToPoint, CGPathCreateMutable, CGPathMoveToPoint)

        left, top, right, bottom = bounds()
        size = WIDTH_PT / (right - left)
        canvas = ((0, 0), (1024, 1024))
        art = CALayer.layer()
        art.setBounds_(canvas)
        # Held by the middle of the drawing: that point is put in the middle of the
        # screen, and the drawing spreads out from it.
        art.setAnchorPoint_(((left + right) / 2 / 1024, 1 - (top + bottom) / 2 / 1024))
        art.setTransform_(CATransform3DMakeScale(size, size, 1))

        halos = CALayer.layer()
        halos.setFrame_(canvas)
        halos.setOpacity_(HALO_ALPHA)
        # One faint shade where halos cross, not a darker spot.
        halos.setAllowsGroupOpacity_(True)
        art.addSublayer_(halos)
        lines = CALayer.layer()
        lines.setFrame_(canvas)
        art.addSublayer_(lines)

        strokes = []
        for i, phase in enumerate(PHASES):
            for width, colour, steps in phase:
                path = CGPathCreateMutable()
                for s in steps:
                    pts = [(x, 1024 - y) for x, y in zip(s[1::2], s[2::2])]
                    if s[0] == "M":
                        CGPathMoveToPoint(path, None, *pts[0])
                    elif s[0] == "L":
                        CGPathAddLineToPoint(path, None, *pts[0])
                    else:
                        CGPathAddQuadCurveToPoint(path, None, *pts[0], *pts[1])
                # Each layer only as large as its own stroke.
                pad = (width + HALO_EXTRA) / 2 + 2
                xs = [x for s in steps for x in s[1::2]]
                ys = [1024 - y for s in steps for y in s[2::2]]
                box = ((min(xs) - pad, min(ys) - pad),
                       (max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad))
                pair = []
                for into, w, rgb in ((halos, width + HALO_EXTRA, HALO), (lines, width, colour)):
                    layer = CAShapeLayer.layer()
                    layer.setBounds_(box)
                    layer.setPosition_((box[0][0] + box[1][0] / 2, box[0][1] + box[1][1] / 2))
                    layer.setPath_(path)
                    layer.setFillColor_(None)
                    layer.setStrokeColor_(_cg(rgb))
                    layer.setLineWidth_(w)
                    layer.setLineCap_("round")
                    layer.setLineJoin_("round")
                    layer.setContentsScale_(scale * size)
                    into.addSublayer_(layer)
                    pair.append(layer)
                strokes.append((i, path_length(steps), pair))
        return art, strokes, size

    def _start_pen(self):
        """Each stroke's share of the one clock, as keyframes: the pen is eased
        over the whole drawing, not stroke by stroke."""
        from Quartz import CAKeyframeAnimation

        total = BLOOM_START + BLOOM_TIME
        times = [k / SAMPLES for k in range(SAMPLES + 1)]
        phase_spans = spans()
        for phase, length, pair in self._layers["strokes"]:
            span = phase_spans[phase]
            drawn = [1.0 if self._reduced else stroke_at(pen(t * total), span) for t in times]
            shown = [min(max(d * length / FADE_IN, 0.0), 1.0) for d in drawn]
            for layer in pair:
                for key, values in (("strokeEnd", drawn), ("opacity", shown)):
                    a = CAKeyframeAnimation.animationWithKeyPath_(key)
                    a.setValues_(values)
                    a.setKeyTimes_(times)
                    a.setDuration_(total)
                    a.setCalculationMode_("linear")
                    layer.addAnimation_forKey_(a, "pen-" + key)

    # ── the hand-over ────────────────────────────────────────────────────────
    def hand_over(self, main) -> None:
        """Wait for the page; put the main window where the system wants it,
        unseen; let the window open out of the drawing; then make the real one
        visible underneath and take the splash away. Runs on its own thread.

        WHATEVER GOES WRONG, MEDSEARCH OPENS: the last step, showing the main
        window, runs in every case."""
        try:
            self.ready.wait(READY_TIMEOUT_S)
            if self._window is None:
                return
            _on_main_wait(lambda: self._place_unseen(main))
            # STAGE MANAGER, AND ANYTHING ELSE THAT ARRANGES WINDOWS, acts as the
            # window comes forward; its frame is read once it has had the chance.
            time.sleep(SETTLE_PLACE_S)
            rect = _on_main_wait(lambda: self._where(main))
            if rect is None:
                return
            wait = leave_at() - (time.monotonic() - self._t0)
            if wait > 0:
                time.sleep(wait)
            _on_main_wait(lambda: self._open_out(rect))
            time.sleep(SPLASH_OUT)
        finally:
            _on_main(lambda: self._finish(main), otherwise=lambda: _show_plainly(main))

    def _place_unseen(self, main):
        from AppKit import NSApplication
        ns = main.native
        ns.setAlphaValue_(0.0)
        ns.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    def _where(self, main):
        """The main window's frame in the splash's coordinates, and its title bar."""
        ns = main.native
        f, s = ns.frame(), self._screen
        bar = f.size.height - ns.contentRectForFrameRect_(f).size.height
        return (f.origin.x - s.origin.x, f.origin.y - s.origin.y,
                f.size.width, f.size.height, bar)

    def _open_out(self, rect):
        """The disc of the window growing out of the drawing, above it, and the
        drawing spreading and fading beneath; all of it held inside the window's
        frame, so nothing is drawn outside the window it becomes."""
        from AppKit import NSApplication
        from Quartz import (CABasicAnimation, CALayer, CAMediaTimingFunction, CAShapeLayer,
                            CATransaction, CGPathCreateWithEllipseInRect)

        x, y, w, h, bar = rect
        stage, art = self._layers["stage"], self._layers["art"]
        look = _appearance(NSApplication.sharedApplication())
        radius = corner_radius()

        CATransaction.begin()
        CATransaction.setDisableActions_(True)
        clip = CALayer.layer()
        clip.setFrame_(((x, y), (w, h)))
        clip.setCornerRadius_(radius)
        clip.setBackgroundColor_(_cg((0, 0, 0)))
        stage.setMask_(clip)

        pane = CALayer.layer()
        pane.setFrame_(((x, y), (w, h)))
        pane.setCornerRadius_(radius)
        pane.setMasksToBounds_(True)
        pane.setBackgroundColor_(_cg(GROUND[look]))
        band = CALayer.layer()
        band.setFrame_(((0, h - bar), (w, bar)))    # the top: these layers count y upwards
        band.setBackgroundColor_(_cg(TITLE_BAR[look]))
        pane.addSublayer_(band)
        stage.addSublayer_(pane)                    # above the drawing
        CATransaction.commit()

        ax, ay = art.position()
        cx, cy, far = disc((x, y, w, h), ax, ay)
        ease = CAMediaTimingFunction.functionWithControlPoints____(0.65, 0, 0.25, 1)
        if self._reduced:
            fade = CABasicAnimation.animationWithKeyPath_("opacity")
            fade.setFromValue_(0.0)
            fade.setToValue_(1.0)
            fade.setDuration_(0.3)
            pane.addAnimation_forKey_(fade, "open")
            return

        def circle(r):
            return CGPathCreateWithEllipseInRect(((cx - r, cy - r), (2 * r, 2 * r)), None)
        mask = CAShapeLayer.layer()
        mask.setFrame_(pane.bounds())
        mask.setPath_(circle(far))
        pane.setMask_(mask)
        grow = CABasicAnimation.animationWithKeyPath_("path")
        grow.setFromValue_(circle(0.5))
        grow.setToValue_(circle(far))
        grow.setDuration_(SPLASH_OUT)
        grow.setTimingFunction_(ease)
        mask.addAnimation_forKey_(grow, "open")

        # The drawing spreads radially from its middle, beneath the disc, and fades
        # in the last of it: whatever the disc has not reached by then goes with it.
        size = self._layers["size"]
        spread = CABasicAnimation.animationWithKeyPath_("transform.scale")
        spread.setFromValue_(size)
        spread.setToValue_(size * 2.4)
        spread.setDuration_(SPLASH_OUT)
        spread.setTimingFunction_(CAMediaTimingFunction.functionWithControlPoints____(0.4, 0, 0.2, 1))
        spread.setFillMode_("forwards")
        spread.setRemovedOnCompletion_(False)
        art.addAnimation_forKey_(spread, "spread")
        gone = CABasicAnimation.animationWithKeyPath_("opacity")
        gone.setFromValue_(1.0)
        gone.setToValue_(0.0)
        gone.setBeginTime_(art.convertTime_fromLayer_(_now(), None) + 0.25)
        gone.setDuration_(0.3)
        gone.setTimingFunction_(CAMediaTimingFunction.functionWithName_("easeIn"))
        gone.setFillMode_("both")
        gone.setRemovedOnCompletion_(False)
        art.addAnimation_forKey_(gone, "gone")

    def _finish(self, main):
        """The real window, fully there; the splash fading off it, then closed."""
        _show_plainly(main)
        w = self._window
        if w is None:
            return
        from AppKit import NSAnimationContext
        from PyObjCTools import AppHelper
        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(SETTLE_S)
        w.animator().setAlphaValue_(0.0)
        NSAnimationContext.endGrouping()

        def close():
            w.orderOut_(None)
            w.close()
            self._window = None
        AppHelper.callLater(SETTLE_S + 0.15, close)


def _show_plainly(main):
    """The main window, opaque and on screen, however the rest went."""
    try:
        ns = main.native
        ns.setAlphaValue_(1.0)
        if not ns.isVisible():
            main.show()
    except Exception as e:
        print(f"  (splash: {e!r})")
        try:
            main.show()
        except Exception:
            pass


def _appearance(app) -> str:
    try:
        from AppKit import NSAppearanceNameAqua, NSAppearanceNameDarkAqua
        best = app.effectiveAppearance().bestMatchFromAppearancesWithNames_(
            [NSAppearanceNameAqua, NSAppearanceNameDarkAqua])
        return "dark" if best == NSAppearanceNameDarkAqua else "light"
    except Exception:
        return "light"


def _cg(rgb, alpha=1.0):
    from Quartz import CGColorCreateGenericRGB
    return CGColorCreateGenericRGB(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, alpha)


def _now():
    from Quartz import CACurrentMediaTime
    return CACurrentMediaTime()


def _on_main_wait(fn, timeout: float = 2.0):
    """Run `fn` on the main thread and return what it returns; None if it failed
    or the main thread did not get to it in time."""
    got, done = [], threading.Event()

    def run():
        try:
            got.append(fn())
        finally:
            done.set()
    _on_main(run, otherwise=done.set)
    done.wait(timeout)
    return got[0] if got else None


def _on_main(fn, otherwise=None) -> None:
    """Run `fn` on the main thread, where AppKit accepts window changes. If it
    fails, `otherwise` runs instead: MedSearch still opens, only less gracefully."""
    def safe():
        try:
            fn()
        except Exception as exc:
            print(f"  (splash: {exc!r})")
            if otherwise:
                otherwise()
    try:
        from PyObjCTools import AppHelper
        AppHelper.callAfter(safe)
    except Exception:
        if otherwise:
            otherwise()

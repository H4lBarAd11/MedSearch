# MedSearch — the splash, on Windows.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""splash.py's splash, drawn on Windows (his choice, 30 Sep): the same drawing
on the same clock, and the window growing out of it.

A SEE-THROUGH WINDOW OF ITS OWN: a layered window (every pixel its own alpha),
click-through, above everything and out of the taskbar, on a GUI thread of its
own, so it is up before pywebview has built anything. Each frame is drawn with
GDI+ (System.Drawing, which pywebview's WinForms already loads) and handed to
the window whole.

THE SAME GEOMETRY, A RENDERER BY HAND. Core Animation strokes a path to a given
length and eases its own clock. Here each path is flattened (splash.flatten),
cut to the length the pen has reached (splash.prefix) and eased by the same
curves (splash.bezier_ease), from the Mac's PHASES, spans and clock.

THE WINDOW IS NOT SHOWN UNSEEN FIRST, as on the Mac: nothing on Windows moves a
window as it appears, and pywebview has already placed it while building it
hidden. Its frame is read as it is, and it is shown once the disc has become it.

IF ANY OF IT FAILS, MEDSEARCH OPENS: the splash is skipped and the window shown
plainly, as on the Mac.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time

import splash as S

FRAME_MS = 15
#: Windows' own title bar, light and dark (a plain window's, not Mica).
TITLE_BAR = {"light": (0xFF, 0xFF, 0xFF), "dark": (0x20, 0x20, 0x20)}
GROUND = S.GROUND

_OPEN_EASE = S.bezier_ease(0.65, 0, 0.25, 1)     # the disc (splash._open_out)
_SPREAD_EASE = S.bezier_ease(0.4, 0, 0.2, 1)     # the drawing spreading
_GONE_EASE = S.bezier_ease(0.42, 0, 1, 1)        # Core Animation's easeIn

#: Every stroke once: (phase, width, colour, points, length).
STROKES = [(i, width, rgb, S.flatten(path), S.path_length(path))
           for i, phase in enumerate(S.PHASES) for width, rgb, path in phase]
_SPANS = S.spans()


def pen_frame(elapsed: float, reduced: bool = False) -> list:
    """What is on screen `elapsed` s in: (width, colour, points drawn, opacity)
    for each stroke the pen has reached. With reduced motion, all of it."""
    progress = S.pen(elapsed)
    out = []
    for phase, width, rgb, pts, length in STROKES:
        drawn = 1.0 if reduced else S.stroke_at(progress, _SPANS[phase])
        if drawn <= 0.0:
            continue
        shown = min(max(drawn * length / S.FADE_IN, 0.0), 1.0)
        out.append((width, rgb, S.prefix(pts, drawn), shown))
    return out


def open_frame(t: float, reduced: bool = False):
    """(disc 0..1, the drawing's spread, its opacity, the pane's opacity) `t` s
    into the opening: splash._open_out's four animations, sampled."""
    if reduced:
        return 1.0, 1.0, 1.0, min(max(t / 0.3, 0.0), 1.0)
    x = min(max(t / S.SPLASH_OUT, 0.0), 1.0)
    gone = min(max((t - 0.25) / 0.3, 0.0), 1.0)
    return _OPEN_EASE(x), 1.0 + 1.4 * _SPREAD_EASE(x), 1.0 - _GONE_EASE(gone), 1.0


def corner_radius() -> float:
    """Windows 11 rounds a window's corners; Windows 10 does not."""
    try:
        return 8.0 if sys.getwindowsversion().build >= 22000 else 0.0
    except Exception:
        return 0.0


# ── Win32 ────────────────────────────────────────────────────────────────────
_GWL_EXSTYLE = -20
_WS_EX = 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000 | 0x00000008
#        layered    | click-through | no taskbar | never activated | topmost
_SW_SHOWNOACTIVATE = 4
_HWND_TOPMOST = -1
_SWP = 0x0001 | 0x0002 | 0x0010                 # no size, no move, no activation
_ULW_ALPHA = 2


class _BLEND(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


def _win32():
    from ctypes import wintypes as w
    u, g = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    p = ctypes.POINTER
    u.UpdateLayeredWindow.argtypes = [w.HWND, w.HDC, p(w.POINT), p(w.SIZE), w.HDC,
                                      p(w.POINT), w.COLORREF, p(_BLEND), w.DWORD]
    u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]
    u.SetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int, ctypes.c_ssize_t]
    u.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, w.UINT]
    u.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
    u.GetDC.restype = w.HDC
    u.GetDC.argtypes = [w.HWND]
    u.ReleaseDC.argtypes = [w.HWND, w.HDC]
    g.CreateCompatibleDC.restype = w.HDC
    g.CreateCompatibleDC.argtypes = [w.HDC]
    g.SelectObject.restype = w.HGDIOBJ
    g.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
    g.DeleteObject.argtypes = [w.HGDIOBJ]
    g.DeleteDC.argtypes = [w.HDC]
    g.GetDeviceCaps.argtypes = [w.HDC, ctypes.c_int]
    return u, g, w


def _dpi_aware():
    """What pywebview asks for too, asked first: the splash is up before it."""
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _animations_on() -> bool:
    """Settings ▸ Accessibility ▸ Visual effects ▸ Animation effects."""
    try:
        on = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(on), 0)
        return bool(on.value)
    except Exception:
        return True


def _look() -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
    except Exception:
        return "light"


class Splash:
    """The drawing's window, and the hand-over from it to the main window."""

    def __init__(self):
        self.ready = threading.Event()          # set by the page, through app.py
        self._form = None
        self._t0 = None
        self._opening = None                    # (start, frame, title bar) once opening
        self._fade = None                       # when the fading off began
        self._still = False                     # the finished drawing is on screen

    # ── its own GUI thread ───────────────────────────────────────────────────
    def open(self) -> None:
        """Put the drawing up and start the pen, on a GUI thread of its own.
        Returns once it is up (or has failed)."""
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        from System.Threading import ApartmentState, Thread, ThreadStart
        import System.Windows.Forms as WinForms

        _dpi_aware()
        up = threading.Event()

        def run():
            try:
                self._build(WinForms)
            except Exception as e:
                print(f"  (splash unavailable: {e!r})")
                self._form = None
                up.set()
                return
            up.set()
            WinForms.Application.Run()

        t = Thread(ThreadStart(run))
        t.SetApartmentState(ApartmentState.STA)
        t.IsBackground = True
        t.Start()
        up.wait(3.0)

    def _build(self, WinForms):
        self._u, self._g, self._w = _win32()
        self._wf = WinForms
        self._reduced = not _animations_on()
        self._look = _look()
        f = WinForms.Form()
        f.FormBorderStyle = getattr(WinForms.FormBorderStyle, "None")
        f.ShowInTaskbar = False
        f.StartPosition = WinForms.FormStartPosition.Manual
        hwnd = f.Handle.ToInt64()
        u = self._u
        u.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, u.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE) | _WS_EX)
        screen = u.GetDC(None)
        try:
            self._scale = (self._g.GetDeviceCaps(screen, 88) or 96) / 96    # LOGPIXELSX
        finally:
            u.ReleaseDC(None, screen)
        left, top, right, bottom = S.bounds()
        self._mid = ((left + right) / 2, (top + bottom) / 2)            # icon units
        self._k = S.WIDTH_PT * self._scale / (right - left)              # px per unit
        self._centre = (u.GetSystemMetrics(0) / 2, u.GetSystemMetrics(1) / 2)
        half_w, half_h = (right - left) / 2 * self._k, (bottom - top) / 2 * self._k
        self._box = (int(self._centre[0] - half_w) - 2, int(self._centre[1] - half_h) - 2,
                     int(2 * half_w) + 4, int(2 * half_h) + 4)
        self._form, self._hwnd = f, hwnd
        self._t0 = time.monotonic()
        self._frame()                             # the first frame, before it shows
        u.ShowWindow(hwnd, _SW_SHOWNOACTIVATE)
        u.SetWindowPos(hwnd, _HWND_TOPMOST, 0, 0, 0, 0, _SWP)
        self._timer = WinForms.Timer()
        self._timer.Interval = FRAME_MS
        self._timer.Tick += lambda s, e: self._tick()
        self._timer.Start()

    def _on_splash(self, fn):
        from System import Action
        f = self._form
        if f is not None:
            try:
                f.BeginInvoke(Action(fn))
            except Exception:
                pass

    def _tick(self):
        try:
            if self._fade is not None:
                self._fading()
            else:
                self._frame()
        except Exception as e:
            print(f"  (splash: {e!r})")
            self._close()

    # ── the frames ───────────────────────────────────────────────────────────
    def _frame(self):
        now = time.monotonic()
        if self._opening is None:
            finished = now - self._t0 > S.BLOOM_START + S.BLOOM_TIME + 0.1
            if finished and self._still:
                return                             # nothing moves until the page is ready
            self._still = finished
            x, y, w, h = self._box
            strokes = pen_frame(now - self._t0, self._reduced)
            cx, cy = self._centre[0] - x, self._centre[1] - y
            self._present(self._render(w, h, lambda g: self._art(g, w, h, strokes, cx, cy,
                                                                 self._k, 1.0)), x, y, w, h)
            return
        start, (x, y, w, h), bar = self._opening
        disc, spread, art_alpha, pane_alpha = open_frame(now - start, self._reduced)
        strokes = pen_frame(1e9)
        cx, cy = self._centre[0] - x, self._centre[1] - y
        dx, dy, far = S.disc((x, y, w, h), self._centre[0], self._centre[1])
        look = self._look

        def draw(g):
            from System.Drawing import Color, Rectangle, RectangleF, SolidBrush
            from System.Drawing.Drawing2D import CombineMode
            frame = _rounded(0, 0, w, h, corner_radius() * self._scale)
            g.SetClip(frame)
            self._art(g, w, h, strokes, cx, cy, self._k * spread, art_alpha)
            r = 0.5 + (far - 0.5) * disc
            from System.Drawing.Drawing2D import GraphicsPath
            round_ = GraphicsPath()
            round_.AddEllipse(RectangleF(dx - r, dy - r, 2 * r, 2 * r))
            g.SetClip(frame)
            g.SetClip(round_, CombineMode.Intersect)
            a = int(255 * pane_alpha)
            g.FillRectangle(SolidBrush(Color.FromArgb(a, *GROUND[look])), Rectangle(0, 0, w, h))
            g.FillRectangle(SolidBrush(Color.FromArgb(a, *TITLE_BAR[look])), Rectangle(0, 0, w, bar))
        self._present(self._render(w, h, draw), x, y, w, h)

    def _render(self, w, h, draw):
        from System.Drawing import Bitmap, Color, Graphics
        from System.Drawing.Drawing2D import SmoothingMode
        from System.Drawing.Imaging import PixelFormat
        bmp = Bitmap(max(w, 1), max(h, 1), PixelFormat.Format32bppArgb)
        g = Graphics.FromImage(bmp)
        try:
            g.SmoothingMode = SmoothingMode.AntiAlias
            g.Clear(Color.Transparent)
            draw(g)
        finally:
            g.Dispose()
        return bmp

    def _art(self, g, w, h, strokes, cx, cy, k, alpha):
        """The drawing, its middle at (cx, cy), `k` px to the icon's unit: the
        halos first, as one faint layer (where two cross it is no darker), then
        the lines."""
        from System import Array
        from System.Drawing import Color, Graphics, Pen, PointF, Rectangle
        from System.Drawing.Drawing2D import LineCap, LineJoin, SmoothingMode
        from System.Drawing.Imaging import (ColorAdjustType, ColorMatrix, ColorMatrixFlag,
                                            ImageAttributes)

        def place(gr):
            gr.TranslateTransform(cx, cy)
            gr.ScaleTransform(k, k)
            gr.TranslateTransform(-self._mid[0], -self._mid[1])

        def strokes_on(gr, halo):
            for width, rgb, pts, shown in strokes:
                if len(pts) < 2:
                    continue
                colour = S.HALO if halo else rgb
                a = int(255 * shown * (1.0 if halo else alpha))
                pen = Pen(Color.FromArgb(a, *colour), width + (S.HALO_EXTRA if halo else 0))
                pen.StartCap = pen.EndCap = LineCap.Round
                pen.LineJoin = LineJoin.Round
                gr.DrawLines(pen, Array[PointF]([PointF(px, py) for px, py in pts]))
                pen.Dispose()

        halos = self._render(w, h, lambda gr: (place(gr), strokes_on(gr, True)))
        m = ColorMatrix()
        m.Matrix33 = S.HALO_ALPHA * alpha
        attrs = ImageAttributes()
        attrs.SetColorMatrix(m, ColorMatrixFlag.Default, ColorAdjustType.Bitmap)
        from System.Drawing import GraphicsUnit
        g.DrawImage(halos, Rectangle(0, 0, w, h), 0, 0, w, h, GraphicsUnit.Pixel, attrs)
        halos.Dispose()
        state = g.Save()
        place(g)
        strokes_on(g, False)
        g.Restore(state)

    def _present(self, bmp, x, y, w, h, alpha=255):
        """The bitmap as the window's picture, at (x, y) on the screen."""
        from System.Drawing import Color
        u, gd, wt = self._u, self._g, self._w
        hbmp = bmp.GetHbitmap(Color.FromArgb(0)).ToInt64()
        screen = u.GetDC(None)
        mem = gd.CreateCompatibleDC(screen)
        old = gd.SelectObject(mem, hbmp)
        try:
            u.UpdateLayeredWindow(self._hwnd, screen, ctypes.byref(wt.POINT(x, y)),
                                  ctypes.byref(wt.SIZE(w, h)), mem,
                                  ctypes.byref(wt.POINT(0, 0)), 0,
                                  ctypes.byref(_BLEND(0, 0, alpha, 1)), _ULW_ALPHA)
        finally:
            gd.SelectObject(mem, old)
            gd.DeleteObject(hbmp)
            gd.DeleteDC(mem)
            u.ReleaseDC(None, screen)
            bmp.Dispose()

    def _fading(self):
        share = (time.monotonic() - self._fade) / S.SETTLE_S
        if share >= 1.0:
            self._close()
            return
        self._u.UpdateLayeredWindow(self._hwnd, None, None, None, None, None, 0,
                                    ctypes.byref(_BLEND(0, 0, int(255 * (1 - share)), 1)),
                                    _ULW_ALPHA)

    def _close(self):
        try:
            self._timer.Stop()
        except Exception:
            pass
        f, self._form = self._form, None
        if f is not None:
            f.Close()
            f.Dispose()
        self._wf.Application.ExitThread()

    # ── the hand-over ────────────────────────────────────────────────────────
    def hand_over(self, main) -> None:
        """Wait for the page; let the window open out of the drawing; then show
        the real one underneath and fade the splash off. On its own thread.

        WHATEVER GOES WRONG, MEDSEARCH OPENS: the last step, showing the main
        window, runs in every case."""
        try:
            self.ready.wait(S.READY_TIMEOUT_S)
            if self._form is None:
                return
            where = _on_gui_wait(main, lambda: _frame_of(main.native))
            if where is None:
                return
            wait = S.leave_at() - (time.monotonic() - self._t0)
            if wait > 0:
                time.sleep(wait)
            self._on_splash(lambda: setattr(self, "_opening", (time.monotonic(),) + where))
            time.sleep(S.SPLASH_OUT)
        finally:
            _on_gui_wait(main, lambda: _show_plainly(main))
            self._on_splash(lambda: setattr(self, "_fade", time.monotonic()))


def _rounded(x, y, w, h, r):
    from System.Drawing import Rectangle
    from System.Drawing.Drawing2D import GraphicsPath
    path = GraphicsPath()
    if r <= 0:
        path.AddRectangle(Rectangle(x, y, w, h))
        return path
    d = 2 * r
    path.AddArc(x, y, d, d, 180, 90)
    path.AddArc(x + w - d, y, d, d, 270, 90)
    path.AddArc(x + w - d, y + h - d, d, d, 0, 90)
    path.AddArc(x, y + h - d, d, d, 90, 90)
    path.CloseFigure()
    return path


def _frame_of(form):
    """((x, y, w, h), title bar height) of the window as drawn on screen: its
    bounds less the invisible borders Windows 10 and 11 give a resizable window.
    DWM says exactly where those are, but only for a window on screen; for one
    still hidden they are worked out from the system's frame metrics."""
    from ctypes import wintypes as w
    rect = w.RECT()
    hwnd = form.Handle.ToInt64()
    b = form.Bounds
    x, y, width, height = b.X, b.Y, b.Width, b.Height
    try:
        if not form.Visible:
            raise OSError("hidden")
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(
                w.HWND(hwnd), 9, ctypes.byref(rect), ctypes.sizeof(rect)) == 0 \
                and rect.right > rect.left:
            x, y, width, height = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        else:
            raise OSError("no frame")
    except Exception:
        u = ctypes.windll.user32
        side = u.GetSystemMetrics(32) + u.GetSystemMetrics(92) - 1    # frame + padding
        x, width, height = x + side, width - 2 * side, height - side
    client_top = form.RectangleToScreen(form.ClientRectangle).Top
    return (x, y, width, height), max(client_top - y, 0)


def _show_plainly(main):
    """The main window, opaque and on screen, however the rest went."""
    try:
        form = main.native
        form.Opacity = 1.0
        if not form.Visible:
            form.Show()
        form.Activate()
    except Exception as e:
        print(f"  (splash: {e!r})")
        try:
            main.show()
        except Exception:
            pass


def _on_gui_wait(main, fn, timeout: float = 2.0):
    """Run `fn` on pywebview's GUI thread and return what it returns; None if it
    failed or the thread did not get to it in time."""
    from System import Action
    got, done = [], threading.Event()

    def run():
        try:
            got.append(fn())
        except Exception as e:
            print(f"  (splash: {e!r})")
        finally:
            done.set()
    try:
        main.native.BeginInvoke(Action(run))
    except Exception:
        return None
    done.wait(timeout)
    return got[0] if got else None

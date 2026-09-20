# Copyright 2026 Riccardo Nevoso
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""MedSearch's application icon: an open book in ivory line on the house sage,
with a caramel magnifier resting on it (his choice, 20 Sep, option C).

    .venv/bin/python render_icon.py          → icon.icns, icon_preview.png

GENERATED, NOT DRAWN IN AN EDITOR. The icon is code for the same reason the
README's banner is: an exported file is one nobody can change. The colours are
the application's own, read from static/css/app.css, so the icon cannot drift
away from the interface.

FLAT, AND ON THE APPLE GRID. The old icon had a gradient ground, highlights and
four browns, from before the house style. This one is flat: sage ground, ivory
line, one caramel. The body is 824 of a 1024 canvas, which is the proportion
macOS expects, so it sits at the same size as every other app in the Dock.

THE LINE IS THE INTERFACE'S LINE. Same construction as the icons in the app:
even stroke, round caps and joins, no fill inside the drawing.
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
CSS = ROOT / "static" / "css" / "app.css"

OUT = 1024                     # the canvas macOS asks for
SS = 4                         # supersampling: draw big, shrink once
W = OUT * SS
BODY = 824 / 1024              # Apple's grid: the artwork's own square


def palette() -> dict:
    """The light theme's tokens from app.css — the interface's colours."""
    light = CSS.read_text(encoding="utf-8").split("@media (prefers-color-scheme: dark)")[0]
    hexes = {m.group(1): m.group(2) for m in
             re.finditer(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", light)}
    return {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) + (255,) for k, v in hexes.items()}


def q(p0, p1, p2, steps=60):
    """A quadratic Bézier as points, so a curve can be stroked as a polyline."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1])
            for t in (i / steps for i in range(steps + 1))]


def stroke(d, pts, fill, width, round_caps=True):
    """A polyline with round joins and caps: PIL draws neither on its own."""
    d.line([(round(x), round(y)) for x, y in pts], fill=fill, width=width, joint="curve")
    if round_caps:
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=fill)


def draw(c: dict) -> Image.Image:
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = W / 1024                                   # one canvas unit
    m = (1 - BODY) / 2 * W                         # margin around the artwork

    # ── the ground: flat sage, Apple's corner radius (~22% of the body) ──
    d.rounded_rectangle([m, m, W - m, W - m], radius=int(0.225 * BODY * W), fill=c["accent"])

    ivory, caramel = c["bg"], c["yellow"]
    line_w, thin_w = int(30 * u), int(22 * u)

    # ── the open book, in ivory line ──
    # Spine at the centre; each page a curve out and a curve back, as the app's
    # own icons are drawn: outline only, nothing filled.
    spine_top, spine_bot = (512 * u, 322 * u), (512 * u, 726 * u)
    for side in (-1, 1):
        outer_x = 512 * u + side * 262 * u
        top = q(spine_top, (512 * u + side * 150 * u, 286 * u), (outer_x, 306 * u))
        bot = q(spine_bot, (512 * u + side * 150 * u, 690 * u), (outer_x, 700 * u))
        stroke(d, top, ivory, line_w)
        stroke(d, bot, ivory, line_w)
        stroke(d, [(outer_x, 306 * u), (outer_x, 700 * u)], ivory, line_w)
    stroke(d, [spine_top, spine_bot], ivory, line_w)

    # three lines of text on the left page
    for i, length in enumerate((120, 120, 84)):
        y = (404 + i * 70) * u
        stroke(d, [(330 * u, y), ((330 + length) * u, y)], ivory, thin_w)

    # ── the magnifier, in caramel, over the right page ──
    cx, cy, r = 648 * u, 520 * u, 96 * u
    ring = [(cx + r * math.cos(a), cy + r * math.sin(a))
            for a in (i / 120 * 2 * math.pi for i in range(121))]
    # A sage disc under the ring keeps the page's lines out of the lens, so the
    # magnifier reads as an object on top rather than a circle drawn over text.
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c["accent"])
    stroke(d, ring, caramel, int(34 * u), round_caps=False)
    handle_w = int(44 * u)
    a = math.pi / 4
    stroke(d, [(cx + r * math.cos(a), cy + r * math.sin(a)), (802 * u, 674 * u)],
           caramel, handle_w)
    return img.resize((OUT, OUT), Image.LANCZOS)


def icns(png: Path) -> Path:
    """icon.icns from the 1024 px artwork, through macOS's own iconutil."""
    iconset = ROOT / "icon.iconset"
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir()
    master = Image.open(png)
    for size in (16, 32, 64, 128, 256, 512, 1024):
        for name, px in ((f"icon_{size}x{size}.png", size),
                         (f"icon_{size // 2}x{size // 2}@2x.png", size)):
            if name.startswith("icon_8x8"):
                continue
            master.resize((px, px), Image.LANCZOS).save(iconset / name)
    out = ROOT / "icon.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
    shutil.rmtree(iconset, ignore_errors=True)
    return out


def main() -> None:
    art = draw(palette())
    preview = ROOT / "icon_preview.png"
    art.save(preview)
    out = icns(preview)
    print(f"✓ {out.name} and {preview.name} ({OUT}px, {int(BODY * OUT)}px body)")


if __name__ == "__main__":
    main()

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
"""MedSearch's menu bar glyph: the application icon's drawing, at menu bar size.

    .venv/bin/python render_menubar_icon.py      → menubar_icon.png (36 px)

A TEMPLATE IMAGE: solid black on transparent. macOS tints it itself, so the one
file is right on a light menu bar, a dark one, and while the menu is open. It
must therefore carry no colour of its own — this is the one place the house
palette does not reach.

THE SAME DRAWING AS THE ICON, NOT A SECOND ONE. Open book, magnifier over the
right page (render_icon.py). At 18 points the icon's three lines of text and its
page curves close up into mush, so the glyph keeps the silhouette and drops the
detail: flat pages, two text lines, a slightly larger lens.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
TARGET = 36                 # 18 pt at 2x, the size the status item asks for
SS = 8                      # supersampling: draw big, shrink once
W = TARGET * SS
BLACK = (0, 0, 0, 255)


def u(v):                   # one glyph unit (the drawing is laid out on 36)
    return v * SS


def stroke(d, pts, width, round_caps=True):
    d.line([(round(x), round(y)) for x, y in pts], fill=BLACK, width=width, joint="curve")
    if round_caps:
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=BLACK)


def draw() -> Image.Image:
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    line_w = max(1, int(u(2.0)))
    thin_w = max(1, int(u(1.6)))

    # ── the open book: straight pages, which is all that survives at this size ──
    spine_top, spine_bot = (u(18), u(10.5)), (u(18), u(26.5))
    for side in (-1, 1):
        outer = u(18 + side * 12)
        stroke(d, [spine_top, (outer, u(9))], line_w)
        stroke(d, [spine_bot, (outer, u(25))], line_w)
        stroke(d, [(outer, u(9)), (outer, u(25))], line_w)
    stroke(d, [spine_top, spine_bot], line_w)

    # two lines of text on the left page
    for y in (u(15), u(19)):
        stroke(d, [(u(9.5), y), (u(15), y)], thin_w)

    # ── the magnifier over the right page ──
    cx, cy, r = u(24), u(18), u(5)
    ring = [(cx + r * math.cos(a), cy + r * math.sin(a))
            for a in (i / 90 * 2 * math.pi for i in range(91))]
    # Clear the page lines behind the lens, so the two drawings don't merge.
    d.ellipse([cx - r - line_w, cy - r - line_w, cx + r + line_w, cy + r + line_w],
              fill=(0, 0, 0, 0))
    stroke(d, ring, line_w, round_caps=False)
    a = math.pi / 4
    stroke(d, [(cx + r * math.cos(a), cy + r * math.sin(a)), (u(31), u(25))],
           max(1, int(u(2.4))))
    return img.resize((TARGET, TARGET), Image.LANCZOS)


if __name__ == "__main__":
    out = ROOT / "menubar_icon.png"
    draw().save(out)
    print(f"✓ {out.name} ({TARGET}px template: black on transparent)")

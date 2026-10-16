#!/usr/bin/env python3
# MedSearch — search the medical literature, many sources at once.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""Draw the README's banner in the application's own house style.

    .venv/bin/python scripts/make-readme-art.py

GENERATED, NOT EXPORTED. A banner saved out of a design tool is a file nobody can
change; this script is the artwork, and it reads the palette, the typeface and the
icon from where the application keeps them. Re-run it after changing any of them.

SVG, AND THE TYPEFACE TRAVELS INSIDE IT. GitHub renders a README without its
stylesheet, so the house style can only arrive as images. The DM Sans faces the
application ships are embedded as data URIs, with the system sans-serif stack
behind them. DM Sans is under the SIL Open Font License, which permits embedding;
see static/fonts/OFL.txt.

THE IVORY GROUND IS PART OF THE IMAGE. On GitHub's dark theme a transparent figure
would put ink on near-black, so the banner carries its own ground and hairline.

    docs/readme/banner.svg   the icon, the wordmark, what it does, who made it
    docs/readme/icon.png     the application icon at 256 px (from icon.icns, via sips)
    docs/readme/social-preview.svg, .png
                             the banner at 1280 x 640, for the picture a shared link
                             to the repository shows (uploaded in the repository's
                             Settings). The PNG is drawn by WebKit, through the PyObjC
                             that the native window brings, so it needs the project's
                             Python; any other writes the SVGs and says so.
"""
from __future__ import annotations

import base64
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "readme"
CSS = ROOT / "static" / "css" / "app.css"
FONTS = ROOT / "static" / "fonts"

STACK = "'DM Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"


def palette() -> dict:
    """The light theme's `--token: #hex` pairs from app.css: the application's
    colours, not copies. Only the first :root block, before the dark overrides."""
    light = CSS.read_text(encoding="utf-8").split("@media (prefers-color-scheme: dark)")[0]
    return {m.group(1): m.group(2) for m in
            re.finditer(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", light)}


def font_faces(weights=(400, 500, 800)) -> str:
    faces = []
    for w in weights:
        data = base64.b64encode((FONTS / f"dm-sans-{w}.woff2").read_bytes()).decode()
        faces.append(f"@font-face{{font-family:'DM Sans';font-weight:{w};"
                     f"src:url(data:font/woff2;base64,{data}) format('woff2')}}")
    return "".join(faces)


def icon_png() -> Path:
    """icon.icns at 256 px. `sips` ships with macOS, so no imaging dependency."""
    out = OUT / "icon.png"
    subprocess.run(["sips", "-s", "format", "png", "-z", "256", "256",
                    str(ROOT / "icon.icns"), "--out", str(out)],
                   check=True, capture_output=True)
    return out


def banner(c: dict, icon: Path) -> str:
    W, H = 1280, 360
    png = base64.b64encode(icon.read_bytes()).decode()
    body = (
        '<title>MedSearch</title>'
        f'<image x="92" y="70" width="220" height="220" href="data:image/png;base64,{png}"/>'
        # THE WORDMARK AS THE APPLICATION DRAWS IT: Med in ink, Search in sage, 800.
        f'<text x="352" y="178" font-size="104" font-weight="800" letter-spacing="-3" '
        f'fill="{c["text"]}">Med<tspan fill="{c["wordmark"]}">Search</tspan></text>'
        f'<text x="356" y="228" font-size="27" font-weight="500" fill="{c["text"]}">'
        'The medical literature, sixteen sources at once</text>'
        f'<text x="356" y="263" font-size="27" font-weight="500" fill="{c["text"]}">'
        'with AI summaries, a PDF reader and a research assistant</text>'
        f'<line x1="356" y1="292" x2="1188" y2="292" stroke="{c["border"]}" stroke-width="2"/>'
        f'<text x="356" y="324" font-size="19" font-weight="400" fill="{c["text3"]}">'
        'Riccardo Nevoso · a personal project · for macOS and Windows'
        f'<tspan fill="{c["yellow"]}" font-weight="500">   ·   Apache-2.0</tspan></text>'
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" role="img">'
            f"<style>{font_faces()}text{{font-family:{STACK}}}</style>"
            f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" '
            f'fill="{c["bg"]}" stroke="{c["border"]}" stroke-width="2"/>'
            f"{body}</svg>\n")


def social_preview(c: dict, icon: Path) -> str:
    """The banner's layout at GitHub's 2:1 for a social preview: the icon on the
    left, the wordmark, what it does and who made it on the right, the block
    centred top to bottom."""
    W, H = 1280, 640
    png = base64.b64encode(icon.read_bytes()).decode()
    body = (
        '<title>MedSearch</title>'
        f'<image x="45" y="180" width="280" height="280" href="data:image/png;base64,{png}"/>'
        f'<text x="369" y="282" font-size="124" font-weight="800" letter-spacing="-3.5" '
        f'fill="{c["text"]}">Med<tspan fill="{c["wordmark"]}">Search</tspan></text>'
        f'<text x="375" y="342" font-size="31" font-weight="500" fill="{c["text"]}">'
        'The medical literature, sixteen sources at once</text>'
        f'<text x="375" y="384" font-size="31" font-weight="500" fill="{c["text"]}">'
        'with AI summaries, a PDF reader and a research assistant</text>'
        f'<line x1="375" y1="418" x2="1165" y2="418" stroke="{c["border"]}" stroke-width="2"/>'
        f'<text x="375" y="456" font-size="21" font-weight="400" fill="{c["text3"]}">'
        'Riccardo Nevoso · a personal project · for macOS and Windows'
        f'<tspan fill="{c["yellow"]}" font-weight="500">   ·   Apache-2.0</tspan></text>'
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" role="img">'
            f"<style>{font_faces()}text{{font-family:{STACK}}}</style>"
            f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="18" '
            f'fill="{c["bg"]}" stroke="{c["border"]}" stroke-width="2"/>'
            f"{body}</svg>\n")


def png_of(svg: Path, out: Path, w: int, h: int) -> bool:
    """`svg` drawn as `out`, w x h pixels, by WebKit: the engine MedSearch's own
    window uses, so the embedded faces come out as they do there. False when
    this Python has no PyObjC."""
    try:
        from AppKit import NSApplication, NSBitmapImageRep, NSPNGFileType
        from Foundation import NSDate, NSMakeRect, NSRunLoop, NSURL
        from WebKit import WKSnapshotConfiguration, WKWebView, WKWebViewConfiguration
    except ImportError:
        return False
    NSApplication.sharedApplication()
    view = WKWebView.alloc().initWithFrame_configuration_(
        NSMakeRect(0, 0, w, h), WKWebViewConfiguration.alloc().init())
    url = NSURL.fileURLWithPath_(str(svg))
    view.loadFileURL_allowingReadAccessToURL_(url, url)

    def spin(seconds):
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))
    spin(0.2)
    while view.isLoading():
        spin(0.1)
    spin(0.5)                                   # the faces, decoded after the load
    shot = {}
    config = WKSnapshotConfiguration.alloc().init()
    config.setRect_(NSMakeRect(0, 0, w, h))
    config.setSnapshotWidth_(w)
    view.takeSnapshotWithConfiguration_completionHandler_(
        config, lambda image, error: shot.update(image=image, error=error))
    while not shot:
        spin(0.1)
    if shot["image"] is None:
        raise RuntimeError(f"WebKit could not draw {svg.name}: {shot['error']}")
    rep = NSBitmapImageRep.imageRepWithData_(shot["image"].TIFFRepresentation())
    rep.representationUsingType_properties_(NSPNGFileType, {}).writeToFile_atomically_(str(out), True)
    # A Retina screen draws two pixels to the point: brought back to w x h.
    subprocess.run(["sips", "-z", str(h), str(w), str(out)], check=True, capture_output=True)
    return True


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = palette()
    icon = icon_png()
    (OUT / "banner.svg").write_text(banner(c, icon), encoding="utf-8")
    social = OUT / "social-preview.svg"
    social.write_text(social_preview(c, icon), encoding="utf-8")
    print(f"wrote {OUT / 'banner.svg'}, {icon} and {social}")
    if png_of(social, OUT / "social-preview.png", 1280, 640):
        print(f"wrote {OUT / 'social-preview.png'}")
    else:
        print("social-preview.png not drawn: run this with the project's Python "
              "(.venv/bin/python), which has PyObjC")


if __name__ == "__main__":
    main()

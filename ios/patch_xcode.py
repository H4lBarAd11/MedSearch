# MedSearch for iOS — what the generated Xcode project needs after `briefcase create`.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""Two fixes to the project Briefcase generates, applied in place, safe to run
again:  cd ios && python3 patch_xcode.py

1. The build phase that installs the Python packages leaves one path
   unquoted, and this repository's path has a space in it ("Coding
   Projects"): the build failed at `source`. Quoted.

2. The launch screen: the interface's ground, ivory or dark as the phone
   is, with the drawing centred, 320 points square, as the Mac's splash. What the system shows of it varies:
   his phone (iOS 27.1 beta) drew the ground and never the image, whatever
   image, name, size or layout it was given, through a reinstall and a
   restart, while the simulator drew it; the Info.plist form (UILaunchScreen)
   drew on the phone and came out white in the simulator (19 Oct). So the
   launch screen is only asked for the ground, and the drawing is the app's
   own, put up by shell.py the moment its window exists and taken down when
   the page is ready, as the Mac's splash is.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

XCODE = Path(__file__).resolve().parent / "build" / "medsearch" / "ios" / "xcode"
PBXPROJ = XCODE / "MedSearch.xcodeproj" / "project.pbxproj"
STORYBOARD = XCODE / "MedSearch" / "Launch Screen.storyboard"
ASSETS = XCODE / "MedSearch" / "Images.xcassets"

UNQUOTED = "source $PROJECT_DIR/Support/Python.xcframework/build/utils.sh"
QUOTED = 'source \\"$PROJECT_DIR/Support/Python.xcframework/build/utils.sh\\"'

IVORY = 'red="0.976" green="0.973" blue="0.937"'      # app.css --bg, #F9F8EF
DARK = 'red="0.106" green="0.102" blue="0.090"'       # its dark counterpart, #1B1A17
#: The ground, light and dark (his ask, 19 Oct: a dark mode for the splash):
#: a colour set in the catalogue, which the storyboard names and the app's
#: own splash (shell.py) repeats.
COLORSET = """{
  "colors" : [
    { "idiom" : "universal",
      "color" : { "color-space" : "srgb", "components" : { "red" : "0.976", "green" : "0.973", "blue" : "0.937", "alpha" : "1.000" } } },
    { "idiom" : "universal",
      "appearances" : [ { "appearance" : "luminosity", "value" : "dark" } ],
      "color" : { "color-space" : "srgb", "components" : { "red" : "0.106", "green" : "0.102", "blue" : "0.090", "alpha" : "1.000" } } }
  ],
  "info" : { "version" : 1, "author" : "xcode" }
}
"""
NAMED_COLOUR = f"""        <namedColor name="LaunchGround">
            <color {IVORY} alpha="1" colorSpace="custom" customColorSpace="sRGB"/>
        </namedColor>
"""
IMAGE, VIEW, SAFE = "993-d8-iHn", "Ze5-6b-2t3", "Bcu-3y-fUS"   # the template's ids
# Fixed sizes, nothing relative: the system renders a launch screen once,
# headless, after the install, and there the safe-area guide the first
# attempt measured against was empty, so the image got no width and his
# phone showed the ivory alone (19 Oct) where the simulator, rendering live,
# showed the drawing. 320 points square holds the drawing at about 180.
SIDE = 320
CONSTRAINTS = f"""<constraints>
                            <constraint firstItem="{IMAGE}" firstAttribute="centerX" secondItem="{VIEW}" secondAttribute="centerX" id="msX-ce-001"/>
                            <constraint firstItem="{IMAGE}" firstAttribute="centerY" secondItem="{VIEW}" secondAttribute="centerY" id="msY-ce-002"/>
                        </constraints>"""
OWN = f"""<constraints>
                                    <constraint firstAttribute="width" constant="{SIDE}" id="msW-fx-004"/>
                                    <constraint firstAttribute="height" constant="{SIDE}" id="msH-fx-005"/>
                                </constraints>
                            </imageView>"""


def patch_pbxproj() -> str:
    text = PBXPROJ.read_text(encoding="utf-8")
    if UNQUOTED not in text:
        return "build phase: already quoted"
    PBXPROJ.write_text(text.replace(UNQUOTED, QUOTED), encoding="utf-8")
    return "build phase: path quoted"


#: The launch image's name. Briefcase calls it "Splash"; under that name his
#: phone and the simulator went on showing Briefcase's bee although the
#: catalogue held the drawing (19 Oct): iOS renders a launch screen once
#: after an install and keeps the picture by name, through a reinstall and a
#: restart. A new name is a new picture.
IMAGE_NAME = "Opening"
OLD_NAMES = ("Splash", "LaunchDrawing", "LaunchBook", "LaunchMark", "LaunchTile")
#: The launch image's pixels at 1x, 2x and 3x. The layout shows it at most
#: 480 points wide, so Briefcase's 640/1280/1920 are more than the system's
#: launch-screen renderer needs: on his phone a 1920 px image left the
#: screen blank (19 Oct) where the simulator drew it.
SIZES = {"splash-640.png": 320, "splash-1280.png": 640, "splash-1920.png": 960}


def rename_image() -> str:
    new = ASSETS / f"{IMAGE_NAME}.imageset"
    # Briefcase's own set, when `briefcase update --update-resources` has put
    # it back, is the freshest; it replaces whatever earlier name is there.
    for old in OLD_NAMES:
        folder = ASSETS / f"{old}.imageset"
        if not folder.is_dir():
            continue
        if new.is_dir():
            shutil.rmtree(new)
        folder.rename(new)
        for stale in OLD_NAMES:
            shutil.rmtree(ASSETS / f"{stale}.imageset", ignore_errors=True)
        return f"launch image: {old} renamed {IMAGE_NAME}"
    return "launch image: already renamed" if new.is_dir() else "launch image: none found"


MANIFEST = """{
  "images" : [
    { "idiom" : "universal", "filename" : "splash-640.png", "scale" : "1x" },
    { "idiom" : "universal", "filename" : "splash-1280.png", "scale" : "2x" },
    { "idiom" : "universal", "filename" : "splash-1920.png", "scale" : "3x" }
  ],
  "info" : { "version" : 1, "author" : "xcode" }
}
"""


def manifest() -> str:
    """The image set's Contents.json: `briefcase update --update-resources`
    writes the three files into a bare Splash.imageset, and without the
    manifest the catalogue compiles without the image (the launch screen
    then shows its ground alone, 19 Oct)."""
    f = ASSETS / f"{IMAGE_NAME}.imageset" / "Contents.json"
    if f.is_file():
        return "launch image: manifest present"
    f.write_text(MANIFEST, encoding="utf-8")
    return "launch image: manifest written"


def shrink_image() -> str:
    """Each file of the image set to its size in SIZES, through macOS's sips
    (already that size: left alone)."""
    import subprocess
    folder = ASSETS / f"{IMAGE_NAME}.imageset"
    done = []
    for name, px in SIZES.items():
        f = folder / name
        if not f.is_file():
            continue
        width = subprocess.run(["sips", "-g", "pixelWidth", str(f)], capture_output=True, text=True).stdout
        if width.rstrip().endswith(f" {px}"):
            continue
        subprocess.run(["sips", "-Z", str(px), str(f)], check=True, capture_output=True)
        done.append(f"{name}→{px}")
    return "launch image: " + (", ".join(done) if done else "sizes as they should be")


def patch_storyboard() -> str:
    text = STORYBOARD.read_text(encoding="utf-8")
    for old in OLD_NAMES:
        text = text.replace(f'image="{old}"', f'image="{IMAGE_NAME}"').replace(f'<image name="{old}"', f'<image name="{IMAGE_NAME}"')
    text = re.sub(r'<color key="backgroundColor" (red="[^"]*" green="[^"]*" blue="[^"]*" alpha="1" '
                  r'colorSpace="custom" customColorSpace="sRGB"|name="LaunchGround")/>',
                  '<color key="backgroundColor" name="LaunchGround"/>', text, count=1)
    if "<namedColor" not in text:
        text = text.replace("    <resources>\n", "    <resources>\n" + NAMED_COLOUR, 1)
    # Every constraint block goes (the template's, or an earlier run's), and
    # the two of this script come back: run again, the result is the same.
    text = re.sub(r"\s*<constraints>.*?</constraints>", "", text, flags=re.S)
    text, k = re.subn(r"\s*</imageView>", "\n                                " + OWN, text, count=1)
    text, n = re.subn(r'(<viewLayoutGuide key="safeArea"[^>]*/>)', r"\1\n                        " + CONSTRAINTS, text, count=1)
    if n != 1 or k != 1:
        raise SystemExit("launch screen: the storyboard is not the one this script knows")
    STORYBOARD.write_text(text, encoding="utf-8")
    return "launch screen: drawing centred on ivory"


PLIST = XCODE / "MedSearch" / "MedSearch-Info.plist"


def launch_keys() -> str:
    """The ground's colour set, and the Info.plist naming the storyboard and
    nothing else: a UILaunchScreen dictionary left from an experiment would
    take over on a phone."""
    import plistlib
    colours = ASSETS / "LaunchGround.colorset"
    colours.mkdir(exist_ok=True)
    (colours / "Contents.json").write_text(COLORSET, encoding="utf-8")
    with PLIST.open("rb") as fh:
        plist = plistlib.load(fh)
    if "UILaunchScreen" not in plist and plist.get("UILaunchStoryboardName") == "Launch Screen":
        return "launch screen: the storyboard"
    plist.pop("UILaunchScreen", None)
    plist["UILaunchStoryboardName"] = "Launch Screen"
    with PLIST.open("wb") as fh:
        plistlib.dump(plist, fh)
    return "launch screen: the storyboard, UILaunchScreen removed"


def bundle_id_from_build_setting() -> str:
    """CFBundleIdentifier as $(PRODUCT_BUNDLE_IDENTIFIER), as Xcode's own
    templates have it, not the id written out: a build signed by another
    team (build-for-my-iphone.sh) gives PRODUCT_BUNDLE_IDENTIFIER on the
    command line, since no two teams may register one id, and the app's
    Info.plist must then say the same."""
    import plistlib
    with PLIST.open("rb") as fh:
        plist = plistlib.load(fh)
    if plist.get("CFBundleIdentifier") == "$(PRODUCT_BUNDLE_IDENTIFIER)":
        return "bundle id: from the build setting"
    plist["CFBundleIdentifier"] = "$(PRODUCT_BUNDLE_IDENTIFIER)"
    with PLIST.open("wb") as fh:
        plistlib.dump(plist, fh)
    return "bundle id: now from the build setting"


def main() -> None:
    if not XCODE.is_dir():
        raise SystemExit(f"no Xcode project at {XCODE}: run `briefcase create iOS` first")
    print(patch_pbxproj())
    print(rename_image())
    print(manifest())
    print(shrink_image())
    print(patch_storyboard())
    print(launch_keys())
    print(bundle_id_from_build_setting())


if __name__ == "__main__":
    main()

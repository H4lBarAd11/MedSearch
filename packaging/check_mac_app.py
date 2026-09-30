# MedSearch — check that a built MedSearch.app runs on every Mac it is for.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""Every program and library inside the app must hold code for each kind of Mac
(Intel and Apple silicon) and ask for no newer macOS than the oldest one served:
the neurosurgery iMac is an Intel Mac on macOS 12. One file that does not is
enough for the app to fail there, and nothing else would notice before it does.

    python packaging/check_mac_app.py dist/MedSearch.app --archs x86_64 arm64 --min-macos 12.0

Prints each file that falls short and exits 1; exits 0 when all of them pass.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# The first four bytes of a Mach-O file, thin or universal, in either order.
_MAGIC = {bytes.fromhex(m) for m in ("feedface", "cefaedfe", "feedfacf", "cffaedfe",
                                     "cafebabe", "bebafeca", "cafebabf", "bfbafeca")}


def is_macho(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(4) in _MAGIC
    except OSError:
        return False


def version(text: str) -> tuple:
    return tuple(int(x) for x in text.split("."))


def minimum_macos(otool_output: str):
    """The macOS a slice asks for, from `otool -l`: LC_BUILD_VERSION's minos,
    or the older LC_VERSION_MIN_MACOSX's version. None if it names neither."""
    m = re.search(r"cmd LC_BUILD_VERSION\b.*?\n\s*minos (\S+)", otool_output, re.S) \
        or re.search(r"cmd LC_VERSION_MIN_MACOSX\b.*?\n\s*version (\S+)", otool_output, re.S)
    return m.group(1) if m else None


def problems(app: Path, archs, min_macos: str) -> list[str]:
    out = []
    for f in sorted(p for p in app.rglob("*") if p.is_file() and not p.is_symlink()):
        if not is_macho(f):
            continue
        rel = f.relative_to(app)
        has = subprocess.run(["lipo", "-archs", str(f)], capture_output=True, text=True).stdout.split()
        for arch in archs:
            if arch not in has:
                out.append(f"{rel}: no {arch} code (has {' '.join(has) or 'none'})")
                continue
            listing = subprocess.run(["otool", "-arch", arch, "-l", str(f)],
                                     capture_output=True, text=True).stdout
            needs = minimum_macos(listing)
            if needs and version(needs) > version(min_macos):
                out.append(f"{rel} ({arch}): needs macOS {needs}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("app", type=Path)
    ap.add_argument("--archs", nargs="+", default=["x86_64", "arm64"])
    ap.add_argument("--min-macos", default="12.0")
    args = ap.parse_args(argv)
    found = problems(args.app, args.archs, args.min_macos)
    for line in found:
        print(line)
    print(f"{'FAIL' if found else 'OK'}: {args.app} for {' and '.join(args.archs)}, "
          f"macOS {args.min_macos} and later")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

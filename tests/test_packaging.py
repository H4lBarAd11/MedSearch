"""What the Release build checks before it publishes (packaging/, .github/).

check_mac_app.py stands between a build and the iMac, an Intel Mac on macOS 12:
it must notice a part that lacks Intel code or asks for a newer macOS.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packaging"))
import check_mac_app as C  # noqa: E402

BUILD_VERSION = """Load command 9
      cmd LC_BUILD_VERSION
  cmdsize 32
 platform 1
    minos 11.0
      sdk 14.0
"""
VERSION_MIN = """Load command 8
      cmd LC_VERSION_MIN_MACOSX
  cmdsize 16
  version 10.9
      sdk 10.14
"""


def test_the_macos_a_part_asks_for_is_read_from_either_load_command():
    assert C.minimum_macos(BUILD_VERSION) == "11.0"
    assert C.minimum_macos(VERSION_MIN) == "10.9"
    assert C.minimum_macos("cmd LC_SEGMENT_64\n") is None


def test_versions_compare_as_numbers():
    assert C.version("12.0") < C.version("12.10") and C.version("26.0") > C.version("12.0")
    assert C.version("9.0") < C.version("12.0")                # not as text: "9" > "1"


def test_only_programs_and_libraries_are_looked_at(tmp_path):
    (tmp_path / "text").write_text("hello")
    (tmp_path / "thin").write_bytes(bytes.fromhex("cffaedfe") + b"\0" * 28)
    (tmp_path / "fat").write_bytes(bytes.fromhex("cafebabe") + b"\0" * 28)
    assert [C.is_macho(tmp_path / n) for n in ("text", "thin", "fat")] == [False, True, True]


@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("lipo"), reason="the Mac's tools")
def test_a_part_without_intel_code_or_for_a_newer_macos_fails_the_check(tmp_path):
    """A real single-kind program: this Mac's own Python, as a Homebrew build is
    Apple silicon only and made for the macOS it was built on."""
    app = tmp_path / "MedSearch.app" / "Contents" / "MacOS"
    app.mkdir(parents=True)
    exe = Path(sys.executable).resolve()
    shutil.copy(exe, app / "MedSearch")
    import subprocess
    has = subprocess.run(["lipo", "-archs", str(exe)], capture_output=True, text=True).stdout.split()
    found = C.problems(tmp_path / "MedSearch.app", ["x86_64", "arm64"], "10.9")
    if "x86_64" not in has:
        assert any("no x86_64 code" in p for p in found)
    assert any("needs macOS" in p for p in found)              # nothing today runs on 10.9
    assert C.main([str(tmp_path / "MedSearch.app"), "--archs", *has, "--min-macos", "99.0"]) == 0


def test_the_release_waits_for_both_systems_and_publishes_both_installers():
    w = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "paths: [VERSION]" in w                              # a VERSION bump releases (his choice)
    assert "needs: [mac, windows]" in w
    assert 'MedSearch-$V-mac.dmg" "dist/MedSearch-$V-Setup.exe"' in w
    assert "check_mac_app.py dist/MedSearch.app --archs x86_64 arm64 --min-macos 12.0" in w
    assert "MEDSEARCH_TARGET_ARCH: universal2" in w

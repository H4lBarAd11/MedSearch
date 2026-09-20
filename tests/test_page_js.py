"""The page's own logic is tested in Node (tests/js), and run from here so that
one `pytest` covers the whole application. Skipped where Node isn't installed;
those tests can also be run on their own:

    node --test tests/js/*.test.js
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_pages_own_tests_pass():
    files = sorted(str(f) for f in (ROOT / "tests" / "js").glob("*.test.js"))
    assert files, "no browser-side tests found"
    r = subprocess.run([NODE, "--test", *files], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]

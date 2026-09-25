"""
Test setup. app.py reads ~/.medsearch at import time, so HOME is pointed at a
throwaway folder BEFORE app is imported, and removed when the run ends: the
suite never reads or writes the real configuration, history or cache. Nothing
here touches the network — every test that would call an outside service
replaces that call with a fake.
"""
import atexit
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_HOME = tempfile.mkdtemp(prefix="medsearch-tests-")
atexit.register(shutil.rmtree, _HOME, ignore_errors=True)
os.environ["HOME"] = _HOME
# The suite never touches the real Keychain: the keys-in-the-Keychain path is
# exercised with a fake store instead (test_routes.py).
os.environ["MEDSEARCH_KEYCHAIN"] = "0"
for var in ("ANTHROPIC_API_KEY", "NCBI_API_KEY", "SCOPUS_API_KEY", "WOS_API_KEY", "UNPAYWALL_EMAIL"):
    os.environ.pop(var, None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
import app as A  # noqa: E402

BASE = "http://127.0.0.1:5050"


@pytest.fixture
def client():
    return A.app.test_client()


@pytest.fixture
def auth():
    return {"X-MedSearch-Token": A.APP_TOKEN}


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Every test starts from an empty session and default config, and no
    test can reach the network by accident."""
    A.SESSION.update({"articles": [], "query": "", "history": [],
                      "last_synthesis": "", "offsets": {}})
    A.CONFIG.clear()
    A.CONFIG.update(dict(A.DEFAULTS))
    A._DOI_CACHE.clear()

    def no_network(*a, **k):
        raise AssertionError("test tried to reach the network")
    monkeypatch.setattr(A.urllib.request, "urlopen", no_network)
    yield


def sse_events(response):
    """The JSON events of a server-sent-events response, in order."""
    out = []
    for block in response.get_data(as_text=True).split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            out.append(json.loads(block[5:]))
    return out


def article(**kw):
    """A result shaped like the search functions produce."""
    a = A._article(**{"title": "A title", "source": "PubMed", **kw})
    if a["access_kind"] is None:
        a["access_kind"], a["access_link"] = "none", None
    return a

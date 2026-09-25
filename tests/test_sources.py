"""The databases ticked in the top bar are the ones MedSearch starts with."""
import json
import re
from pathlib import Path

import app as A
from conftest import BASE

ROOT = Path(__file__).resolve().parent.parent


def _checked(client, auth):
    html = client.get("/", headers=auth, base_url=BASE).get_data(as_text=True)
    return re.findall(r'class="db-item checked" data-db="([a-z]+)"', html)


def _tick(client, auth, sources):
    return client.post("/sources", json={"sources": sources}, headers=auth, base_url=BASE)


def test_a_fresh_install_starts_on_pubmed(client, auth):
    assert _checked(client, auth) == ["pubmed"]


def test_the_ticks_are_saved_and_come_back_at_the_next_start(client, auth):
    r = _tick(client, auth, ["guidelines", "cochrane", "pubmed"])
    assert r.status_code == 200 and r.json["sources"] == ["cochrane", "guidelines", "pubmed"]
    assert json.loads(A.CONFIG_FILE.read_text())["search_sources"] == \
        ["cochrane", "guidelines", "pubmed"]
    assert _checked(client, auth) == ["pubmed", "cochrane", "guidelines"]


def test_unknown_names_are_dropped(client, auth):
    r = _tick(client, auth, ["cochrane", "google", "<script>", 3])
    assert r.json["sources"] == ["cochrane"]


def test_nothing_ticked_starts_on_pubmed_rather_than_nothing(client, auth):
    _tick(client, auth, [])
    assert A.CONFIG["search_sources"] == []
    assert _checked(client, auth) == ["pubmed"]


def test_a_database_without_its_key_is_not_ticked_at_start(client, auth):
    _tick(client, auth, ["pubmed", "scopus", "wos"])
    assert _checked(client, auth) == ["pubmed"]
    A.CONFIG["scopus_api_key"] = "abcd1234"
    assert _checked(client, auth) == ["pubmed", "scopus"]


def test_a_malformed_request_is_refused(client, auth):
    r = client.post("/sources", json={"sources": "pubmed"}, headers=auth, base_url=BASE)
    assert r.status_code == 400
    assert client.post("/sources", json={"sources": ["pubmed"]}, base_url=BASE).status_code == 403


def test_only_your_own_ticks_are_saved():
    """A quick search from the menu bar or a saved search run again changes the
    ticks for that search only: just the panel's two clicks save them."""
    js = (ROOT / "static" / "js" / "app.js").read_text()
    calls = [m.start() for m in re.finditer(r"\brememberSources\(\);", js)]
    assert len(calls) == 2
    for name in ("function runSearchWithSource", "function runSaved"):
        start = js.find(name)
        if start < 0:
            continue
        end = js.find("\nfunction ", start + 1)
        assert "rememberSources" not in js[start:end]


def test_the_settings_icon_is_a_gear_not_a_sun():
    html = (ROOT / "templates" / "index.html").read_text()
    sym = re.search(r'<symbol id="i-settings".*?</symbol>', html).group(0)
    assert sym.count(" Z") == 1 and "<circle" in sym      # one toothed outline round a hub
    assert "M12 3v2.5" not in sym                         # the sun's rays

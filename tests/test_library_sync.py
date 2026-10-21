# The library setup travels with the keys through iCloud Keychain (20 Oct):
# the proxies, the active library and the library resources, as one item,
# the newer of the two devices' winning. These run against a fake store;
# the suite's HOME is a temporary folder and the real Keychain is off.
import json

import pytest

import app as A
import secrets_store
import signins as S
from conftest import BASE

ASUIT = {"id": "asuit", "label": "ASUIT", "url": "https://ezproxy.asuit.it/login?url="}
FBK = {"id": "fbk", "label": "FBK", "url": "https://ezproxy.fbk.eu/login?url="}


@pytest.fixture
def store(monkeypatch):
    """A Keychain that syncs, held in a dict."""
    held = {}
    monkeypatch.setattr(secrets_store, "syncs", lambda: True)
    monkeypatch.setattr(secrets_store, "available", lambda: True)
    monkeypatch.setattr(secrets_store, "get", lambda name: held.get(name, ""))
    monkeypatch.setattr(secrets_store, "read", lambda name: (held.get(name, ""), True))
    monkeypatch.setattr(secrets_store, "set", lambda name, value: held.__setitem__(name, value) or True)
    monkeypatch.setattr(S, "forget_later", lambda domains, store=None: None)
    A._LIBRARY_SETUP.update({"sent": None, "known": None})
    yield held
    A._LIBRARY_SETUP.update({"sent": None, "known": None})


def _item(held):
    return json.loads(held["library_setup"])


def test_the_other_devices_newer_setup_comes_down_with_the_page(client, store):
    A.CONFIG["library_setup_saved"] = 100
    store["library_setup"] = json.dumps({"saved": 200, "institution_proxies": [ASUIT, FBK],
                                         "library_resources": {"on": [], "own": []}})
    client.get("/", base_url=BASE)
    assert [p["label"] for p in A.CONFIG["institution_proxies"]] == ["ASUIT", "FBK"]
    assert A.CONFIG["library_setup_saved"] == 200
    assert json.loads(A.CONFIG_FILE.read_text())["library_setup_saved"] == 200


def test_the_first_meeting_merges_and_loses_nothing(client, store):
    # The finding: the phone (UniTN only) synced first, then the Mac (all
    # three, never stamped) took the phone's list and lost ASUIT and FBK.
    unitn = {"id": "unitn", "label": "UniTN", "url": "https://ezp.biblio.unitn.it"}
    store["library_setup"] = json.dumps({"saved": 500, "institution_proxies": [unitn],
                                         "library_resources": {"on": ["clinicalkey"], "own": []}})
    A.CONFIG["institution_proxies"] = [dict(unitn), ASUIT, FBK]
    client.get("/", base_url=BASE)
    assert [p["label"] for p in A.CONFIG["institution_proxies"]] == ["UniTN", "ASUIT", "FBK"]
    assert [p["label"] for p in _item(store)["institution_proxies"]] == ["UniTN", "ASUIT", "FBK"]
    assert A.CONFIG["library_setup_saved"] > 500


def test_a_pull_keeps_remember_sign_in_and_deletes_no_sign_in(client, store, monkeypatch):
    asked = []
    monkeypatch.setattr(S, "forget_later", lambda domains, store=None: asked.append(domains))
    unitn = {"id": "unitn", "label": "UniTN", "url": "https://ezp.biblio.unitn.it"}
    A.CONFIG["institution_proxies"] = [dict(unitn, remember_signin=True)]
    A.CONFIG["library_setup_saved"] = 100
    store["library_setup"] = json.dumps({"saved": 200, "institution_proxies": [unitn, ASUIT],
                                         "library_resources": {"on": [], "own": []}})
    client.get("/", base_url=BASE)
    assert A.CONFIG["institution_proxies"][0].get("remember_signin") is True
    assert asked == []
    assert "remember_signin" not in store["library_setup"]


def test_the_active_library_stays_the_same_library(client, store):
    custom_a = {"label": "A", "url": "https://a.example.org"}
    custom_b = {"label": "B", "url": "https://b.example.org"}
    A.CONFIG["institution_proxies"] = [custom_a, custom_b]
    A.CONFIG["active_proxy"] = 4                     # B: after the three predefined and A
    A.CONFIG["library_setup_saved"] = 100
    store["library_setup"] = json.dumps({"saved": 200, "institution_proxies": [custom_b],
                                         "library_resources": {"on": [], "own": []}})
    client.get("/", base_url=BASE)
    assert A.CONFIG["active_proxy"] == 3             # still B, now right after the three


def test_a_keychain_that_does_not_answer_changes_nothing(client, store, monkeypatch):
    monkeypatch.setattr(secrets_store, "read", lambda name: ("", False))
    A.CONFIG["institution_proxies"] = [ASUIT]
    A.CONFIG["library_setup_saved"] = 100
    client.get("/", base_url=BASE)
    assert "library_setup" not in store
    assert A.CONFIG["library_setup_saved"] == 100


def test_one_unreadable_entry_does_not_throw_the_setup_away(client, store):
    A.CONFIG["library_setup_saved"] = 100
    store["library_setup"] = json.dumps({"saved": 200, "institution_proxies": [
        ASUIT, {"label": "Bad", "url": "https://x.org", "openurl": "not an address"}],
        "library_resources": {"on": [], "own": [{"name": "Odd", "url": "ftp://x"}]}})
    client.get("/", base_url=BASE)
    assert [p["label"] for p in A.CONFIG["institution_proxies"]] == ["ASUIT"]


def test_this_devices_setup_goes_up_when_the_keychain_is_empty(client, store):
    A.CONFIG["institution_proxies"] = [ASUIT]
    client.get("/", base_url=BASE)
    item = _item(store)
    assert [p["label"] for p in item["institution_proxies"]] == ["ASUIT"]
    assert item["saved"] > 0 and A.CONFIG["library_setup_saved"] == item["saved"]


def test_a_fresh_device_beside_an_empty_keychain_sends_nothing(client, store):
    client.get("/", base_url=BASE)
    assert "library_setup" not in store
    assert not A.CONFIG.get("library_setup_saved")


def test_an_older_item_never_overwrites_this_device(client, store):
    store["library_setup"] = json.dumps({"saved": 100, "institution_proxies": [FBK],
                                         "library_resources": {"on": [], "own": []}})
    A.CONFIG["institution_proxies"] = [ASUIT]
    A.CONFIG["library_setup_saved"] = 200
    client.get("/", base_url=BASE)
    assert [p["label"] for p in A.CONFIG["institution_proxies"]] == ["ASUIT"]
    assert [p["label"] for p in _item(store)["institution_proxies"]] == ["ASUIT"]
    assert _item(store)["saved"] == 200


def test_a_change_saved_in_settings_goes_up_with_a_fresh_stamp(client, auth, store):
    A.CONFIG["library_setup_saved"] = 100
    store["library_setup"] = json.dumps({"saved": 200, "institution_proxies": [ASUIT],
                                         "library_resources": {"on": [], "own": []}})
    client.get("/", base_url=BASE)
    r = client.post("/settings", json={"institution_proxies": [ASUIT, FBK], "active_proxy": 1},
                    headers=auth, base_url=BASE)
    assert r.get_json()["ok"] is True
    item = _item(store)
    assert [p["label"] for p in item["institution_proxies"]] == ["ASUIT", "FBK"]
    assert "active_proxy" not in item and item["saved"] > 200


def test_saving_something_else_keeps_the_stamp(client, auth, store):
    A.CONFIG["institution_proxies"] = [ASUIT]
    client.get("/", base_url=BASE)
    stamp = _item(store)["saved"]
    client.post("/settings", json={"ai_monthly_cap": 3}, headers=auth, base_url=BASE)
    assert _item(store)["saved"] == stamp


def test_only_the_library_setup_travels(client, auth, store):
    A.CONFIG["anthropic_api_key"] = "sk-test"
    A.CONFIG["institution_proxies"] = [ASUIT]
    A.SESSION["history"].append({"query": "private"})
    client.get("/", base_url=BASE)
    assert set(_item(store)) == {"saved", "institution_proxies", "library_resources"}
    assert "sk-test" not in store["library_setup"] and "private" not in store["library_setup"]


def test_a_broken_item_is_ignored(client, store):
    store["library_setup"] = "not json"
    A.CONFIG["institution_proxies"] = [ASUIT]
    client.get("/", base_url=BASE)
    assert [p["label"] for p in A.CONFIG["institution_proxies"]] == ["ASUIT"]


def test_a_login_keychain_syncs_nothing(client, monkeypatch):
    written = []
    monkeypatch.setattr(secrets_store, "set", lambda name, value: written.append(name) or True)
    A.CONFIG["institution_proxies"] = [ASUIT]
    client.get("/", base_url=BASE)
    assert "library_setup" not in written

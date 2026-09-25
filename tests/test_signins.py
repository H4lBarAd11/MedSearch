"""Library sign-ins: which pages may have one, when one is kept or deleted, and
what Settings saves. None of this touches the real Keychain: the store is a
fake, and the real web page part runs in tests/webkit/signins_page.py.
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import app as A
import signins as S
from conftest import BASE

ROOT = Path(__file__).resolve().parent.parent
CASES = json.loads((ROOT / "tests" / "signin_domains.json").read_text())

UNITN = {"id": "unitn", "label": "UniTN", "url": "https://ezp.biblio.unitn.it",
         "remember_signin": True}
FBK = {"id": "fbk", "label": "FBK", "url": "https://ezproxy.fbk.eu/login?url=",
       "remember_signin": True}


class Store:
    def __init__(self, items=None):
        self.items, self.saves, self.forgotten = dict(items or {}), 0, []

    def available(self):
        return True

    def load(self, domain):
        return self.items.get(domain)

    def save(self, domain, user, password, label):
        self.saves += 1
        self.items[domain] = (user, password)
        return True

    def forget(self, domain):
        self.forgotten.append(domain)
        self.items.pop(domain, None)
        return True


# ── the domain ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,domain", CASES)
def test_the_sign_in_domain_comes_from_the_proxy_address(url, domain):
    assert S.domain_of(url) == domain


@pytest.mark.parametrize("host,ok", [
    ("idp.unitn.it", True), ("unitn.it", True), ("IDP.UNITN.IT", True),
    ("idp.unitn.it.example.org", False),       # named to look like it
    ("notunitn.it", False), ("unitn.it.", True), ("", False),
])
def test_only_the_domain_and_what_is_inside_it_are_covered(host, ok):
    assert S.covers(host, "unitn.it") is ok


def test_an_empty_domain_covers_nothing():
    assert S.covers("anything.org", "") is False


# ── which libraries ──────────────────────────────────────────────────────────

def test_only_a_ticked_library_is_remembered():
    libs = [UNITN, dict(FBK, remember_signin=False),
            {"label": "No box", "url": "https://ezp.example.org"},
            {"label": "Truthy but not yes", "url": "https://ezp.other.org",
             "remember_signin": "yes"},
            {"label": "No address", "url": "", "remember_signin": True},
            "not a dict"]
    assert S.remembered(libs) == [("unitn.it", "UniTN")]


def test_the_library_that_owns_a_host_is_found():
    assert S.match("idp.unitn.it", [FBK, UNITN]) == ("unitn.it", "UniTN")
    assert S.match("idp.fbk.eu", [FBK, UNITN]) == ("fbk.eu", "FBK")
    assert S.match("www.nejm.org", [FBK, UNITN]) is None


def test_unticked_removed_or_moved_libraries_lose_their_sign_in():
    moved = dict(FBK, url="https://ezp.elsewhere.org")
    assert S.dropped([UNITN, FBK], [UNITN]) == ["fbk.eu"]                    # removed
    assert S.dropped([UNITN, FBK], [UNITN, dict(FBK, remember_signin=False)]) == ["fbk.eu"]
    assert S.dropped([UNITN, FBK], [UNITN, moved]) == ["fbk.eu"]
    assert S.dropped([UNITN, FBK], [FBK, UNITN]) == []                       # only reordered


def test_a_domain_another_ticked_library_still_uses_is_kept():
    twin = {"label": "UniTN again", "url": "https://other.unitn.it", "remember_signin": True}
    assert S.dropped([UNITN, twin], [twin]) == []


# ── what a sent form may leave behind ────────────────────────────────────────

def _body(u="name.surname@unitn.it", p="pw"):
    return {"medsearchSignIn": {"u": u, "p": p}}


def test_a_sign_in_sent_from_the_librarys_login_page_is_taken():
    assert S.take(_body(), True, "https", "idp.unitn.it", [UNITN]) == \
        ("unitn.it", "UniTN", "name.surname@unitn.it", "pw")


@pytest.mark.parametrize("main,protocol,host", [
    (False, "https", "idp.unitn.it"),                  # a frame inside the page
    (True, "http", "idp.unitn.it"),                    # not encrypted
    (True, "https", "idp.unitn.it.example.org"),       # somebody else's site
    (True, "https", "www.nejm.org"),                   # a publisher's own login
])
def test_a_sign_in_from_anywhere_else_is_not_taken(main, protocol, host):
    assert S.take(_body(), main, protocol, host, [UNITN]) is None


@pytest.mark.parametrize("body", [
    _body(u=""), _body(u="   "), _body(p=""), {"medsearchSignIn": "text"}, {}, "print", None,
])
def test_an_incomplete_or_foreign_message_is_not_taken(body):
    assert S.take(body, True, "https", "idp.unitn.it", [UNITN]) is None


def test_an_unticked_library_takes_nothing():
    assert S.take(_body(), True, "https", "idp.unitn.it",
                  [dict(UNITN, remember_signin=False)]) is None


# ── the store ────────────────────────────────────────────────────────────────

def test_a_new_sign_in_is_stored_and_an_unchanged_one_is_not_rewritten():
    store = Store()
    assert S.keep("unitn.it", "UniTN", "u@unitn.it", "one", store) is True
    assert S.keep("unitn.it", "UniTN", "u@unitn.it", "one", store) is False
    assert store.saves == 1
    assert S.keep("unitn.it", "UniTN", "u@unitn.it", "two", store) is True
    assert store.items["unitn.it"] == ("u@unitn.it", "two")


def test_forgetting_runs_off_the_requests_thread():
    started = threading.Event()

    class Slow(Store):
        def forget(self, domain):
            started.wait(2)
            return super().forget(domain)
    store = Slow({"fbk.eu": ("u", "p")})
    S.forget_later(["fbk.eu"], store)                  # returns at once, though forget waits
    assert store.forgotten == []
    started.set()
    for _ in range(200):
        if store.forgotten:
            break
        time.sleep(0.01)
    assert store.forgotten == ["fbk.eu"]


def test_the_suite_never_reaches_the_real_keychain():
    assert S.STORE.available() is False
    assert S.STORE.load("unitn.it") is None
    assert S.STORE.save("unitn.it", "u", "p", "UniTN") is False


def test_the_fill_script_cannot_be_broken_out_of():
    js = S.fill_script('a"b', "x'); alert(1); ('\\\n</script>", "unitn.it", True)
    args = js[js.rindex("})(") + 3:-3]
    # One JSON array, one JSON string, one boolean: the values are data.
    arr, rest = json.JSONDecoder().raw_decode(args)
    assert arr == ['a"b', "x'); alert(1); ('\\\n</script>"]
    assert rest < len(args) and args[rest:].strip() == ', "unitn.it", true'


# ── Settings ─────────────────────────────────────────────────────────────────

def _save(client, auth, libraries):
    return client.post("/settings", json={"institution_proxies": libraries},
                       headers=auth, base_url=BASE)


def test_settings_keeps_the_box_and_only_an_explicit_yes(client, auth, monkeypatch):
    monkeypatch.setattr(S, "forget_later", lambda domains, store=None: None)
    _save(client, auth, [UNITN, dict(FBK, remember_signin="true"),
                         {"label": "X", "url": "https://ezp.x.org", "remember_signin": 1}])
    saved = client.get("/settings", headers=auth, base_url=BASE).json["institution_proxies"]
    assert [p.get("remember_signin") for p in saved] == [True, None, None]
    on_disk = json.loads(A.CONFIG_FILE.read_text())["institution_proxies"]
    assert on_disk[0]["remember_signin"] is True


def test_unticking_in_settings_deletes_the_saved_sign_in(client, auth, monkeypatch):
    asked = []
    monkeypatch.setattr(S, "forget_later", lambda domains, store=None: asked.append(domains))
    _save(client, auth, [UNITN, FBK])
    _save(client, auth, [dict(UNITN, remember_signin=False), FBK])
    _save(client, auth, [FBK])
    assert asked == [[], ["unitn.it"], []]


def test_saving_other_settings_deletes_nothing(client, auth, monkeypatch):
    asked = []
    monkeypatch.setattr(S, "forget_later", lambda domains, store=None: asked.append(domains))
    _save(client, auth, [UNITN])
    client.post("/settings", json={"ai_monthly_cap": 3}, headers=auth, base_url=BASE)
    assert asked == [[], []]


# ── a real page ──────────────────────────────────────────────────────────────

def _webkit():
    if sys.platform != "darwin":
        return False
    try:
        import WebKit  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _webkit(), reason="needs macOS WebKit")
def test_a_real_login_page_is_filled_and_its_sign_in_kept():
    r = subprocess.run([sys.executable, "-B", str(ROOT / "tests" / "webkit" / "signins_page.py")],
                       capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "ALL PASS" in r.stdout

"""The Keychain itself: what MedSearch asks /usr/bin/security to do, and
Credential Manager, its Windows counterpart (wincred.py).

Every one of these runs against a fake `security` or a fake advapi32, never
the real Keychain or Credential Manager.
What they are really testing is how often macOS puts up its password dialog:
each write to a stored item costs the user one, so the calls that are NOT made
matter as much as the ones that are.
"""
import ctypes
import sys

import pytest

import secrets_store as S
import wincred as W

KEYS = ("anthropic_api_key", "pubmed_api_key", "scopus_api_key",
        "scopus_insttoken", "wos_api_key")


class FakeSecurity:
    """/usr/bin/security, as a dict — and a log of every call it was given."""
    def __init__(self, items=None):
        self.items, self.calls = dict(items or {}), []

    def run(self, argv, **kw):
        self.calls.append(argv)
        cmd, name = argv[1], argv[argv.index("-a") + 1]
        if cmd == "find-generic-password":
            if name not in self.items:
                return self._r(S._NO_SUCH_ITEM)
            return self._r(0, self.items[name] + "\n")
        if cmd == "add-generic-password":
            self.items[name] = argv[argv.index("-w") + 1]
            return self._r(0)
        if cmd == "delete-generic-password":
            if name not in self.items:
                return self._r(S._NO_SUCH_ITEM)
            del self.items[name]
            return self._r(0)
        raise AssertionError(f"unexpected security command: {cmd}")

    @staticmethod
    def _r(code, out=""):
        class R: pass
        R.returncode, R.stdout, R.stderr = code, out, ""
        return R

    def writes(self):
        return [a[1] for a in self.calls if a[1] != "find-generic-password"]


@pytest.fixture
def security(monkeypatch):
    """A Keychain that is present and working, holding four of the five keys."""
    fake = FakeSecurity({k: f"value-of-{k}" for k in KEYS[:4]})
    S._KNOWN.clear()
    monkeypatch.setattr(S, "_backend", lambda: "security")
    monkeypatch.setattr(S, "available", lambda: True)
    monkeypatch.setattr(S.subprocess, "run", fake.run)
    yield fake
    S._KNOWN.clear()


def test_saving_a_key_that_has_not_changed_asks_for_nothing(security):
    """The bug: turning the AI on saves the settings whole, which rewrote all
    five keys and put up the password dialog once per stored key."""
    for k in KEYS:                       # startup reads them
        S.get(k)
    security.calls.clear()
    for k in KEYS:                       # a save that changed only ai_enabled
        assert S.set(k, security.items.get(k, "")) is True
    assert security.calls == []


def test_a_key_that_really_changed_is_written(security):
    S.get("anthropic_api_key")
    security.calls.clear()
    assert S.set("anthropic_api_key", "sk-ant-new") is True
    assert security.writes() == ["add-generic-password"]
    assert security.items["anthropic_api_key"] == "sk-ant-new"
    # and the second save of the same value costs nothing
    security.calls.clear()
    S.set("anthropic_api_key", "sk-ant-new")
    assert security.calls == []


def test_a_key_that_was_never_there_is_not_deleted_again(security):
    assert S.get("wos_api_key") == ""     # the fifth key, unstored
    security.calls.clear()
    assert S.set("wos_api_key", "") is True
    assert S.delete("wos_api_key") is True
    assert security.calls == []


def test_removing_a_stored_key_still_removes_it(security):
    S.get("scopus_insttoken")
    security.calls.clear()
    assert S.set("scopus_insttoken", "") is True
    assert security.writes() == ["delete-generic-password"]
    assert "scopus_insttoken" not in security.items


def test_a_refusal_is_not_mistaken_for_an_empty_keychain(monkeypatch):
    """A locked keychain answers neither yes nor no. Remembering that as ""
    would skip the next write and quietly lose the key."""
    S._KNOWN.clear()
    monkeypatch.setattr(S, "_backend", lambda: "security")
    monkeypatch.setattr(S, "available", lambda: True)
    monkeypatch.setattr(S.subprocess, "run",
                        lambda argv, **kw: FakeSecurity._r(51))   # user cancelled
    assert S.get("anthropic_api_key") == ""
    assert S._KNOWN == {}
    fake = FakeSecurity()
    monkeypatch.setattr(S.subprocess, "run", fake.run)
    assert S.set("anthropic_api_key", "sk-ant-keepme") is True    # still attempted
    assert fake.items["anthropic_api_key"] == "sk-ant-keepme"
    S._KNOWN.clear()


# ── Windows: Credential Manager ──────────────────────────────────────────────
class FakeAdvapi:
    """advapi32's credential calls, over a dict, speaking the real structures:
    what reaches it went through wincred's own ctypes marshalling."""
    def __init__(self, items=None):
        self.items = dict(items or {})     # target -> (user, secret bytes, persist)
        self.calls, self.error, self.refuse = [], 0, False
        self._held = []                    # what a read handed out, kept alive

    def get_last_error(self):
        return self.error

    def CredReadW(self, target, kind, flags, found):
        self.calls.append(("read", target))
        if self.refuse:
            self.error = 5                 # ERROR_ACCESS_DENIED
            return False
        if target not in self.items:
            self.error = W._NOT_FOUND
            return False
        user, data, _ = self.items[target]
        buf = (ctypes.c_ubyte * max(len(data), 1)).from_buffer_copy(data or b"\0")
        cred = W.CREDENTIAL(Type=kind, TargetName=target, UserName=user,
                            CredentialBlobSize=len(data),
                            CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
        self._held += [buf, cred]
        found._obj.contents = cred
        return True

    def CredWriteW(self, pcred, flags):
        c = pcred._obj
        self.calls.append(("write", c.TargetName))
        if self.refuse:
            self.error = 5
            return False
        data = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
        assert c.Type == W._GENERIC
        self.items[c.TargetName] = (c.UserName, data, c.Persist)
        return True

    def CredDeleteW(self, target, kind, flags):
        self.calls.append(("delete", target))
        if target not in self.items:
            self.error = W._NOT_FOUND
            return False
        del self.items[target]
        return True

    def CredFree(self, p):
        self.calls.append(("free", None))

    def writes(self):
        return [c for c in self.calls if c[0] in ("write", "delete")]


@pytest.fixture
def credman(monkeypatch):
    """Credential Manager, present and working, holding one key."""
    fake = FakeAdvapi({"MedSearch/pubmed_api_key": ("pubmed_api_key", b"ncbi-123", 2)})
    monkeypatch.setattr(W, "API", fake)
    monkeypatch.setattr(S, "_backend", lambda: "wincred")
    monkeypatch.setenv("MEDSEARCH_KEYCHAIN", "1")
    S._KNOWN.clear()
    yield fake
    S._KNOWN.clear()


def test_windows_keeps_each_key_as_its_own_credential(credman):
    assert S.available() is True
    assert S.get("pubmed_api_key") == "ncbi-123"
    assert S.set("anthropic_api_key", "sk-ant-päss") is True
    user, data, persist = credman.items["MedSearch/anthropic_api_key"]
    assert (user, data.decode("utf-8")) == ("anthropic_api_key", "sk-ant-päss")
    assert persist == W._LOCAL_MACHINE             # this PC only, never roaming
    S._KNOWN.clear()
    assert S.get("anthropic_api_key") == "sk-ant-päss"


def test_windows_frees_what_it_read(credman):
    S.get("pubmed_api_key")
    assert ("free", None) in credman.calls


def test_windows_tells_missing_from_refused(credman):
    assert S.get("wos_api_key") == ""
    assert S._KNOWN == {"wos_api_key": ""}            # an answer: nothing there
    S._KNOWN.clear()
    credman.refuse = True
    assert S.get("pubmed_api_key") == ""
    assert S._KNOWN == {}                              # a refusal teaches nothing


def test_windows_skips_writing_what_is_already_there(credman):
    S.get("pubmed_api_key")
    assert S.set("pubmed_api_key", "ncbi-123") is True
    assert credman.writes() == []


def test_windows_removes_a_key_and_treats_missing_as_removed(credman):
    assert S.set("pubmed_api_key", "") is True
    assert "MedSearch/pubmed_api_key" not in credman.items
    assert W.delete("MedSearch/never-there") is True


def test_windows_refuses_a_secret_too_large_to_keep(credman):
    assert W.write("MedSearch/x", "x", "k" * (W.MAX_SECRET + 1)) is False
    assert credman.writes() == []


def test_windows_is_off_when_the_suite_says_so(credman, monkeypatch):
    monkeypatch.setenv("MEDSEARCH_KEYCHAIN", "0")
    assert S.available() is False


@pytest.mark.skipif(sys.platform != "win32", reason="the real Credential Manager")
def test_the_real_credential_manager_round_trip(monkeypatch):
    """On Windows only (the release build runs it): the structures' real layout."""
    monkeypatch.setattr(W, "API", None)
    target = "MedSearch test/round-trip"
    try:
        assert W.write(target, "tester", "sécret") is True
        assert W.read(target) == (W.FOUND, "tester", "sécret")
    finally:
        assert W.delete(target) is True
    assert W.read(target)[0] == W.MISSING

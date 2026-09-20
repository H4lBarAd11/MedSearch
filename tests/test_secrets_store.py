"""The Keychain itself: what MedSearch asks /usr/bin/security to do.

Every one of these runs against a fake `security`, never the real Keychain.
What they are really testing is how often macOS puts up its password dialog:
each write to a stored item costs the user one, so the calls that are NOT made
matter as much as the ones that are.
"""
import pytest

import secrets_store as S

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

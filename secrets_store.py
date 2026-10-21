# MedSearch — where the API keys are kept.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""The API keys, in the macOS Keychain instead of a file.

WHY. The keys used to sit in ~/.medsearch/config.json as plain text. On a shared
department machine that is readable by anyone using the account, and the
Anthropic one spends money. The Keychain is the place macOS provides for this:
encrypted at rest, unlocked with the login, and visible in Keychain Access so a
user can see and revoke what the app holds.

HOW. Through /usr/bin/security, which every macOS has — no dependency, nothing
to build, and it works the same on Monterey as on the current release. Each key
is a generic password under the service "MedSearch", with the setting's own name
as the account, so Keychain Access lists them one by one.

NO PROMPT ON EVERY READ. The item is created with `-T /usr/bin/security`, which
trusts exactly that tool to read it back, so the app never has to ask again.

NO PROMPT ON A SAVE THAT CHANGES NOTHING. Writing an item macOS already holds
raises the login-password dialog, once per item — and MedSearch saves its
settings whole, so turning the AI on or off rewrote every key and asked four
or five times for values nobody had touched. This module therefore remembers
what the Keychain answered during this run and skips a write of the value that
is already there, which leaves the password asked only when a key really
changes. Only what /usr/bin/security itself reported is remembered; a key
edited in Keychain Access while MedSearch is open is the one case that goes
unnoticed, and restarting MedSearch settles it.

ICLOUD KEYCHAIN, WHEN THE BUILD IS SIGNED FOR IT (19 Oct). The iPhone app keeps
its keys as iCloud Keychain items (secitem.py), and a Mac build signed by the
same team with the keychain-access-groups entitlement (packaging/sign-mac.sh)
keeps them in the same place: the keys typed on one device appear on the
other. Such a build moves each key out of the login keychain the first time
it is asked for, and leaves the old item behind for a build that is not
signed (the public download is not; it goes on using the login keychain).

ON WINDOWS, CREDENTIAL MANAGER (wincred.py) takes the Keychain's place: one
credential per setting, "MedSearch/<setting>", under the same rules. It asks
for no password, so the saved writes cost nothing there; they are skipped all
the same, since the rules are one.

IF IT IS NOT AVAILABLE (neither of the two, or the store refuses), the caller
keeps the keys in the config file as before: MedSearch must still work, and the
file is the same place they already were.
"""
from __future__ import annotations

import os
import subprocess
import sys

import secitem
import wincred

SERVICE = secitem.SERVICE          # "MedSearch", or a test's own (secitem.py)
_SECURITY = "/usr/bin/security"
# security(1)'s exit code for "there is no such item", which is an answer about
# the Keychain's contents rather than a refusal to answer.
_NO_SUCH_ITEM = 44

_MISSING = object()   # "this run has not been told", which is not the same as ""

# name -> what the Keychain holds for it, as far as this run has been told.
# A name that is absent means "not known", which is never treated as empty.
_KNOWN: dict[str, str] = {}


_ENTITLED: bool | None = None   # the Mac's answer, asked once per run


def _entitled() -> bool:
    """Whether this Mac build may use the data-protection keychain, where
    iCloud Keychain's items live: only an app signed by a team with the
    keychain-access-groups entitlement may (packaging/sign-mac.sh does that
    with the developer's own team; the public download is unsigned). The
    process is asked for its own entitlement (secitem.entitled).
    MEDSEARCH_KEYCHAIN_SYNC=0 says no without asking."""
    global _ENTITLED
    if _ENTITLED is None:
        _ENTITLED = (os.environ.get("MEDSEARCH_KEYCHAIN_SYNC") != "0"
                     and secitem.available() and secitem.entitled())
        print("  keys: " + ("iCloud Keychain (signed by the team)" if _ENTITLED
                            else "the login keychain (not signed for iCloud Keychain)"))
    return _ENTITLED


def _backend() -> str:
    """Where the secrets go: "wincred" on Windows; "secitem" (the Keychain
    through Security.framework, each item marked for iCloud Keychain:
    secitem.py) on iOS and on a Mac whose build is signed for it; else
    "security" (the login keychain through /usr/bin/security) on the Mac."""
    if sys.platform == "win32":
        return "wincred"
    if sys.platform == "ios":
        return "secitem"
    if sys.platform == "darwin" and _entitled():
        return "secitem"
    return "security"


def available() -> bool:
    """False turns the whole thing off and leaves the config file in charge.
    MEDSEARCH_KEYCHAIN=0 is how the test suite stays out of the real Keychain
    (and the real Credential Manager)."""
    if os.environ.get("MEDSEARCH_KEYCHAIN") == "0":
        return False
    if _backend() == "wincred":
        return wincred.available()
    if _backend() == "secitem":
        return secitem.available()
    return sys.platform == "darwin" and os.path.exists(_SECURITY)


def syncs() -> bool:
    """Whether what is stored here reaches the person's other devices: only
    the iCloud Keychain items (secitem) do. The library setup travels that
    way too (app.py); on a login keychain or Credential Manager there would
    be no point, so it stays in the config file alone."""
    return available() and _backend() == "secitem"


def _target(name: str) -> str:
    return f"{SERVICE}/{name}"


def _read(name: str):
    """(value, known): known is False when the store refused to answer."""
    if _backend() == "wincred":
        status, _user, value = wincred.read(_target(name))
        if status == wincred.FOUND:
            return value.strip(), True
        return "", status == wincred.MISSING
    if _backend() == "secitem":
        status, value = secitem.read(name)
        if status == secitem.OK:
            return value.strip(), True
        if status == secitem.NOT_FOUND and sys.platform == "darwin":
            # A Mac newly signed for iCloud Keychain still has its keys in
            # the login keychain, where every earlier build put them: each
            # moves across the first time it is asked for. The old item
            # stays, so a build without the signature (the public download
            # taking this one's place) still finds its key.
            value, known = _read_security(name)
            if known and value:
                # Moved across; if the write fails the key stays where it
                # was and is still this key (it read as empty for the whole
                # run before: the sweep, 20 Oct).
                secitem.write(name, value)
            return value, known
        return "", status == secitem.NOT_FOUND
    return _read_security(name)


def _read_security(name: str):
    try:
        r = subprocess.run([_SECURITY, "find-generic-password", "-s", SERVICE,
                            "-a", name, "-w"],
                           capture_output=True, text=True, timeout=10)
    except Exception:
        return "", False
    if r.returncode == 0:
        return r.stdout.strip(), True
    # "No such item" is an answer about the Keychain's contents; any other
    # code is the Keychain refusing, which tells nothing.
    return "", r.returncode == _NO_SUCH_ITEM


def _write(name: str, value: str) -> bool:
    if _backend() == "wincred":
        return wincred.write(_target(name), name, value, "MedSearch API key")
    if _backend() == "secitem":
        return secitem.write(name, value) == secitem.OK
    try:
        r = subprocess.run([_SECURITY, "add-generic-password", "-s", SERVICE,
                            "-a", name, "-w", value, "-U",
                            "-T", _SECURITY,               # readable without a prompt
                            "-j", "MedSearch API key"],
                           capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    return r.returncode == 0


def _remove(name: str) -> bool:
    """True once the item is gone, whether or not it was there."""
    if _backend() == "wincred":
        return wincred.delete(_target(name))
    if _backend() == "secitem":
        gone = secitem.remove(name) == secitem.OK
        if gone and sys.platform == "darwin":
            # The login keychain's copy, left by the move to iCloud Keychain,
            # would otherwise come back at the next launch and sync to the
            # iPhone again (the sweep, 20 Oct).
            _remove_security(name)
        return gone
    return _remove_security(name)


def _remove_security(name: str) -> bool:
    try:
        r = subprocess.run([_SECURITY, "delete-generic-password", "-s", SERVICE, "-a", name],
                           capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    # "no such item" is the state the caller asked for anyway.
    return r.returncode in (0, _NO_SUCH_ITEM)


def get(name: str) -> str:
    """The stored secret, or "" if there is none (or the store said no)."""
    if not available():
        return ""
    value, known = _read(name)
    # A refusal teaches nothing, so nothing is remembered.
    if known:
        _KNOWN[name] = value
    return value


def read(name: str) -> tuple[str, bool]:
    """(value, known): known is False when the store refused to answer, which
    is not the same as having nothing (get() folds the two together)."""
    if not available():
        return "", False
    value, known = _read(name)
    if known:
        _KNOWN[name] = value
    return value, known


def set(name: str, value: str) -> bool:
    """Store (or replace) a secret. An empty value removes it instead."""
    if not available():
        return False
    if _KNOWN.get(name, _MISSING) == value:
        return True                 # already there; writing would cost a password
    if not value:
        # An empty value removes the key only when this run KNOWS what the
        # store holds: a read the store refused (a locked keychain at a
        # login start) left the setting empty, and the next ordinary save
        # deleted every key with it (the sweep, 20 Oct). Removing a key on
        # purpose goes through delete() (Settings' "clear").
        if name not in _KNOWN:
            return False
        return delete(name)
    if _write(name, value):
        _KNOWN[name] = value
        return True
    return False


def delete(name: str) -> bool:
    if not available():
        return False
    if _KNOWN.get(name, _MISSING) == "":
        return True                 # nothing there to remove
    if _remove(name):
        _KNOWN[name] = ""
        return True
    return False

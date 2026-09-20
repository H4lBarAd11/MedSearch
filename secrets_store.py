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

IF IT IS NOT AVAILABLE (not macOS, or the Keychain refuses), the caller keeps
the keys in the config file as before: MedSearch must still work, and the file
is the same place they already were.
"""
from __future__ import annotations

import os
import subprocess
import sys

SERVICE = "MedSearch"
_SECURITY = "/usr/bin/security"


def available() -> bool:
    """False turns the whole thing off and leaves the config file in charge.
    MEDSEARCH_KEYCHAIN=0 is how the test suite stays out of the real Keychain."""
    if os.environ.get("MEDSEARCH_KEYCHAIN") == "0":
        return False
    return sys.platform == "darwin" and os.path.exists(_SECURITY)


def get(name: str) -> str:
    """The stored secret, or "" if there is none (or the Keychain said no)."""
    if not available():
        return ""
    try:
        r = subprocess.run([_SECURITY, "find-generic-password", "-s", SERVICE,
                            "-a", name, "-w"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def set(name: str, value: str) -> bool:
    """Store (or replace) a secret. An empty value removes it instead."""
    if not available():
        return False
    if not value:
        return delete(name)
    try:
        r = subprocess.run([_SECURITY, "add-generic-password", "-s", SERVICE,
                            "-a", name, "-w", value, "-U",
                            "-T", _SECURITY,               # readable without a prompt
                            "-j", "MedSearch API key"],
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def delete(name: str) -> bool:
    if not available():
        return False
    try:
        r = subprocess.run([_SECURITY, "delete-generic-password", "-s", SERVICE, "-a", name],
                           capture_output=True, text=True, timeout=10)
        # 44 is "no such item", which is the state the caller asked for anyway.
        return r.returncode in (0, 44)
    except Exception:
        return False

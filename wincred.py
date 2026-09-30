# MedSearch — Windows Credential Manager.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""The Windows counterpart of the Keychain: Credential Manager.

WHY THIS ONE. It is where Windows keeps an app's secrets for the person signed
in: encrypted with their Windows login, and listed one by one under Control
Panel ▸ Credential Manager ▸ Windows Credentials, where they can be seen and
removed. It is part of every Windows, so there is nothing to install.

HOW. advapi32's CredRead, CredWrite and CredDelete, called through ctypes in
MedSearch's own process, so a secret never goes on a command line. Each is a
generic credential: its target says what it is ("MedSearch/anthropic_api_key",
"MedSearch sign-in (unitn.it)"), its user name is the account.

THIS COMPUTER ONLY. Kept for this PC (CRED_PERSIST_LOCAL_MACHINE); a roaming
profile does not carry it to other computers.

THREE ANSWERS, NOT TWO. `read` tells "there is no such credential" (MISSING)
apart from "Windows would not say" (FAILED), as secrets_store.py needs: only
the first is an answer about what is stored.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

FOUND, MISSING, FAILED = "found", "missing", "failed"

_GENERIC = 1                   # CRED_TYPE_GENERIC
_LOCAL_MACHINE = 2             # CRED_PERSIST_LOCAL_MACHINE
_NOT_FOUND = 1168              # ERROR_NOT_FOUND
MAX_SECRET = 5 * 512           # CRED_MAX_CREDENTIAL_BLOB_SIZE, in bytes


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class CREDENTIAL(ctypes.Structure):
    """CREDENTIALW, field for field."""
    _fields_ = [("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", _FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR)]


PCREDENTIAL = ctypes.POINTER(CREDENTIAL)


class _Advapi32:
    """The four calls, typed, and the error each failure left behind."""

    def __init__(self):
        dll = ctypes.WinDLL("advapi32", use_last_error=True)
        dll.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.POINTER(PCREDENTIAL)]
        dll.CredReadW.restype = wintypes.BOOL
        dll.CredWriteW.argtypes = [PCREDENTIAL, wintypes.DWORD]
        dll.CredWriteW.restype = wintypes.BOOL
        dll.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        dll.CredDeleteW.restype = wintypes.BOOL
        dll.CredFree.argtypes = [ctypes.c_void_p]
        dll.CredFree.restype = None
        self.CredReadW, self.CredWriteW = dll.CredReadW, dll.CredWriteW
        self.CredDeleteW, self.CredFree = dll.CredDeleteW, dll.CredFree

    @staticmethod
    def get_last_error():
        return ctypes.get_last_error()


#: advapi32, once asked for; the tests put a fake here.
API = None


def available() -> bool:
    try:
        return _api() is not None
    except Exception:
        return False


def _api():
    global API
    if API is None and sys.platform == "win32":
        API = _Advapi32()
    return API


def read(target: str):
    """(FOUND, user, secret), (MISSING, "", "") or (FAILED, "", "")."""
    api = _api()
    if api is None:
        return FAILED, "", ""
    found = PCREDENTIAL()
    try:
        ok = api.CredReadW(target, _GENERIC, 0, ctypes.byref(found))
    except Exception:
        return FAILED, "", ""
    if not ok:
        return (MISSING if api.get_last_error() == _NOT_FOUND else FAILED), "", ""
    try:
        c = found.contents
        size = int(c.CredentialBlobSize)
        blob = ctypes.string_at(c.CredentialBlob, size) if size else b""
        return FOUND, c.UserName or "", blob.decode("utf-8", "replace")
    finally:
        api.CredFree(found)


def write(target: str, user: str, secret: str, comment: str = "") -> bool:
    """Store (or replace) a credential; False if Windows refused it."""
    api = _api()
    data = secret.encode("utf-8")
    if api is None or len(data) > MAX_SECRET:
        return False
    blob = (ctypes.c_ubyte * max(len(data), 1)).from_buffer_copy(data or b"\0")
    cred = CREDENTIAL(Type=_GENERIC, TargetName=target, Comment=comment or None,
                      CredentialBlobSize=len(data),
                      CredentialBlob=ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte)),
                      Persist=_LOCAL_MACHINE, UserName=user)
    try:
        return bool(api.CredWriteW(ctypes.byref(cred), 0))
    except Exception:
        return False


def delete(target: str) -> bool:
    """True once the credential is gone, whether or not it was there."""
    api = _api()
    if api is None:
        return False
    try:
        if api.CredDeleteW(target, _GENERIC, 0):
            return True
    except Exception:
        return False
    return api.get_last_error() == _NOT_FOUND

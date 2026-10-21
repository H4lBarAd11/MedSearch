# MedSearch — the Keychain through Security.framework, on iOS and macOS.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""Generic-password items in the data-protection Keychain, marked for iCloud
Keychain, so a key typed once on one of a person's devices reaches the others.

WHY NOT /usr/bin/security. secrets_store.py keeps the Mac's keys through that
tool, which iOS does not have and which cannot mark an item synchronisable:
only the SecItem functions can, and only for an app signed by a team (an
unsigned run gets errSecMissingEntitlement, -34018, and secrets_store then
falls back to its file-based ways). The items live under the same service
("MedSearch") and account (the setting's name) as the Mac's, so Keychain
Access shows them beside each other.

TWO BRIDGES, ONE SHAPE. On iOS the Objective-C runtime is reached through
rubicon-objc (which Toga brings); on macOS through PyObjC (which pywebview
brings). Each gives read/write/remove returning an OSStatus; 0 is success.
"""
from __future__ import annotations

import os
import sys

# MEDSEARCH_KEYCHAIN_SERVICE names another service for a check that must not
# touch the real keys (the signed-app walk, 19 Oct); never set in use.
SERVICE = os.environ.get("MEDSEARCH_KEYCHAIN_SERVICE") or "MedSearch"

OK = 0
NOT_FOUND = -25300           # errSecItemNotFound
DUPLICATE = -25299           # errSecDuplicateItem
MISSING_ENTITLEMENT = -34018 # errSecMissingEntitlement: not signed for an access group
NOT_ALLOWED = -25308         # errSecInteractionNotAllowed: the device is locked

_impl = None


def entitled() -> bool:
    """Whether this process may use a keychain access group, which is what
    iCloud Keychain's items need: on iOS always; on a Mac only an app signed
    by a team with the keychain-access-groups entitlement (asked of the
    process itself, through SecTask: a read from the data-protection
    keychain answers "not found" either way, and only a write would tell)."""
    if sys.platform == "ios":
        return True
    if sys.platform != "darwin":
        return False
    try:
        import Security as S
        task = S.SecTaskCreateFromSelf(None)
        groups, _err = S.SecTaskCopyValueForEntitlement(task, "keychain-access-groups", None)
        return bool(groups)
    except Exception:
        return False


def available() -> bool:
    """True when a bridge loads and the Keychain answers a query (any answer,
    "no such item" included) rather than refusing for a missing entitlement."""
    impl = _bridge()
    if impl is None:
        return False
    status, _ = impl.read("__probe__")
    return status in (OK, NOT_FOUND)


def read(name: str) -> tuple[int, str]:
    impl = _bridge()
    if impl is None:
        return MISSING_ENTITLEMENT, ""
    return impl.read(name)


def write(name: str, value: str) -> int:
    impl = _bridge()
    if impl is None:
        return MISSING_ENTITLEMENT
    return impl.write(name, value)


def remove(name: str) -> int:
    impl = _bridge()
    if impl is None:
        return MISSING_ENTITLEMENT
    return impl.remove(name)


def _bridge():
    global _impl
    if _impl is None:
        try:
            if sys.platform == "ios":
                _impl = _Rubicon()
            elif sys.platform == "darwin":
                _impl = _PyObjC()
            else:
                _impl = False
        except Exception as e:  # no bridge on this Python: the caller falls back
            print(f"  (the Keychain bridge did not load: {e})")
            _impl = False
    return _impl or None


# ── iOS: rubicon-objc ──────────────────────────────────────────────────────
class _Rubicon:
    def __init__(self):
        from ctypes import POINTER, c_int32
        from rubicon.objc import ObjCClass, ObjCInstance, objc_id
        from rubicon.objc.runtime import load_library

        self.ObjCInstance, self.objc_id = ObjCInstance, objc_id
        self.sec = load_library("Security")
        self.cf = load_library("CoreFoundation")
        self.sec.SecItemAdd.restype = c_int32
        self.sec.SecItemAdd.argtypes = [objc_id, POINTER(objc_id)]
        self.sec.SecItemCopyMatching.restype = c_int32
        self.sec.SecItemCopyMatching.argtypes = [objc_id, POINTER(objc_id)]
        self.sec.SecItemUpdate.restype = c_int32
        self.sec.SecItemUpdate.argtypes = [objc_id, objc_id]
        self.sec.SecItemDelete.restype = c_int32
        self.sec.SecItemDelete.argtypes = [objc_id]
        self.cf.CFRelease.restype = None
        self.cf.CFRelease.argtypes = [objc_id]
        self.NSMutableDictionary = ObjCClass("NSMutableDictionary")
        self.NSString = ObjCClass("NSString")

    def _k(self, name):
        """A Security.framework constant (a CFStringRef global), as an object."""
        return self.ObjCInstance(self.objc_id.in_dll(self.sec, name))

    def _true(self):
        return self.ObjCInstance(self.objc_id.in_dll(self.cf, "kCFBooleanTrue"))

    def _query(self, name, **more):
        q = self.NSMutableDictionary.alloc().init()
        q.setObject_forKey_(self._k("kSecClassGenericPassword"), self._k("kSecClass"))
        q.setObject_forKey_(SERVICE, self._k("kSecAttrService"))
        q.setObject_forKey_(name, self._k("kSecAttrAccount"))
        # Synchronisable items are invisible to a query that does not ask for
        # them: "any" finds the item whether or not it was marked.
        q.setObject_forKey_(self._k("kSecAttrSynchronizableAny"), self._k("kSecAttrSynchronizable"))
        # On a Mac the synchronisable items live in the data-protection
        # keychain, which has to be asked for by name (iOS has no other).
        if sys.platform == "darwin":
            q.setObject_forKey_(self._true(), self._k("kSecUseDataProtectionKeychain"))
        for key, value in more.items():
            q.setObject_forKey_(value, self._k(key))
        return q

    def _data(self, value: str):
        return self.NSString.stringWithString_(value).dataUsingEncoding_(4)   # NSUTF8StringEncoding

    def read(self, name):
        from ctypes import byref, string_at
        q = self._query(name, kSecReturnData=self._true(), kSecMatchLimit=self._k("kSecMatchLimitOne"))
        out = self.objc_id()
        status = self.sec.SecItemCopyMatching(q.ptr, byref(out))
        if status != OK or not out.value:
            return status, ""
        # SecItemCopyMatching hands over a CFData the caller owns (the Copy
        # rule); wrapping it does not take that over, so it is released here
        # once read, or every read leaked one.
        try:
            data = self.ObjCInstance(out)
            return OK, string_at(data.bytes, data.length).decode("utf-8", "replace")
        finally:
            self.cf.CFRelease(out)

    def write(self, name, value):
        from ctypes import byref
        attrs = self._query(name)
        attrs.setObject_forKey_(self._data(value), self._k("kSecValueData"))
        # Marked for iCloud Keychain, readable once the device has been
        # unlocked since it started (a synchronisable item cannot be
        # "this device only", and the app runs after unlock anyway).
        attrs.setObject_forKey_(self._true(), self._k("kSecAttrSynchronizable"))
        attrs.setObject_forKey_(self._k("kSecAttrAccessibleAfterFirstUnlock"), self._k("kSecAttrAccessible"))
        attrs.setObject_forKey_("MedSearch API key", self._k("kSecAttrLabel"))
        out = self.objc_id()
        status = self.sec.SecItemAdd(attrs.ptr, byref(out))
        if status == DUPLICATE:
            update = self.NSMutableDictionary.alloc().init()
            update.setObject_forKey_(self._data(value), self._k("kSecValueData"))
            status = self.sec.SecItemUpdate(self._query(name).ptr, update.ptr)
        return status

    def remove(self, name):
        status = self.sec.SecItemDelete(self._query(name).ptr)
        return OK if status == NOT_FOUND else status


# ── macOS: PyObjC ──────────────────────────────────────────────────────────
class _PyObjC:
    def __init__(self):
        import Security as S
        self.S = S

    def _query(self, name, **more):
        S = self.S
        q = {S.kSecClass: S.kSecClassGenericPassword,
             S.kSecAttrService: SERVICE,
             S.kSecAttrAccount: name,
             S.kSecAttrSynchronizable: S.kSecAttrSynchronizableAny,
             # The data-protection Keychain, where iCloud items live; without
             # this macOS answers from the file-based login keychain.
             S.kSecUseDataProtectionKeychain: True}
        q.update({getattr(S, k): v for k, v in more.items()})
        return q

    def read(self, name):
        S = self.S
        status, data = S.SecItemCopyMatching(
            self._query(name, kSecReturnData=True, kSecMatchLimit=S.kSecMatchLimitOne), None)
        if status != OK or data is None:
            return status, ""
        return OK, bytes(data).decode("utf-8", "replace")

    def write(self, name, value):
        S = self.S
        attrs = self._query(name)
        attrs[S.kSecValueData] = value.encode("utf-8")
        attrs[S.kSecAttrSynchronizable] = True
        attrs[S.kSecAttrAccessible] = S.kSecAttrAccessibleAfterFirstUnlock
        attrs[S.kSecAttrLabel] = "MedSearch API key"
        status, _ = S.SecItemAdd(attrs, None)
        if status == DUPLICATE:
            status = S.SecItemUpdate(self._query(name), {S.kSecValueData: value.encode("utf-8")})
        return status

    def remove(self, name):
        status = self.S.SecItemDelete(self._query(name))
        return OK if status == NOT_FOUND else status

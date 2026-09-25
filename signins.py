# MedSearch — the library sign-ins it remembers.
# Copyright 2026 Riccardo Nevoso. Licensed under the Apache License, Version 2.0.
"""The sign-in for a library's login page, kept in the Keychain and filled in
for you, the way UniTN VPN keeps the UniTN one.

WHAT IT DOES. Each library in Settings has a "Remember sign-in" box, off until
someone ticks it (the neurosurgery iMac is shared: a sign-in saved there would
sign every later user in as the first). While it is ticked, the username and
password typed on that library's login page are put in the Keychain when the
form is sent. The next time the login page opens in an article window, the form
is filled and sent once; if it comes back (a changed password), it is filled
but left for you, so it cannot loop. Unticking the box deletes the sign-in.

WHERE IT MAY BE READ AND WRITTEN. Only on an https page whose host is the
library's sign-in domain or inside it: unitn.it for UniTN, whose proxy hands
over to idp.unitn.it. For any other library the domain is taken from its proxy
address (`domain_of`). A sign-in is only ever taken from the page's main frame,
and WebKit, not the page, says which site that frame is on, so a page elsewhere
cannot plant a password. The script that fills the form checks the address again
itself, since the page may have moved on while the Keychain was being read.

THROUGH THE SECURITY FRAMEWORK, NOT /usr/bin/security. The API keys go through
that tool (secrets_store.py), which takes the secret as a command-line argument,
and on macOS any local user can read another's arguments with `ps`. A university
password does not go on a command line. Items are written by MedSearch's own
process, so it reads them back without asking; a new Python (a Homebrew update)
is a different program to the Keychain, which then asks once to allow it.
The login keychain stays on this Mac; nothing is synchronised to iCloud.
"""
from __future__ import annotations

import json
import os
import sys
import threading

SERVICE = "MedSearch sign-in"

# The second-level labels under which an institution's own name comes one label
# further down: ox.ac.uk, apss.tn.it (Italy's two-letter province domains).
_SHARED_SECOND_LEVEL = {"ac", "co", "com", "edu", "gov", "net", "nhs", "org"}


def domain_of(url: str) -> str:
    """The sign-in domain of a library, from its proxy address: the registered
    name under which its own pages live. https://ezp.biblio.unitn.it gives
    unitn.it; a login-prefix proxy (…/login?url=) gives its host's domain."""
    s = (url or "").strip().lower()
    if "://" in s:
        s = s.split("://", 1)[1]
    host = s.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = host.rsplit("@", 1)[-1].split(":", 1)[0].strip(".")
    labels = [x for x in host.split(".") if x]
    if len(labels) < 2 or all(x.isdigit() for x in labels):
        return host
    keep = 3 if (len(labels) >= 3 and (len(labels[-2]) <= 2
                                       or labels[-2] in _SHARED_SECOND_LEVEL)) else 2
    return ".".join(labels[-keep:])


def covers(host: str, domain: str) -> bool:
    host, domain = (host or "").lower().strip("."), (domain or "").lower()
    return bool(domain) and (host == domain or host.endswith("." + domain))


def remembered(institutions) -> list[tuple[str, str]]:
    """(domain, library name) for each library whose box is ticked, in order."""
    out = []
    for p in institutions or []:
        if not isinstance(p, dict) or p.get("remember_signin") is not True:
            continue
        domain = domain_of(p.get("url") or "")
        if "." in domain:
            out.append((domain, (p.get("label") or "").strip() or "Library"))
    return out


def match(host: str, institutions):
    """The ticked library whose sign-in domain holds `host`, or None."""
    for domain, label in remembered(institutions):
        if covers(host, domain):
            return domain, label
    return None


def dropped(before, after) -> list[str]:
    """The domains whose sign-in must be deleted after Settings are saved: ticked
    before, not any more (unticked, removed, or moved to another address)."""
    now = {d for d, _ in remembered(after)}
    return sorted({d for d, _ in remembered(before)} - now)


def take(body, main_frame: bool, protocol: str, host: str, institutions):
    """What a sent login form reported, as (domain, library, username, password),
    or None when it must not be kept: not the main frame, not https, not a
    ticked library's domain, or either field empty. `protocol` and `host` are
    WebKit's own account of the frame that sent it."""
    if not main_frame or protocol != "https":
        return None
    hit = match(host, institutions)
    if hit is None or not hasattr(body, "get"):
        return None
    sent = body.get("medsearchSignIn")
    if not hasattr(sent, "get"):
        return None
    user, password = str(sent.get("u") or ""), str(sent.get("p") or "")
    if not user.strip() or not password:
        return None
    return hit[0], hit[1], user, password


# ── the pages ────────────────────────────────────────────────────────────────
# A login form: exactly one password field, and a username field next to it. A
# page with two or three (a password change) is left alone, and so is one with
# a password field only, which may well be asking for a one-time code.
_USER = ("input[type=email], input[autocomplete=username], "
         "input[name*=user i], input[type=text]")

CAPTURE = """
(function () {
  if (window.__medsearchSignIn) return;
  window.__medsearchSignIn = true;
  document.addEventListener('submit', function (e) {
    var f = e.target, ps = f.querySelectorAll('input[type=password]');
    if (ps.length !== 1 || !ps[0].value) return;
    var u = f.querySelector(%s);
    if (!u || !u.value.trim()) return;
    window.webkit.messageHandlers.browserDelegate.postMessage(
      { medsearchSignIn: { u: u.value, p: ps[0].value } });
  }, true);
})();
""" % json.dumps(_USER)

# Filled with JSON-encoded values, so nothing in a password can break out of the
# string. A form already holding a DIFFERENT username is someone else signing
# in: it gets nothing.
_FILL = """
(function (a, domain, submit) {
  var h = location.hostname;
  if (location.protocol !== 'https:' || !(h === domain || h.endsWith('.' + domain))) return false;
  var ps = document.querySelectorAll('input[type=password]');
  if (ps.length !== 1 || !ps[0].form) return false;
  var p = ps[0], f = p.form, u = f.querySelector(%s);
  if (!u || (u.value && u.value !== a[0])) return false;
  function set(el, v) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  if (!u.value) set(u, a[0]);
  set(p, a[1]);
  if (!submit) return false;
  var b = f.querySelector('[type=submit]');
  if (b) b.click(); else if (f.requestSubmit) f.requestSubmit(); else f.submit();
  return true;
})(%%s, %%s, %%s);
""" % json.dumps(_USER)


def fill_script(user: str, password: str, domain: str, submit: bool) -> str:
    return _FILL % (json.dumps([user, password]), json.dumps(domain),
                    "true" if submit else "false")


# ── the Keychain ─────────────────────────────────────────────────────────────
class KeychainStore:
    """One generic password per sign-in domain: the service names the domain,
    the account is the username, so Keychain Access shows whose it is."""

    def available(self) -> bool:
        # MEDSEARCH_KEYCHAIN=0 is how the test suite stays out of the real Keychain.
        if os.environ.get("MEDSEARCH_KEYCHAIN") == "0" or sys.platform != "darwin":
            return False
        try:
            import Security  # noqa: F401
        except Exception:
            return False
        return True

    @staticmethod
    def _service(domain):
        return f"{SERVICE} ({domain})"

    def load(self, domain):
        """(username, password), or None."""
        if not self.available():
            return None
        import Security as S
        status, item = S.SecItemCopyMatching({
            S.kSecClass: S.kSecClassGenericPassword,
            S.kSecAttrService: self._service(domain),
            S.kSecReturnAttributes: True,
            S.kSecReturnData: True,
            S.kSecMatchLimit: S.kSecMatchLimitOne,
        }, None)
        if status != 0 or item is None:
            return None
        user = item.get(S.kSecAttrAccount)
        data = item.get(S.kSecValueData)
        if not user or data is None:
            return None
        password = bytes(data).decode("utf-8", "replace")
        return (str(user), password) if password else None

    def save(self, domain, user, password, label) -> bool:
        if not self.available():
            return False
        import Security as S
        self.forget(domain)
        status, _ = S.SecItemAdd({
            S.kSecClass: S.kSecClassGenericPassword,
            S.kSecAttrService: self._service(domain),
            S.kSecAttrAccount: user,
            S.kSecAttrLabel: f"MedSearch — {label} sign-in",
            S.kSecValueData: password.encode("utf-8"),
        }, None)
        return status == 0

    def forget(self, domain) -> bool:
        if not self.available():
            return False
        import Security as S
        status = S.SecItemDelete({S.kSecClass: S.kSecClassGenericPassword,
                                  S.kSecAttrService: self._service(domain)})
        return status in (0, S.errSecItemNotFound)


STORE = KeychainStore()


def keep(domain, label, user, password, store=None) -> bool:
    """Store a sign-in unless the Keychain already holds exactly that one: an
    unchanged sign-in is not rewritten on every visit."""
    store = store or STORE
    if store.load(domain) == (user, password):
        return False
    return store.save(domain, user, password, label)


def forget_later(domains, store=None) -> None:
    """Delete these sign-ins off the request's thread: the Keychain may stop to
    ask, and Settings must not hang on it."""
    store = store or STORE
    if not domains:
        return

    def run():
        for d in domains:
            try:
                store.forget(d)
            except Exception as e:
                print(f"  (couldn't delete the {d} sign-in: {e})")
    threading.Thread(target=run, daemon=True).start()


# ── the windows ──────────────────────────────────────────────────────────────
def install(institutions):
    """Teach every window pywebview builds from now on to keep and fill library
    sign-ins. `institutions` returns the saved library list, read afresh on
    every page, so a box ticked in Settings applies to the next page loaded.
    Returns what runs on a loaded page, for windows pywebview does not build.

    A subclass of whatever delegate pywebview will use (MedSearch's own, when
    the reload-on-crash one is installed), like that one: the sign-in rides on
    the delegate's existing message channel, so nothing new is registered."""
    import objc
    from PyObjCTools import AppHelper
    from webview.platforms.cocoa import BrowserView

    base = BrowserView.BrowserDelegate
    submitted = set()                       # windows whose form was already sent once

    def page_loaded(web):
        url = web.URL()
        if url is None or str(url.scheme() or "").lower() != "https":
            return
        hit = match(str(url.host() or ""), institutions())
        if hit is None:
            return
        domain = hit[0]
        web.evaluateJavaScript_completionHandler_(CAPTURE, None)
        inst = BrowserView.get_instance("webview", web)
        uid = inst.uid if inst is not None else id(web)

        def read_then_fill():
            try:
                saved = STORE.load(domain)
            except Exception as e:
                print(f"  (couldn't read the {domain} sign-in: {e})")
                return
            if not saved:
                return

            def fill():
                def done(result, error):
                    if result is True:
                        submitted.add(uid)
                web.evaluateJavaScript_completionHandler_(
                    fill_script(saved[0], saved[1], domain, uid not in submitted), done)
            AppHelper.callAfter(fill)
        # The Keychain may stop to ask; the window's thread must not wait on it.
        threading.Thread(target=read_then_fill, daemon=True).start()

    class MedSearchSignInDelegate(base):
        def webView_didFinishNavigation_(self, web, nav):
            objc.super(MedSearchSignInDelegate, self).webView_didFinishNavigation_(web, nav)
            try:
                page_loaded(web)
            except Exception as e:
                print(f"  (sign-in fill skipped: {e})")

        def userContentController_didReceiveScriptMessage_(self, controller, message):
            body = message.body()
            if hasattr(body, "get") and "medsearchSignIn" in body:
                try:
                    frame = message.frameInfo()
                    origin = frame.securityOrigin()
                    got = take(body, bool(frame.isMainFrame()), str(origin.protocol() or ""),
                               str(origin.host() or ""), institutions())
                except Exception as e:
                    print(f"  (sign-in not kept: {e})")
                    return
                if got:
                    threading.Thread(target=keep, args=got, daemon=True).start()
                return
            objc.super(MedSearchSignInDelegate, self).userContentController_didReceiveScriptMessage_(
                controller, message)

    BrowserView.BrowserDelegate = MedSearchSignInDelegate
    return page_loaded

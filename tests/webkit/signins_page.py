"""The library sign-in hooks in a real WebKit page, without a window.

Run by tests/test_signins.py in a process of its own (it stands in a small
imitation of pywebview's window class, which must not leak into the suite), or
directly:  .venv/bin/python tests/webkit/signins_page.py

NO WINDOW, NO DOCK ICON, NO NETWORK. The web view is never put in a window, the
process asks for no Dock icon, and every navigation after the test page's own
load is refused and written down instead: a form that is sent is recorded, never
posted. The page is a copy of UniTN's login form, loaded as if it came from
idp.unitn.it, so WebKit reports that site as the sender, as it would for the real
page. Prints one PASS/FAIL line per check and exits 1 if any failed.
"""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from AppKit import NSApplication                                    # noqa: E402
from Foundation import NSObject, NSRunLoop, NSDate, NSURL, NSMakeRect  # noqa: E402
import WebKit                                                       # noqa: E402

NSApplication.sharedApplication().setActivationPolicy_(2)          # no Dock icon

log = {"nav": [], "print": 0, "finished": 0}


class PywebviewDelegate(NSObject):
    """What signins.install() subclasses: pywebview's page delegate, reduced to
    the parts it relies on, plus the refusal of every second navigation."""

    def webView_didFinishNavigation_(self, web, nav):
        log["finished"] += 1

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        if message.body() == "print":
            log["print"] += 1

    def webView_decidePolicyForNavigationAction_decisionHandler_(self, web, action, handler):
        url, frame = action.request().URL(), action.targetFrame()
        if frame is not None and not frame.isMainFrame() and str(url.scheme()) == "about":
            handler(WebKit.WKNavigationActionPolicyAllow)     # an inline frame, no network
            return
        if getattr(self, "allow_one", False):
            self.allow_one = False                 # the test page itself, and nothing else
            handler(WebKit.WKNavigationActionPolicyAllow)
            return
        log["nav"].append(str(action.request().URL().absoluteString()))
        handler(WebKit.WKNavigationActionPolicyCancel)


class _Instance:
    uid = "article"


class BrowserView:
    BrowserDelegate = PywebviewDelegate

    @staticmethod
    def get_instance(attr, value):
        return _Instance


for name in ("webview", "webview.platforms", "webview.platforms.cocoa"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["webview.platforms.cocoa"].BrowserView = BrowserView

import signins  # noqa: E402


class Store:
    def __init__(self):
        self.items, self.saves = {}, 0

    def available(self):
        return True

    def load(self, domain):
        return self.items.get(domain)

    def save(self, domain, user, password, label):
        self.saves += 1
        self.items[domain] = (user, password)
        return True

    def forget(self, domain):
        self.items.pop(domain, None)
        return True


store = Store()
signins.STORE = store
LIBRARIES = [{"id": "unitn", "label": "UniTN", "url": "https://ezp.biblio.unitn.it",
              "remember_signin": True}]
signins.install(lambda: LIBRARIES)
assert BrowserView.BrowserDelegate is not PywebviewDelegate

config = WebKit.WKWebViewConfiguration.alloc().init()
config.setWebsiteDataStore_(WebKit.WKWebsiteDataStore.nonPersistentDataStore())
delegate = BrowserView.BrowserDelegate.alloc().init()
config.userContentController().addScriptMessageHandler_name_(delegate, "browserDelegate")
web = WebKit.WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, 800, 600), config)
web.setNavigationDelegate_(delegate)

# UniTN's form as idp.unitn.it serves it: an email-typed username, the password,
# the Login button, then the SPID button inside the same form.
FORM = """<!doctype html><html><body>
<form id="login" action="/idp/profile/SAML2/POST/SSO?execution=e1s1" method="post">
<input type="hidden" name="csrf_token" value="x">
<input name="j_username" type="email" id="clid" value="%s">
<input name="j_password" type="password" id="inputPassword">
<input type="radio" name="dominio" value="@unitn.it" checked>
<button type="submit" name="_eventId_proceed" id="btnAccedi">Login</button>
<button type="submit" name="_eventId_runFlow_ExternalSpidIt" id="spid">SPID</button>
</form>
<script>document.addEventListener('submit', function (e) {
  window.sentWith = e.submitter ? e.submitter.id : '?'; });</script>
</body></html>"""
IDP = "https://idp.unitn.it/idp/profile/SAML2/POST/SSO?execution=e1s1"
USER, PASSWORD = "name.surname@unitn.it", 's3cr"et\\'


def spin(seconds=0.05):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))


def load(html, base):
    before = log["finished"]
    delegate.allow_one = True
    web.loadHTMLString_baseURL_(html, NSURL.URLWithString_(base))
    for _ in range(200):
        spin()
        if log["finished"] > before:
            break
    settle()                        # the Keychain is read on its own thread, then the form filled


def settle():
    for _ in range(10):
        spin()


def js(source):
    box = {}

    def done(result, error):
        box["result"] = result
    web.evaluateJavaScript_completionHandler_(source, done)
    for _ in range(100):
        spin()
        if box:
            break
    return box.get("result")


def fields():
    return js("[document.getElementById('clid').value,"
              " document.getElementById('inputPassword').value].join('|')")


def post(user, password):
    js("window.webkit.messageHandlers.browserDelegate.postMessage("
       "{medsearchSignIn: {u: %s, p: %s}}); 1" % (json.dumps(user), json.dumps(password)))
    settle()


failed = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        failed.append(name)


# Nothing saved: the page is left alone, and what is typed and sent is kept.
load(FORM % "", IDP)
check("nothing saved: nothing filled", fields() == "|")
js("document.getElementById('clid').value = %s;"
   "document.getElementById('inputPassword').value = %s;"
   "document.getElementById('btnAccedi').click(); 1" % (json.dumps(USER), json.dumps(PASSWORD)))
settle()
check("a sent sign-in is kept", store.items.get("unitn.it") == (USER, PASSWORD))

# Saved: filled, and sent once, with the Login button.
sent, saves = len(log["nav"]), store.saves
load(FORM % "", IDP)
check("saved: the form is filled", fields() == f"{USER}|{PASSWORD}")
check("saved: the form is sent once", len(log["nav"]) == sent + 1)
check("sent with Login, not SPID", js("window.sentWith") == "btnAccedi")
check("an unchanged sign-in is not written again", store.saves == saves)

# The form comes back (a changed password): filled, not sent again.
sent = len(log["nav"])
load(FORM % "", IDP)
check("back again: filled", fields() == f"{USER}|{PASSWORD}")
check("back again: not sent a second time", len(log["nav"]) == sent)

# Someone else's username already in the form: no password for it.
load(FORM % "someone.else@unitn.it", IDP)
check("another user's form gets no password", fields() == "someone.else@unitn.it|")

# Another site, even one named to look like it: nothing filled, nothing kept.
store.items["unitn.it"] = (USER, "pw")
load(FORM % "", "https://idp.unitn.it.example.org/login")
check("look-alike host: not filled", fields() == "|")
post("attacker@example.org", "x")
check("look-alike host: its sign-in is not kept", store.items["unitn.it"] == (USER, "pw"))

# A frame inside the right page sending a sign-in of its own: not kept.
load(FORM % "" + "<iframe srcdoc=\"<script>window.webkit.messageHandlers.browserDelegate"
     ".postMessage({medsearchSignIn: {u: 'frame@unitn.it', p: 'f'}})</script>\"></iframe>", IDP)
settle()
check("a frame inside the page: its sign-in is not kept",
      store.items["unitn.it"] == (USER, "pw"))
check("the frame did send it", js("document.querySelector('iframe').contentWindow"
                                  ".webkit !== undefined") is True)

# The right host over plain http: nothing.
load(FORM % "", "http://idp.unitn.it/login")
check("http page: not filled", fields() == "|")
post("attacker@example.org", "x")
check("http page: its sign-in is not kept", store.items["unitn.it"] == (USER, "pw"))

# The box unticked: nothing filled, nothing kept.
LIBRARIES[0]["remember_signin"] = False
load(FORM % "", IDP)
check("unticked: not filled", fields() == "|")
post("other@unitn.it", "z")
check("unticked: not kept", store.items["unitn.it"] == (USER, "pw"))
LIBRARIES[0]["remember_signin"] = True

# A page asking for a password only (a one-time code): not filled.
load("<form action='/x'><input type=password id=code></form>", IDP)
check("password-only form: not filled", js("document.getElementById('code').value") == "")

# A password change (current, new, repeat): never filled, never kept.
CHANGE = """<form action="/change" method="post"><input type="email" id="clid" value="%s">
<input type="password" id="old"><input type="password" id="new"><input type="password" id="again">
<button type="submit" id="go">Change</button></form>"""
load(CHANGE % "", IDP)
check("password change: not filled",
      js("['old','new','again'].map(i => document.getElementById(i).value).join('')") == "")
js("document.getElementById('clid').value = %s; ['old','new','again'].forEach(i =>"
   " document.getElementById(i).value = 'changed'); document.getElementById('go').click(); 1"
   % json.dumps(USER))
settle()
check("password change: not kept", store.items["unitn.it"] == (USER, "pw"))

# pywebview's own message on the same channel still reaches pywebview.
js("window.webkit.messageHandlers.browserDelegate.postMessage('print'); 1")
settle()
check("pywebview's print message still delivered", log["print"] == 1)

print("ALL PASS" if not failed else f"{len(failed)} FAILED")
sys.exit(1 if failed else 0)

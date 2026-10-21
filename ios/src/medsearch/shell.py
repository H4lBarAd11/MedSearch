"""The iOS shell: starts the desktop app's Flask engine inside the app and shows
its page in the system web view. Nothing of the search engine lives here; app.py,
templates/ and static/ are copied in from the repository root by the build
(see pyproject.toml), so a change to the desktop app is a change to this one.

WHAT THE SHELL PROVIDES, as the desktop's pywebview shell does:
- window.pywebview.api.open_external(url, title): the article and PDF buttons
  that cannot be shown in the page itself (a paywalled paper, a publisher's
  viewer, Sci-Hub) open in an SFSafariViewController, the system's in-app
  browser, which carries the person's Safari sign-ins (the library proxy's
  among them), reads PDFs, and offers Share for saving them.
- window.open and any link that would leave the engine's own pages: the same.
- page_ready: ends the app's own splash (Splash below).
- The Keychain comes through secrets_store → secitem (Security.framework).
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import toga
from toga.style.pack import COLUMN, Pack

# The bridge between the page and this shell: a WKScriptMessageHandler, which
# WebKit calls on the main thread with the object the page posted.
from rubicon.objc import SEL, Block, NSObject, ObjCClass, objc_method, py_from_ns
from rubicon.objc.runtime import load_library
from rubicon.objc.types import CGRectMake

_SHELL = None   # the running MedSearch app, for the Objective-C handler


def _engine_dir() -> Path:
    """The folder the build put app.py, templates/ and static/ in: the parent of
    this package."""
    return Path(__file__).resolve().parent.parent


def _no_reverse_lookup():
    """The standard library's HTTP server names itself with a reverse lookup
    of the address it binds (socket.getfqdn in HTTPServer.server_bind): the
    one name resolution the Python side makes at launch (MEDSEARCH_SELFTEST=
    net, 19 Oct). The name is never used; the lookup goes through the system
    resolver, which on a phone is what asks for the local network. The server
    is told its name instead."""
    import http.server
    import socketserver

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = "localhost"
        self.server_port = self.server_address[1]

    http.server.HTTPServer.server_bind = server_bind


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class EngineServer:
    """The engine's HTTP server, which the shell can start again.

    iOS closes the listening socket of an app it suspends (his phone, 20 Oct:
    after a visit to Safari for the Zotero key, every search said "Load
    failed": the page could no longer reach its own server). So the server is
    an object the shell holds, and each time the app becomes active it is
    asked /ping; when it does not answer it is closed and served again, on
    the same port when the system lets it go, else on a new one (the page is
    then loaded again from there)."""

    def __init__(self, app, port: int):
        self.app, self.port, self.srv = app, port, None

    def start(self):
        from werkzeug.serving import make_server
        self.srv = make_server("127.0.0.1", self.port, self.app, threaded=True)
        threading.Thread(target=self.srv.serve_forever, name="medsearch-engine",
                         daemon=True).start()

    def restart(self) -> bool:
        """Serve again; True when the port had to change."""
        old, self.srv = self.srv, None
        if old is not None:
            # shutdown() waits for the serving loop, which a dead socket may
            # have left stuck: two seconds, then on regardless.
            t = threading.Thread(target=old.shutdown, daemon=True)
            t.start()
            t.join(2.0)
            try:
                old.server_close()
            except Exception:
                pass
        try:
            self.start()
            return False
        except (OSError, SystemExit):
            # A port still held: werkzeug says so and calls sys.exit, which
            # would end this thread without a word. A new port, then.
            self.port = _free_port()
            self.start()
            return True


def start_engine() -> tuple[EngineServer, str]:
    """Import the engine and serve it on a free local port, in a thread.
    Returns the server and the per-launch request token."""
    # OpenSSL reads SSL_CERT_FILE when it builds its default verify paths, so
    # the engine's unchanged ssl.create_default_context() finds Mozilla's roots.
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except Exception as e:  # the sources then "don't respond"; say so in the log
        print(f"MedSearch iOS: no certifi ({e})")

    sys.path.insert(0, str(_engine_dir()))
    _self_test()
    _no_reverse_lookup()
    import app as engine  # the desktop engine; its __main__ block does not run
    # Exports and saved PDFs go to the folder picked in Files (exports.py).
    try:
        from medsearch import exports
        engine.EXPORTS_FOLDER = exports.opener(engine.CONFIG_DIR)
        engine.EXPORTS_FOLDER_NAME = lambda: exports.folder_name(engine.CONFIG_DIR)
    except Exception as e:
        print(f"MedSearch iOS: exports stay in the app's own folder ({e})")

    server = EngineServer(engine.app, _free_port())
    server.start()
    return server, engine.APP_TOKEN


def _net_trace():
    """MEDSEARCH_SELFTEST=net: every name lookup and every socket the Python
    side opens, with the line that asked for it, appended to nettrace.txt
    beside selftest.txt. For the question of what makes iOS ask for the
    local network (his phone, 19 Oct): the page is served on 127.0.0.1,
    which is exempt, so whatever asks is something else. A check, not a
    feature."""
    if os.environ.get("MEDSEARCH_SELFTEST") != "net":
        return
    import socket
    import traceback
    out = Path.home() / "Library" / "Application Support" / "MedSearch"
    out.mkdir(parents=True, exist_ok=True)
    log = out / "nettrace.txt"
    log.write_text("")

    def note(what, args):
        frames = [f for f in traceback.extract_stack()[:-2]
                  if "nettrace" not in f.filename and "/socket.py" not in f.filename]
        where = " < ".join(f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in frames[-4:])
        with log.open("a") as fh:
            fh.write(f"{what} {args!r}\n    {where}\n")

    def wrap(name, pick=lambda a, k: a):
        orig = getattr(socket, name)

        def traced(*a, **k):
            note(name, pick(a, k))
            return orig(*a, **k)
        setattr(socket, name, traced)

    for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr",
                 "getfqdn", "gethostname", "getnameinfo", "create_connection"):
        wrap(name, lambda a, k: a[:1])
    cls = socket.socket
    for meth in ("connect", "connect_ex", "sendto", "bind"):
        orig = getattr(cls, meth)

        def traced(self, *a, _orig=orig, _meth=meth, **k):
            note(f"socket.{_meth}", a[-1:] if a else ())
            return _orig(self, *a, **k)
        setattr(cls, meth, traced)


def _self_test():
    """MEDSEARCH_SELFTEST=keychain: a round trip through the Keychain before
    the engine starts, its result in Library/Application Support/MedSearch/
    selftest.txt (the engine's own folder on iOS), where the Mac can read it
    from a simulator's container. A check, not a feature."""
    _net_trace()
    if os.environ.get("MEDSEARCH_SELFTEST") != "keychain":
        return
    lines = []
    try:
        import secitem
        lines.append(f"available: {secitem.available()}")
        lines.append(f"write: {secitem.write('selftest_key', 'sk-test-123')}")
        lines.append(f"read: {secitem.read('selftest_key')}")
        lines.append(f"rewrite: {secitem.write('selftest_key', 'sk-test-456')}")
        lines.append(f"read: {secitem.read('selftest_key')}")
        lines.append(f"remove: {secitem.remove('selftest_key')}")
        lines.append(f"read after remove: {secitem.read('selftest_key')}")
    except Exception:
        import traceback
        lines.append("ERROR " + traceback.format_exc())
    out = Path.home() / "Library" / "Application Support" / "MedSearch"
    out.mkdir(parents=True, exist_ok=True)
    (out / "selftest.txt").write_text("\n".join(lines) + "\n")


def wait_until_up(port: int, timeout: float = 15.0) -> bool:
    """/ping needs no token; true once the engine answers it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def _opening_query() -> str:
    """A search to open on, as the desktop's --query: MEDSEARCH_QUERY (and
    MEDSEARCH_SOURCE) in the app's environment. The simulator passes them as
    SIMCTL_CHILD_MEDSEARCH_QUERY=... briefcase run iOS."""
    q = os.environ.get("MEDSEARCH_QUERY", "").strip()
    if not q:
        return ""
    return "?" + urllib.parse.urlencode(
        {"q": q, "src": os.environ.get("MEDSEARCH_SOURCE", "").strip()})


# What the page sees as window.pywebview, installed before any of its own
# script runs (WKUserScriptInjectionTimeAtDocumentStart), so app.js finds the
# API where the desktop's shell puts it and never falls back to window.open,
# which a web view without a delegate ignores.
_PAGE_BRIDGE_JS = """
(function () {
  var post = function (m) {
    try { window.webkit.messageHandlers.medsearch.postMessage(m); return true; } catch (e) { return false; }
  };
  // The chrome is native: the page hides its own bars (touch.css).
  document.documentElement.classList.add('native-chrome');
  window.pywebview = { api: {
    open_external: function (url, title) {
      post({cmd: 'open', url: String(url || ''), title: String(title || '')});
    },
    page_ready: function () { post({cmd: 'ready'}); }
  }};
  window.open = function (url) {
    post({cmd: 'open', url: String(url || ''), title: ''});
    return null;
  };
  // A link that would leave the engine's pages opens in the in-app browser
  // instead of taking the window away from MedSearch. (Toga's navigation
  // hook would do this, but it re-loads every page it approves.)
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var href = a.href || '';
    if (/^https?:/i.test(href) && href.indexOf(location.origin) !== 0) {
      e.preventDefault();
      post({cmd: 'open', url: href, title: (a.textContent || '').trim()});
    }
  }, true);
  // Errors, questions and sharing as the system's own (his ask, 20 Oct:
  // errors and warnings as Liquid Glass popups, not whole screens). app.js
  // calls these when they are here; a question's answer comes back through
  // __msAnswer, as the page's own dialog would have given it.
  var asks = {}, askId = 0;
  window.__msNative = {
    alert: function (title, text) {
      return post({cmd: 'alert', title: String(title || ''), text: String(text || '')});
    },
    ask: function (o) {
      o = o || {};
      var id = ++askId;
      return new Promise(function (resolve) {
        asks[id] = resolve;
        var sent = post({cmd: 'ask', id: id, title: String(o.title || ''), text: String(o.text || ''),
                         okLabel: String(o.okLabel || 'OK'), danger: !!o.danger,
                         input: o.input === undefined ? null : String(o.input)});
        if (!sent) { delete asks[id]; resolve(typeof _pageAsk === 'function' ? _pageAsk(o) : null); }
      });
    },
    // A choice among a few, as the system's action sheet: the index chosen,
    // or null. rect: the page's button it comes from (an iPad points at it).
    choose: function (title, text, options, rect) {
      var id = ++askId;
      return new Promise(function (resolve) {
        asks[id] = resolve;
        if (!post({cmd: 'choose', id: id, title: String(title || ''), text: String(text || ''),
                   options: (options || []).map(String), rect: rect || null})) { delete asks[id]; resolve(undefined); }
      });
    },
    // screen: whether a screen has the display as the toast is asked for, so
    // it takes the bottom (the bars are there) or the X's row (they're not).
    toast: function (text, kind) {
      return post({cmd: 'toast', text: String(text || ''), kind: String(kind || ''), screen: screenUp()});
    },
    share: function (url, title) {
      return post({cmd: 'share', url: String(url || ''), title: String(title || '')});
    },
    // The folder for exports and saved PDFs, picked in Files: true once one is.
    pickFolder: function () {
      var id = ++askId;
      return new Promise(function (resolve) {
        asks[id] = resolve;
        if (!post({cmd: 'pickFolder', id: id})) { delete asks[id]; resolve(false); }
      });
    }
  };
  window.__msAnswer = function (id, value) {
    var r = asks[id]; delete asks[id];
    if (r) r(value);
  };
  // The keyboard gone, the page back in place (with the native side's
  // UIKeyboardDidHide, page_back_in_place): once no field has the focus, and
  // when the visible viewport is full height again (21 Oct).
  document.addEventListener('focusout', function () {
    setTimeout(function () {
      var a = document.activeElement;
      if (!a || !/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) window.scrollTo(0, 0);
    }, 120);
  });
  if (window.visualViewport) window.visualViewport.addEventListener('resize', function () {
    var v = window.visualViewport;
    if (v.height >= window.innerHeight - 1 && (v.offsetTop || window.scrollY)) window.scrollTo(0, 0);
  });
  // The native close button: whatever has the screen, closed.
  window.__msCloseAll = function () {
    try { if (typeof closeTopDialog === 'function' && closeTopDialog()) return; } catch (e) {}
    try { if (document.querySelector('.pdf-overlay.open') && typeof closePdf === 'function') { closePdf(); return; } } catch (e) {}
    // The page's own state, not the class: a sheet sliding out still has
    // .open, and a second tap on the X would have opened it again.
    try { if (typeof assistantOpen !== 'undefined' && assistantOpen && typeof toggleAssistant === 'function') { toggleAssistant(); return; } } catch (e) {}
    try { if (typeof synthesisOpen !== 'undefined' && synthesisOpen && typeof closeSynthesis === 'function') { closeSynthesis(); return; } } catch (e) {}
    try { if (typeof closePanels === 'function') closePanels(); } catch (e) {}
  };
  // One that is sliding out (.closing, app.js _sheetOut) counts as gone.
  function sheetUp() {
    return !!document.querySelector('.modal-overlay.open:not(:has(> .closing)), .pdf-overlay.open:not(:has(> .closing)), ' +
                                    '.assistant-panel.open:not(.closing), .synthesis-panel.open:not(.closing)');
  }
  function panelUp() { return !!document.querySelector('.dock-panel:not([hidden]):not(.closing)'); }
  function screenUp() { return sheetUp() || panelUp(); }
  // What the native chrome mirrors: the sources label, the query, the dock
  // button that is "on", and whether a sheet is open (the chrome steps aside).
  var last = {};
  function report() {
    var label = (document.getElementById('dockSourcesLabel') || {}).textContent || '';
    var input = document.getElementById('searchInput');
    var query = input ? input.value : '';
    var on = -1, hid = [];
    var btns = document.querySelectorAll('#dock .dock-btn');
    for (var i = 0; i < btns.length; i++) {
      if (on < 0 && btns[i].classList.contains('on')) on = i;
      if (btns[i].hidden) hid.push(i);
    }
    var sheet = sheetUp();
    var panel = panelUp();
    var now = {label: label, query: query, on: on, sheet: sheet, panel: panel, hidden: hid.join(',')};
    for (var k in now) if (now[k] !== last[k]) { post({cmd: 'state', state: now}); break; }
    last = now;
  }
  document.addEventListener('DOMContentLoaded', function () {
    report();
    new MutationObserver(function () { report(); }).observe(document.body,
      {subtree: true, attributes: true, childList: true, characterData: true,
       attributeFilter: ['class', 'hidden']});
    setInterval(report, 500);   // a typed or restored query changes no attribute
  });
})();
"""


class Splash:
    """The icon's drawing on the interface's ground, over the window from the
    moment it exists until the page says it is ready (page_ready through the
    bridge), then faded off: the Mac's splash (splash.py), minus the pen.
    The launch screen before it is the same ground, so the drawing simply
    appears on it once Python is up. Drawn by the app itself because what the
    system makes of a launch screen's image varies by device and version
    (patch_xcode.py tells the story); the ground is all it is asked for."""

    SIDE = 320                       # points; the drawing fills about 180

    def __init__(self, window):
        UIView = ObjCClass("UIView")
        UIImageView = ObjCClass("UIImageView")
        UIImage = ObjCClass("UIImage")
        UIColor = ObjCClass("UIColor")
        self.view = UIView.alloc().initWithFrame(window.bounds)
        self.view.autoresizingMask = 2 | 16                     # width, height
        # The page's ground (app.css --bg), light or dark as the phone is:
        # the launch screen before it takes the same two from the asset
        # catalogue (LaunchGround, patch_xcode.py), so the drawing appears
        # on the ground already there (dark mode: his ask, 19 Oct).
        dark = window.traitCollection.userInterfaceStyle == 2
        rgb = (0x1B, 0x1A, 0x17) if dark else (0xF9, 0xF8, 0xEF)
        self.view.backgroundColor = UIColor.colorWithRed_green_blue_alpha_(
            rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, 1.0)
        path = str(Path(__file__).resolve().parent / "resources" / "opening.png")
        image = UIImage.imageWithContentsOfFile_(path)
        if image is not None:
            b = window.bounds
            art = UIImageView.alloc().initWithImage_(image)
            art.contentMode = 1                                   # aspect fit
            art.frame = CGRectMake((b.size.width - self.SIDE) / 2,
                                   (b.size.height - self.SIDE) / 2, self.SIDE, self.SIDE)
            art.autoresizingMask = 1 | 4 | 8 | 32                 # flexible margins
            self.view.addSubview_(art)
        window.addSubview_(self.view)
        self.ended = False

    def end(self, loop):
        """Fade off over the page, then leave the window."""
        if self.ended:
            return
        self.ended = True
        UIView = ObjCClass("UIView")
        view = self.view

        def fade() -> None:
            view.alpha = 0.0

        try:
            UIView.animateWithDuration(0.4, animations=Block(fade))
        except Exception:
            fade()
        loop.call_later(0.45, view.removeFromSuperview)


class LifecycleObserver(NSObject):
    """Each time the app becomes active: is the engine still there?"""

    @objc_method
    def becameActive_(self, note) -> None:
        if _SHELL is not None:
            _SHELL.check_engine()

    @objc_method
    def keyboardHid_(self, note) -> None:
        if _SHELL is not None:
            _SHELL.page_back_in_place()


class MedSearchBridge(NSObject):
    @objc_method
    def userContentController_didReceiveScriptMessage_(self, controller, message) -> None:
        try:
            body = py_from_ns(message.body)
        except Exception:
            body = None
        if not isinstance(body, dict):
            return
        cmd = str(body.get("cmd", ""))
        if _SHELL is None:
            return
        if cmd == "open":
            _SHELL.open_in_browser(str(body.get("url", "")), str(body.get("title", "")))
        elif cmd == "state":
            _SHELL.page_state(body.get("state") or {})
        elif cmd == "ready":
            _SHELL.page_is_ready()
        elif cmd == "log":          # a line from the page into the run log (checks)
            print(f"page: {body.get('text', '')}")
        elif cmd == "alert":
            _SHELL.show_alert(str(body.get("title", "")), str(body.get("text", "")))
        elif cmd == "ask":
            _SHELL.show_ask(body)
        elif cmd == "choose":
            _SHELL.show_choice(body)
        elif cmd == "toast":
            _SHELL.show_toast(str(body.get("text", "")), str(body.get("kind", "")), bool(body.get("screen")))
        elif cmd == "share":
            _SHELL.share(str(body.get("url", "")), str(body.get("title", "")))
        elif cmd == "pickFolder":
            _SHELL.pick_export_folder(int(body.get("id", 0) or 0))


class MedSearch(toga.App):
    def startup(self):
        global _SHELL
        _SHELL = self
        self.origin = ""
        # MEDSEARCH_SELFTEST=hold: the launch screen stays ten seconds, long
        # enough for `devicectl device capture screenshot` to see it (a phone
        # shows it for well under a second). A check, not a feature.
        if os.environ.get("MEDSEARCH_SELFTEST") == "hold":
            time.sleep(10)

        self.web = toga.WebView(style=Pack(flex=1))
        box = toga.Box(children=[self.web], style=Pack(direction=COLUMN))
        # A plain Window, not a MainWindow: the MainWindow puts a navigation
        # bar with the app's name above the page, and the page has its own
        # chrome. The page then takes the whole screen, status bar included,
        # and lays itself out with the safe-area insets (viewport-fit=cover).
        self.main_window = toga.Window(title=self.formal_name)
        self.main_window.content = box
        self.main_window.show()
        self._take_the_whole_screen()
        self._install_page_bridge()
        # The page scrolls its results inside itself, as on the desktop; the
        # web view's own scroller only let a finger drag the whole page
        # under an open screen (his phone, 19 Oct). Off, and no bounce.
        try:
            sv = self.web._impl.native.scrollView
            sv.scrollEnabled = False
            sv.bounces = False
        except Exception as e:
            print(f"MedSearch iOS: the web view's scroller stays ({e})")
        self.chrome = None
        self._alert_blocks = {}       # question id -> (blocks, alert), until answered
        try:
            from medsearch.chrome import NativeChrome
            native = self.main_window._impl.native
            self.chrome = NativeChrome(native, self._run_js, wide=native.bounds.size.width > 700)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"MedSearch iOS: the native chrome did not build ({e}); the page's own bars stay")
            self._no_native_chrome = True
        self.splash = None
        try:
            self.splash = Splash(self.main_window._impl.native)
            # Whatever the page does, the splash leaves: an engine that fails
            # shows its message underneath.
            self.loop.call_later(15, self.page_is_ready)
        except Exception as e:
            print(f"MedSearch iOS: no splash ({e})")

        try:
            self.engine_server, _token = start_engine()
            port = self.engine_server.port
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_failure("MedSearch could not start", str(e))
            return
        self.origin = f"http://127.0.0.1:{port}"
        self._watch_lifecycle()
        # MEDSEARCH_SELFTEST=restart: the server is closed and its port held
        # by another socket, as iOS leaves it after a suspension, then the
        # return is played; the log says whether the engine came back.
        if os.environ.get("MEDSEARCH_SELFTEST") == "restart":
            def drop():
                time.sleep(12)
                srv = self.engine_server.srv
                srv.shutdown()
                srv.server_close()
                self._squatter = socket.socket()
                self._squatter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._squatter.bind(("127.0.0.1", self.engine_server.port))
                self._squatter.listen(1)
                print("MedSearch iOS: selftest dropped the engine")
                self.loop.call_soon_threadsafe(self.check_engine)
            threading.Thread(target=drop, daemon=True).start()

        # MEDSEARCH_SELFTEST=keyboard: the web view's content is offset 44 pt
        # and the keyboard's going announced; the log says whether it was put
        # back. A check of the handler only: a simulator (typing on the Mac's
        # keyboard) never shows the phone's shifted page itself.
        if os.environ.get("MEDSEARCH_SELFTEST") == "keyboard":
            def lift() -> None:
                from rubicon.objc.types import CGPoint
                self.web._impl.native.scrollView.setContentOffset_animated_(CGPoint(0, 44), False)
                print("MedSearch iOS: selftest lifted the page 44 pt")

            def hide() -> None:
                ObjCClass("NSNotificationCenter").defaultCenter.postNotificationName_object_(
                    "UIKeyboardDidHideNotification", None)
            self.loop.call_later(14, lift)
            self.loop.call_later(18, hide)

        def open_when_ready():
            up = wait_until_up(port)

            def show():
                if up:
                    self.web.url = f"{self.origin}/{_opening_query()}"
                    if getattr(self, "_no_native_chrome", False):
                        self.loop.call_later(3, lambda: self._run_js(
                            "document.documentElement.classList.remove('native-chrome')"))
                else:
                    self._show_failure("MedSearch's engine did not answer",
                                       "Close MedSearch and open it again.")
            self.loop.call_soon_threadsafe(show)

            # MEDSEARCH_SELFTEST_JS: script run in the page once it is up, as
            # a tap would (a simulator cannot be tapped from the terminal), so
            # a screenshot can show a panel, a dialog or the in-app browser.
            js = os.environ.get("MEDSEARCH_SELFTEST_JS", "")
            if up and js:
                time.sleep(10)
                self.loop.call_soon_threadsafe(lambda: self.web.evaluate_javascript(js))

        threading.Thread(target=open_when_ready, daemon=True).start()

    # ── The page's bridge ──────────────────────────────────────────────────
    def _install_page_bridge(self):
        try:
            WKUserScript = ObjCClass("WKUserScript")
            controller = self.web._impl.native.configuration.userContentController
            self._bridge = MedSearchBridge.alloc().init()
            controller.addScriptMessageHandler_name_(self._bridge, "medsearch")
            script = WKUserScript.alloc().initWithSource_injectionTime_forMainFrameOnly_(
                _PAGE_BRIDGE_JS, 0, True)   # 0: at document start
            controller.addUserScript_(script)
        except Exception as e:
            print(f"MedSearch iOS: the page bridge did not install ({e})")

    def _run_js(self, script: str):
        try:
            self.web.evaluate_javascript(script)
        except Exception as e:
            print(f"MedSearch iOS: script to the page failed ({e})")

    def page_is_ready(self):
        """The page has drawn itself (page_ready through the bridge): the
        splash fades off it."""
        if self.splash is not None:
            self.splash.end(self.loop)
        if self.chrome is not None:
            self.chrome.tell_page_insets()      # the page is new: it hears the bars' edges again
        # Where the page sits (a check for the run log): the web view's frame
        # and the window's safe areas are what its env() insets should match.
        try:
            f = self.web._impl.native.frame
            w = self.main_window._impl.native
            ins = w.safeAreaInsets
            print(f"page: web view at y={f.origin.y:.0f} h={f.size.height:.0f} of window h={w.bounds.size.height:.0f}; "
                  f"safe areas top={ins.top:.0f} bottom={ins.bottom:.0f}")
        except Exception:
            pass

    def page_state(self, state: dict):
        """What the page reports; the native chrome mirrors it."""
        if self.chrome is None:
            return
        try:
            self.chrome.set_sources_label(str(state.get("label", "")))
            self.chrome.set_query(str(state.get("query", "")))
            self.chrome.set_dock_on(int(state.get("on", -1)))
            hidden = str(state.get("hidden", "") or "")
            self.chrome.set_dock_hidden({int(x) for x in hidden.split(",") if x.strip().isdigit()})
            self.chrome.set_open(bool(state.get("sheet")) or bool(state.get("panel")))
            self._log_presented()
        except Exception as e:
            print(f"MedSearch iOS: chrome state failed ({e})")

    def _log_presented(self):
        """Diagnostics (21 Oct, a dimmed screen on his phone): what is
        presented over the page, if anything."""
        try:
            root = self.main_window._impl.native.rootViewController
            p = root.presentedViewController
            chain = []
            while p is not None:
                chain.append(str(p.objCClass.name))
                p = p.presentedViewController
            if chain or getattr(self, "_last_presented", None):
                print(f"MedSearch iOS: presented over the page: {chain or 'nothing'}")
            self._last_presented = chain
        except Exception as e:
            print(f"MedSearch iOS: presented check failed ({e})")

    def open_in_browser(self, url: str, title: str):
        """The system's in-app browser (SFSafariViewController), presented over
        the page. Only http(s) can be shown there; anything else is dropped."""
        if not url.lower().startswith(("http://", "https://")):
            print(f"MedSearch iOS: not a web address, not opened: {url[:80]}")
            return
        try:
            load_library("SafariServices")
            SFSafariViewController = ObjCClass("SFSafariViewController")
            NSURL = ObjCClass("NSURL")
            nsurl = NSURL.URLWithString_(url)
            if nsurl is None:
                return
            vc = SFSafariViewController.alloc().initWithURL_(nsurl)
            vc.dismissButtonStyle = 1    # "Close"
            top = self.main_window._impl.native.rootViewController
            while top.presentedViewController is not None:
                top = top.presentedViewController
            top.presentViewController_animated_completion_(vc, True, None)
        except Exception as e:
            print(f"MedSearch iOS: the in-app browser did not open ({e})")

    def check_engine(self):
        """Ask the engine for /ping, off the main thread; serve it again when
        it does not answer (EngineServer)."""
        server = getattr(self, "engine_server", None)
        if server is None or not self.origin:
            return

        def check():
            if wait_until_up(server.port, timeout=1.5):
                return
            print("MedSearch iOS: the engine did not answer on return; serving it again")
            try:
                moved = server.restart()
            except Exception as e:
                print(f"MedSearch iOS: the engine could not be served again ({e})")
                return
            if not wait_until_up(server.port, timeout=5):
                print("MedSearch iOS: the engine still does not answer")
                return
            print(f"MedSearch iOS: the engine answers again on port {server.port}")
            if moved:
                def reload():
                    self.origin = f"http://127.0.0.1:{server.port}"
                    self.web.url = f"{self.origin}/"
                self.loop.call_soon_threadsafe(reload)

        threading.Thread(target=check, name="medsearch-engine-check", daemon=True).start()

    def _watch_lifecycle(self):
        try:
            NSNotificationCenter = ObjCClass("NSNotificationCenter")
            self._life = LifecycleObserver.alloc().init()
            NSNotificationCenter.defaultCenter.addObserver_selector_name_object_(
                self._life, SEL("becameActive:"), "UIApplicationDidBecomeActiveNotification", None)
            NSNotificationCenter.defaultCenter.addObserver_selector_name_object_(
                self._life, SEL("keyboardHid:"), "UIKeyboardDidHideNotification", None)
        except Exception as e:
            print(f"MedSearch iOS: the engine is not checked on return ({e})")

    def page_back_in_place(self):
        """The keyboard has gone: the web view's content back to the top. To
        keep a field in sight above the keyboard, iOS moves the web view's
        content up (its scroller off or not) and leaves it there when the
        keyboard goes, so the page sat higher than the native bars it lays out
        against: the status line inside the search pill after a key was
        pasted in Settings (his phone, 20 and 21 Oct)."""
        try:
            from rubicon.objc.types import CGPoint
            sv = self.web._impl.native.scrollView
            off = sv.contentOffset
            if abs(off.y) > 0.5 or abs(off.x) > 0.5:
                print(f"MedSearch iOS: the keyboard left the page {off.y:.0f} pt up; put back")
                sv.setContentOffset_animated_(CGPoint(0, 0), True)
        except Exception as e:
            print(f"MedSearch iOS: the page was not put back after the keyboard ({e})")
        # And the page's own viewport: WebKit can leave the visible part of the
        # page offset from the one fixed elements hang on, scrollY or not.
        self._run_js("window.scrollTo(0, 0)")

    def _show_failure(self, title: str, detail: str):
        """The engine is not there: say so on a page the native bars and the
        splash do not cover (the sweep, 20 Oct: they hid it)."""
        import html
        if self.splash is not None:
            self.splash.end(self.loop)
        if self.chrome is not None:
            for v in (self.chrome.search, self.chrome.dock, self.chrome.sources, self.chrome.close):
                v.hidden = True
        self.web.set_content("about:blank",
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            '<body style="font-family:-apple-system,sans-serif;padding:calc(env(safe-area-inset-top) + 24px) 20px 24px">'
            f"<h2>{html.escape(title)}</h2><pre style=\"white-space:pre-wrap\">{html.escape(detail)}</pre></body>")

    # ── The system's alert and share sheet ─────────────────────────────────
    def _top_controller(self):
        top = self.main_window._impl.native.rootViewController
        while top.presentedViewController is not None:
            top = top.presentedViewController
        return top

    def show_alert(self, title: str, text: str):
        """An error, as the system's alert: Liquid Glass on iOS 26 and later.
        If it cannot be shown, the page's own dialog says it instead."""
        try:
            UIAlertController = ObjCClass("UIAlertController")
            UIAlertAction = ObjCClass("UIAlertAction")
            alert = UIAlertController.alertControllerWithTitle_message_preferredStyle_(
                title or None, text or None, 1)                       # 1: alert
            alert.addAction_(UIAlertAction.actionWithTitle_style_handler_("OK", 0, None))
            self._top_controller().presentViewController_animated_completion_(alert, True, None)
        except Exception as e:
            print(f"MedSearch iOS: the system alert did not show ({e}); the page's own does")
            self._run_js(f"_pageFail({json.dumps(text)}, {json.dumps(title)})")

    def show_toast(self, text: str, kind: str, screen: bool = False):
        """A notice, as the chrome's glass capsule; the page's own without it."""
        if self.chrome is not None:
            try:
                self.chrome.show_toast(text, kind, self.loop.call_later, screen)
                return
            except Exception as e:
                print(f"MedSearch iOS: the native toast did not show ({e}); the page's own does")
        self._run_js(f"_pageToast({json.dumps(text)}, {json.dumps(kind)})")

    def show_ask(self, body: dict):
        """A question (a confirmation, or a line to type), as the system's
        alert. The answer goes back to the page: the text or true for OK,
        null for Cancel — what the page's own dialog would have given."""
        try:
            qid = int(body.get("id", 0))
        except Exception:
            return
        title = str(body.get("title", "") or "")
        text = str(body.get("text", "") or "")
        ok_label = str(body.get("okLabel", "") or "OK")
        danger = bool(body.get("danger"))
        start = body.get("input")
        has_input = start is not None

        def answer(value):
            self._alert_blocks.pop(qid, None)
            self._run_js(f"window.__msAnswer && window.__msAnswer({qid}, {json.dumps(value)})")

        try:
            from rubicon.objc.runtime import objc_id
            UIAlertController = ObjCClass("UIAlertController")
            UIAlertAction = ObjCClass("UIAlertAction")
            alert = UIAlertController.alertControllerWithTitle_message_preferredStyle_(
                title or None, text or None, 1)
            if has_input:
                alert.addTextFieldWithConfigurationHandler_(None)
                alert.textFields.objectAtIndex_(0).text = str(start)

            def on_cancel(_action) -> None:
                answer(None)

            def on_ok(_action) -> None:
                if has_input:
                    field = alert.textFields.objectAtIndex_(0)
                    answer(str(field.text or ""))
                else:
                    answer(True)

            # The blocks live until their answer: UIKit holds them, and
            # Python must too, or the callables behind them could go.
            blocks = (Block(on_cancel, None, objc_id), Block(on_ok, None, objc_id))
            self._alert_blocks[qid] = (blocks, alert)
            cancel = UIAlertAction.actionWithTitle_style_handler_("Cancel", 1, blocks[0])     # 1: cancel
            ok = UIAlertAction.actionWithTitle_style_handler_(ok_label, 2 if danger else 0, blocks[1])
            alert.addAction_(cancel)
            alert.addAction_(ok)
            alert.preferredAction = ok
            self._top_controller().presentViewController_animated_completion_(alert, True, None)
        except Exception as e:
            print(f"MedSearch iOS: the system alert did not show ({e}); the page's own asks")
            self._alert_blocks.pop(qid, None)
            o = {"title": title, "text": text, "okLabel": ok_label, "danger": danger}
            if has_input:
                o["input"] = str(start)
            self._run_js(f"_pageAsk({json.dumps(o)}).then(function (v) {{ window.__msAnswer({qid}, v); }})")

    def show_choice(self, body: dict):
        """A few choices as the system's action sheet (Liquid Glass on iOS 26),
        the page's own menu replaced (his ask, 21 Oct). The answer is the
        index chosen, null for Cancel, undefined when the sheet could not show
        (the page then opens its own menu)."""
        try:
            qid = int(body.get("id", 0))
        except Exception:
            return
        options = [str(o) for o in (body.get("options") or [])]

        def answer(value):
            self._alert_blocks.pop(qid, None)
            self._run_js(f"window.__msAnswer && window.__msAnswer({qid}, {json.dumps(value)})")

        try:
            from rubicon.objc.runtime import objc_id
            from rubicon.objc.types import CGRectMake
            UIAlertController = ObjCClass("UIAlertController")
            UIAlertAction = ObjCClass("UIAlertAction")
            sheet = UIAlertController.alertControllerWithTitle_message_preferredStyle_(
                str(body.get("title") or "") or None, str(body.get("text") or "") or None, 0)   # 0: action sheet

            def chose(i):
                def handler(_action) -> None:
                    answer(i)
                return handler

            def on_cancel(_action) -> None:
                answer(None)

            blocks = [Block(chose(i), None, objc_id) for i in range(len(options))]
            blocks.append(Block(on_cancel, None, objc_id))
            self._alert_blocks[qid] = (blocks, sheet)
            for i, label in enumerate(options):
                sheet.addAction_(UIAlertAction.actionWithTitle_style_handler_(label, 0, blocks[i]))
            sheet.addAction_(UIAlertAction.actionWithTitle_style_handler_("Cancel", 1, blocks[-1]))
            # On an iPad the sheet is a popover: it points at the page's button.
            pop = sheet.popoverPresentationController
            if pop is not None:
                window = self.main_window._impl.native
                r = body.get("rect") or {}
                pop.sourceView = window
                if r:
                    pop.sourceRect = CGRectMake(float(r.get("x", 0)), float(r.get("y", 0)),
                                                float(r.get("w", 1)), float(r.get("h", 1)))
                else:
                    b = window.bounds
                    pop.sourceRect = CGRectMake(b.size.width / 2, b.size.height / 2, 1, 1)
            self._top_controller().presentViewController_animated_completion_(sheet, True, None)
        except Exception as e:
            print(f"MedSearch iOS: the action sheet did not show ({e}); the page's own menu does")
            self._alert_blocks.pop(qid, None)
            self._run_js(f"window.__msAnswer && window.__msAnswer({qid}, undefined)")

    def pick_export_folder(self, qid: int):
        """The system's folder picker, once: the folder chosen (Downloads, for
        him) is where exports and saved PDFs go from then on (exports.py)."""
        from medsearch import exports

        def picked(url):
            # The answer: the folder's name once it is kept (Settings shows
            # it), false when cancelled or not kept.
            ok = False
            print(f"MedSearch iOS: folder picker answered: {url.path if url is not None else 'cancelled'}")
            if url is not None:
                try:
                    if exports.remember(url, self._engine_data_dir()):
                        ok = str(url.lastPathComponent) or True
                except Exception as e:
                    print(f"MedSearch iOS: the folder was not kept ({e})")
            self._run_js(f"window.__msAnswer && window.__msAnswer({qid}, {json.dumps(ok)})")

        try:
            if getattr(self, "_folder_delegate", None) is None:
                self._folder_delegate = exports.FolderPickerDelegate.alloc().init()
            picker = exports.folder_picker(self._folder_delegate, picked)
            self._top_controller().presentViewController_animated_completion_(picker, True, None)
        except Exception as e:
            print(f"MedSearch iOS: the folder picker did not open ({e})")
            picked(None)

    def _engine_data_dir(self):
        import app as engine
        return engine.CONFIG_DIR

    def share(self, url: str, title: str):
        """The system's share sheet with one web address: the Zotero app's
        "Save to Zotero" is there when it is installed. The link alone: an
        extension is offered only for what it accepts, and Zotero's takes a
        web address, not text beside it."""
        if not url.lower().startswith(("http://", "https://")):
            return
        try:
            NSURL = ObjCClass("NSURL")
            NSArray = ObjCClass("NSArray")
            UIActivityViewController = ObjCClass("UIActivityViewController")
            nsurl = NSURL.URLWithString_(url)
            if nsurl is None:
                return
            sheet = UIActivityViewController.alloc().initWithActivityItems_applicationActivities_(
                NSArray.arrayWithObject_(nsurl), None)
            # On an iPad the sheet is a popover and must say where it points
            # (without, presenting it raises): the middle of the window.
            pop = sheet.popoverPresentationController
            if pop is not None:
                window = self.main_window._impl.native
                b = window.bounds
                pop.sourceView = window
                pop.sourceRect = CGRectMake(b.size.width / 2, b.size.height / 2, 1, 1)
                pop.permittedArrowDirections = 0
            self._top_controller().presentViewController_animated_completion_(sheet, True, None)
        except Exception as e:
            print(f"MedSearch iOS: the share sheet did not open ({e})")
            self._run_js("_pageFail('Sharing did not open.', \"Couldn't do that\")")

    def _take_the_whole_screen(self):
        """Toga keeps its content under the status bar; this app's page wants
        the screen edge to edge and handles the inset itself. Toga's window
        recomputes the inset on every native layout, so the handler is
        replaced rather than the value."""
        impl = self.main_window._impl
        try:
            def content_native_layout(container, _impl=impl, _app=self):
                container.top_inset = 0
                _impl.notify_resize(container)
                if getattr(_app, "chrome", None) is not None:
                    try:
                        _app.chrome.layout()
                    except Exception as e:
                        print(f"MedSearch iOS: chrome layout failed ({e})")
            # The container holds its own reference to the handler, taken when
            # it was made: that is the one to replace.
            impl.container.on_native_layout = content_native_layout
            impl.content_native_layout = content_native_layout
            impl.container.top_inset = 0
        except Exception as e:  # a Toga without this shape: the inset stays
            print(f"MedSearch iOS: status bar inset left to Toga ({e})")


class _Tee:
    """The app's own messages, also into a file in its container
    (Library/Application Support/MedSearch/shell.log): on a phone they go only
    to the system log, which a Mac reads only through Console, and
    `devicectl device copy from` can fetch a file (21 Oct). Kept small:
    started afresh at each launch once over 512 KB."""

    def __init__(self, stream, path):
        self.stream, self.path = stream, path

    def write(self, text):
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass
        return self.stream.write(text)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def _log_to_file():
    try:
        folder = Path.home() / "Library" / "Application Support" / "MedSearch"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "shell.log"
        if path.exists() and path.stat().st_size > 512 * 1024:
            path.unlink()
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n── launch {time.strftime('%Y-%m-%d %H:%M:%S')} ──\n")
        sys.stdout = _Tee(sys.stdout, path)
        sys.stderr = _Tee(sys.stderr, path)
    except Exception as e:
        print(f"MedSearch iOS: no log file ({e})")


def main():
    _log_to_file()
    return MedSearch()

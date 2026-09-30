"""MedSearch on Windows: the parts that decide something, run on any system.

WinForms, WebView2 and GDI+ only exist on Windows, so what is tested here is
everything around them: the tray's menu and its closing rules, the splash's
frames, what a sign-in message or page may do, the Run key, and the words the
page shows. The Windows build runs this file too; the calls into Windows itself
are seen working in a Windows machine, not here.
"""
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

import app as A
import appmenu
import article_windows as AW
import signins
import splash as S
import splash_win as SW
import tray as T
import wincred as W
from conftest import BASE

INSTITUTIONS = [{"label": "UniTN", "url": "https://ezp.biblio.unitn.it", "remember_signin": True}]


# ── the menu ─────────────────────────────────────────────────────────────────
def test_the_tray_menu_is_the_mac_menu_item_for_item():
    rows = T.menu_model(["glioma", "x" * 80], "cochrane")
    labels = [r if r is None else r[0] for r in rows]
    assert labels == ["Search MedSearch…", None, "Recent searches", "Default source",
                      None, "Open MedSearch window", None, "Quit MedSearch"]
    recents = rows[2][1]
    assert [r[0] for r in recents] == ["glioma", "x" * 57 + "…"]
    assert recents[1][1:3] == ("recent", "x" * 80)          # the whole query is run
    sources = rows[3][1]
    assert [r[0] for r in sources] == [label for _, label in appmenu.SOURCES]
    assert [r[2] for r in sources if r[3]] == ["cochrane"]  # the default is ticked


def test_the_tray_menu_shows_no_recents_before_any_search():
    assert "Recent searches" not in [r and r[0] for r in T.menu_model([], "pubmed")]


def test_the_tray_menu_shows_six_recent_searches_at_most():
    rows = T.menu_model([f"q{i}" for i in range(10)], "pubmed")
    assert [r[2] for r in rows[2][1]] == [f"q{i}" for i in range(6)]


def test_the_mac_menu_lists_the_same_items():
    """Built by statusbar.fill from the same appmenu: the two cannot drift."""
    AppKit = pytest.importorskip("AppKit", reason="the menu bar item is macOS only")
    import statusbar as SB
    host = types.SimpleNamespace(recent_searches=lambda: ["glioma"],
                                 get_source=lambda: "pubmed", target=None)
    host._add = lambda *a, **k: SB.StatusBar._add(host, *a, **k)
    menu = AppKit.NSMenu.alloc().init()
    SB.StatusBar.fill(host, menu)
    mac = [None if menu.itemAtIndex_(i).isSeparatorItem() else str(menu.itemAtIndex_(i).title())
           for i in range(menu.numberOfItems())]
    windows = [r if r is None else r[0] for r in T.menu_model(["glioma"], "pubmed")]
    assert mac == windows


# ── closing the window, and quitting ─────────────────────────────────────────
class _Page:
    def __init__(self, answer):
        self.answer, self.asked = answer, []

    def evaluate_js(self, js):
        self.asked.append(js)
        return self.answer


def _tray(answer=False):
    t = T.Tray(_Page(answer), icon_path=None, recent_searches=list,
               get_source=lambda: "pubmed", set_source=lambda k: None)
    t.hidden = 0
    t.hide = lambda: setattr(t, "hidden", t.hidden + 1)
    return t


def test_closing_hides_the_window_and_is_decided_off_the_gui_thread(monkeypatch):
    started = []

    class _Thread:
        def __init__(self, target, daemon=None): self.target = target
        def start(self): started.append(self.target)
    monkeypatch.setattr(T.threading, "Thread", _Thread)
    t = _tray()
    assert t.closing() is False                 # refused: it is hidden instead
    assert t.window.asked == []                 # not asked on the GUI thread
    monkeypatch.undo()                          # the page is asked on a real thread
    started[0]()
    assert t.hidden == 1


def test_closing_with_a_dialog_open_closes_only_the_dialog():
    t = _tray(answer=True)
    t._close_dialog_or_hide()
    assert t.hidden == 0 and "closeTopDialog()" in t.window.asked[0]


@pytest.mark.parametrize("reason", ["WindowsShutDown", "TaskManagerClosing", "ApplicationExitCall"])
def test_windows_ending_the_session_is_never_held_up(reason):
    """pywebview's handler has already asked `closing`, which said no; a close
    Windows itself asks for must go through all the same."""
    t = _tray()
    args = types.SimpleNamespace(CloseReason=reason, Cancel=True)
    t._form_closing(None, args)
    assert args.Cancel is False and t.quitting is True
    assert t.closing() is True                   # and nothing is asked any more


def test_a_click_on_the_close_button_is_not_let_through():
    t = _tray()
    args = types.SimpleNamespace(CloseReason="UserClosing", Cancel=True)
    t._form_closing(None, args)
    assert args.Cancel is True and t.quitting is False


def test_the_menu_items_do_what_they_say():
    t = _tray()
    done = []
    t.quick_search = lambda: done.append("search")
    t.run = lambda q: done.append(("run", q))
    t.show = lambda: done.append("show")
    t.quit = lambda: done.append("quit")
    t.save_source = lambda k: done.append(("source", k))
    for action, value in (("search", None), ("recent", "glioma"), ("source", "wos"),
                          ("open", None), ("quit", None)):
        t._do(action, value)
    assert done == ["search", ("run", "glioma"), ("source", "wos"), "show", "quit"]


def test_a_search_from_the_tray_runs_in_the_page():
    assert appmenu.search_js('he said "no"', "pubmed") == \
        'runSearchWithSource("he said \\"no\\"", "pubmed", 0)'


# ── the splash ───────────────────────────────────────────────────────────────
def test_flatten_follows_lines_and_curves():
    pts = S.flatten([("M", 0, 0), ("L", 10, 0), ("Q", 10, 10, 0, 10)], steps=4)
    assert pts[:2] == [(0, 0), (10, 0)] and pts[-1] == (0, 10) and len(pts) == 6


def test_prefix_cuts_a_line_by_length():
    line = [(0, 0), (10, 0), (10, 10)]
    assert S.prefix(line, 0.25) == [(0, 0), (5.0, 0.0)]
    assert S.prefix(line, 0.75) == [(0, 0), (10, 0), (10.0, 5.0)]
    assert S.prefix(line, 1.0) == line and S.prefix(line, 0.0) == [(0, 0)]


def test_the_flattened_paths_are_as_long_as_the_mac_measures_them():
    for _, _, pts, length in [(0, 0, p, n) for _, _, _, p, n in SW.STROKES]:
        measured = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:]))
        assert measured == pytest.approx(length, rel=1e-3)


def test_the_ease_is_core_animations():
    ease = S.bezier_ease(0.42, 0, 1, 1)                    # easeIn
    assert ease(0) == 0 and ease(1) == 1
    assert ease(0.5) == pytest.approx(0.3153, abs=2e-3)    # CSS ease-in at the midpoint
    linear = S.bezier_ease(0.25, 0.25, 0.75, 0.75)
    assert linear(0.3) == pytest.approx(0.3, abs=1e-6)


def test_the_pen_draws_in_the_mac_order_on_the_mac_clock():
    assert SW.pen_frame(0.0) == []                          # the pen has not set out
    done = S.BLOOM_START + S.BLOOM_TIME
    assert len(SW.pen_frame(done)) == len(SW.STROKES)
    assert all(shown == 1.0 for *_, shown in SW.pen_frame(done))
    first = SW.pen_frame(0.6)
    assert first and all(rgb == S.SAGE for _, rgb, _, _ in first)   # the book comes first


def test_reduced_motion_shows_the_drawing_whole_at_once():
    assert len(SW.pen_frame(0.0, reduced=True)) == len(SW.STROKES)
    assert SW.open_frame(0.0, reduced=True)[:3] == (1.0, 1.0, 1.0)


def test_the_window_opens_out_as_on_the_mac():
    disc, spread, art, pane = SW.open_frame(0.0)
    assert (disc, spread, art) == (0.0, 1.0, 1.0)
    disc, spread, art, pane = SW.open_frame(S.SPLASH_OUT)
    assert disc == 1.0 and spread == pytest.approx(2.4) and art == 0.0


class _Form:
    """The main window's WinForms form, as far as the hand-over touches it."""
    def __init__(self):
        self.Opacity, self.Visible, self.activated = 0.0, False, 0
    def Show(self): self.Visible = True
    def Activate(self): self.activated += 1


@pytest.fixture
def handing_over(monkeypatch):
    """The Windows splash's hand-over with its threads inline and no waiting."""
    monkeypatch.setattr(SW, "_on_gui_wait", lambda main, fn, timeout=2.0: fn())
    monkeypatch.setattr(SW.time, "sleep", lambda s: None)
    sp = SW.Splash()
    sp._form, sp._t0 = object(), SW.time.monotonic()
    sp._on_splash = lambda fn: fn()
    main = types.SimpleNamespace(native=_Form(), show=lambda: None)
    return sp, main


def test_the_windows_splash_opens_out_then_shows_the_window(handing_over, monkeypatch):
    sp, main = handing_over
    monkeypatch.setattr(SW, "_frame_of", lambda form: ((10, 20, 1280, 860), 31))
    sp.ready.set()
    sp.hand_over(main)
    assert sp._opening[1:] == ((10, 20, 1280, 860), 31)       # the disc grows into this frame
    assert sp._fade is not None                                 # and the splash fades off
    assert main.native.Visible and main.native.Opacity == 1.0 and main.native.activated


def test_a_windows_splash_that_never_came_up_still_shows_the_window(handing_over):
    sp, main = handing_over
    sp._form = None
    sp.ready.set()
    sp.hand_over(main)
    assert main.native.Visible and main.native.Opacity == 1.0 and sp._opening is None


def test_a_window_whose_frame_cannot_be_read_is_still_shown(handing_over, monkeypatch):
    sp, main = handing_over
    monkeypatch.setattr(SW, "_frame_of", lambda form: None)
    sp.ready.set()
    sp.hand_over(main)
    assert main.native.Visible and sp._opening is None


def test_a_page_that_never_says_ready_does_not_keep_the_window_shut(handing_over, monkeypatch):
    sp, main = handing_over
    monkeypatch.setattr(SW.S, "READY_TIMEOUT_S", 0.01)
    monkeypatch.setattr(SW, "_frame_of", lambda form: ((0, 0, 800, 600), 30))
    sp.hand_over(main)
    assert main.native.Visible


# ── library sign-ins ─────────────────────────────────────────────────────────
def test_a_sign_in_page_is_only_touched_on_https_inside_the_library():
    assert signins.page_domain("https://idp.unitn.it/login", INSTITUTIONS) == "unitn.it"
    assert signins.page_domain("http://idp.unitn.it/login", INSTITUTIONS) is None
    assert signins.page_domain("https://unitn.it.evil.com/", INSTITUTIONS) is None


def test_a_sign_in_message_is_kept_only_from_the_library():
    sent = json.dumps({"medsearchSignIn": {"u": "rn", "p": "pw"}})
    assert signins.windows_message(sent, "https://idp.unitn.it/x", INSTITUTIONS) == \
        ("unitn.it", "UniTN", "rn", "pw")
    assert signins.windows_message(sent, "https://elsewhere.org/", INSTITUTIONS) is False
    assert signins.windows_message(sent, "http://idp.unitn.it/x", INSTITUTIONS) is False
    # pywebview's own messages are not sign-ins: they go on to pywebview.
    assert signins.windows_message('["api", "{}", 1]', "https://idp.unitn.it/", INSTITUTIONS) is None
    assert signins.windows_message("not json", "https://idp.unitn.it/", INSTITUTIONS) is None


@pytest.fixture
def credman(monkeypatch):
    from test_secrets_store import FakeAdvapi
    fake = FakeAdvapi()
    monkeypatch.setattr(W, "API", fake)
    monkeypatch.setenv("MEDSEARCH_KEYCHAIN", "1")
    return fake


def test_windows_keeps_a_sign_in_in_credential_manager(credman):
    store = signins.CredentialStore()
    assert store.save("unitn.it", "rn", "pässword", "UniTN") is True
    user, data, _ = credman.items["MedSearch sign-in (unitn.it)"]
    assert (user, data.decode()) == ("rn", "pässword")
    assert store.load("unitn.it") == ("rn", "pässword")
    assert store.forget("unitn.it") is True and store.load("unitn.it") is None


def test_windows_sign_ins_stay_off_in_the_suite(credman, monkeypatch):
    monkeypatch.setenv("MEDSEARCH_KEYCHAIN", "0")
    assert signins.CredentialStore().save("unitn.it", "rn", "pw", "UniTN") is False
    assert credman.items == {}


_RUN_CAPTURE = """
const sent = [];
let onSubmit = null;
global.document = { addEventListener: (type, fn) => { onSubmit = fn; } };
global.window = %s;
eval(%s);
const field = (v) => ({ value: v });
const form = {
  querySelectorAll: () => [field('secret')],
  querySelector: () => field('rn'),
};
onSubmit({ target: form });
console.log(JSON.stringify(sent));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("window, via", [
    ("{ chrome: { webview: { postMessage: (m) => sent.push(['edge', m]) } } }", "edge"),
    ("{ webkit: { messageHandlers: { browserDelegate: { postMessage: (m) => sent.push(['webkit', m]) } } } }",
     "webkit"),
])
def test_the_sent_form_reaches_medsearch_on_either_system(window, via):
    script = _RUN_CAPTURE % (window, json.dumps(signins.CAPTURE))
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [[via, {"medsearchSignIn": {"u": "rn", "p": "secret"}}]]


# ── downloads ────────────────────────────────────────────────────────────────
def test_a_failed_download_says_why_in_words():
    assert AW.interrupted_because("NetworkFailed") == "Network failed."
    assert AW.interrupted_because("FileNoSpace") == "File no space."
    assert AW.interrupted_because("") == "It stopped for no given reason."


# ── the app on Windows ───────────────────────────────────────────────────────
def _on_windows(monkeypatch, **extra):
    """app.py's own `sys` as Windows'; the real one is left alone."""
    fake = types.SimpleNamespace(**{"platform": "win32", "executable": sys.executable, **extra})
    monkeypatch.setattr(A, "sys", fake)
    return fake


class FakeWinreg:
    """winreg over a dict of HKCU\\<key> -> {value: data}."""
    HKEY_CURRENT_USER, REG_SZ = "HKCU", 1

    def __init__(self):
        self.keys = {}

    class _Key:
        def __init__(self, values): self.values = values
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def CreateKey(self, root, path):
        return self._Key(self.keys.setdefault(path, {}))

    def OpenKey(self, root, path):
        if path not in self.keys:
            raise FileNotFoundError(path)
        return self._Key(self.keys[path])

    def QueryValueEx(self, key, name):
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, data):
        key.values[name] = data

    def DeleteValue(self, key, name):
        if name not in key.values:
            raise FileNotFoundError(name)
        del key.values[name]


@pytest.fixture
def registry(monkeypatch):
    reg = FakeWinreg()
    monkeypatch.setattr(A, "_winreg", lambda: reg)
    return reg


def test_open_at_login_on_windows_is_the_run_key(monkeypatch, registry):
    _on_windows(monkeypatch, frozen=True, executable=r"C:\Users\x\AppData\Local\Programs\MedSearch\MedSearch.exe")
    assert A._open_at_login_supported() is True
    assert A._open_at_login_enabled() is False
    A._set_open_at_login(True)
    command = registry.keys[A._RUN_KEY]["MedSearch"]
    assert command == r"C:\Users\x\AppData\Local\Programs\MedSearch\MedSearch.exe --background"
    assert A._open_at_login_enabled() is True
    A._set_open_at_login(False)
    assert "MedSearch" not in registry.keys[A._RUN_KEY]
    A._set_open_at_login(False)                     # already off: still fine


def test_a_path_with_spaces_is_quoted_in_the_run_key(monkeypatch, registry):
    _on_windows(monkeypatch, frozen=True, executable=r"C:\Program Files\Med Search\MedSearch.exe")
    A._set_run_key(True)
    assert registry.keys[A._RUN_KEY]["MedSearch"] == \
        '"C:\\Program Files\\Med Search\\MedSearch.exe" --background'


def test_settings_reports_the_windows_login_state(client, auth, monkeypatch, registry):
    _on_windows(monkeypatch)
    got = client.get("/settings", headers=auth, base_url=BASE).json
    assert (got["can_open_at_login"], got["open_at_login"]) == (True, False)
    registry.keys[A._RUN_KEY] = {"MedSearch": "x"}
    assert client.get("/settings", headers=auth, base_url=BASE).json["open_at_login"] is True


def test_a_clone_on_windows_restarts_without_a_console_window(monkeypatch, tmp_path):
    (tmp_path / "python.exe").write_text("")
    (tmp_path / "pythonw.exe").write_text("")
    monkeypatch.setattr(A.sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(A.os, "name", "nt")
    assert A._self_command("--relaunch")[0] == str(tmp_path / "pythonw.exe")
    (tmp_path / "pythonw.exe").unlink()             # a Python without one: the plain one
    assert A._self_command("--relaunch")[0] == str(tmp_path / "python.exe")


def test_a_second_launch_brings_the_window_back_through_the_tray(client, auth, monkeypatch):
    _on_windows(monkeypatch)
    shown = []
    monkeypatch.setattr(A, "_STATUSBAR", types.SimpleNamespace(show=lambda: shown.append(1)))
    monkeypatch.setattr(A, "_MAIN_WINDOW", object())
    assert client.post("/focus", headers=auth, base_url=BASE).json["ok"] is True
    assert shown == [1]


def test_a_console_without_emoji_never_stops_medsearch(tmp_path):
    """The first Windows build ended at its start message: its console's code
    page (cp1252) has no 🔬, and print() raised before the server was up. A
    Python of its own, with such a console and a scratch home, imports MedSearch
    and prints the same way."""
    env = dict(os.environ, PYTHONIOENCODING="cp1252", HOME=str(tmp_path),
               USERPROFILE=str(tmp_path), MEDSEARCH_KEYCHAIN="0")
    code = ("import app; "
            "print(f'\\n  🔬  MedSearch {app.LOCAL_VERSION}  —  native window → ok')")
    r = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(A.__file__).parent,
                       env=env, capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr.decode("cp1252", "replace")[-800:]
    assert b"MedSearch" in r.stdout


def test_a_windowed_app_with_no_console_gets_one_that_takes_anything(tmp_path):
    """The second Windows build: a windowed app has no stdout at all, pywebview
    then opens a null file in cp1252 in its place, and the same print ended it.
    MedSearch fills the gap first, with one that takes any character."""
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path), MEDSEARCH_KEYCHAIN="0")
    code = ("import sys; sys.stdout = None; sys.stderr = None; import app; "
            "assert sys.stdout is not None and sys.stderr is not None; "
            "print('\\n  🔬  MedSearch → ok'); print('🔬', file=sys.stderr); "
            "sys.__stdout__.write('survived')")
    r = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(A.__file__).parent,
                       env=env, capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-800:]
    assert r.stdout.endswith(b"survived")


def test_a_first_window_fits_a_small_screen():
    """The build machine's 1024 x 768 screen: 1280 wide put the close button off it."""
    size, minimum = A._screen_fit((1280, 860), (940, 640), (1024, 728))
    assert size == (1000, 704) and minimum == (940, 640)


def test_its_minimum_gives_way_on_a_smaller_screen_still():
    size, minimum = A._screen_fit((1280, 860), (940, 640), (800, 560))
    assert size == (776, 536) and minimum == (776, 536)


def test_a_big_screen_changes_nothing():
    assert A._screen_fit((1280, 860), (940, 640), (2560, 1400)) == ((1280, 860), (940, 640))


def test_where_the_screen_is_unknown_the_system_places_the_window(monkeypatch):
    monkeypatch.setattr(A, "_work_area", lambda: None)
    assert A._window_size((1280, 860), (940, 640)) == ((1280, 860), (940, 640), None)


def test_on_windows_the_window_is_fitted_and_centred_in_the_work_area(monkeypatch):
    """pywebview's own centring comes too late for Windows, which then put the
    window where it puts new ones: at 88 and at 137 px, past the right edge."""
    monkeypatch.setattr(A, "_work_area", lambda: (0, 0, 1024, 728))
    assert A._window_size((1280, 860), (940, 640)) == ((1000, 704), (940, 640), (12, 12))
    monkeypatch.setattr(A, "_work_area", lambda: (0, 48, 1920, 1032))     # taskbar at the top
    assert A._window_size((1280, 860), (940, 640)) == ((1280, 860), (940, 640), (320, 134))


def test_macos_keeps_windows_on_screen_by_itself(monkeypatch):
    monkeypatch.setattr(A, "sys", types.SimpleNamespace(platform="darwin"))
    assert A._work_area() is None


def test_the_page_speaks_of_windows_on_windows(client, monkeypatch):
    _on_windows(monkeypatch)
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert "onWindows:          true" in page
    assert "starts by the clock, in the notification area" in page
    assert "starts in the menu bar" not in page


def test_the_page_speaks_of_the_mac_elsewhere(client, monkeypatch):
    monkeypatch.setattr(A, "sys", types.SimpleNamespace(platform="darwin", executable=sys.executable))
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert "onWindows:          false" in page and "starts in the menu bar" in page


def test_the_installer_ships_what_windows_needs():
    root = Path(__file__).resolve().parent.parent
    spec = (root / "packaging" / "MedSearch.spec").read_text(encoding="utf-8")
    for needed in ('"tray"', '"splash_win"', "icon.ico"):
        assert needed in spec
    iss = (root / "packaging" / "MedSearch.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss                # no administrator
    assert 'Tasks: desktopicon' in iss and "Flags: unchecked" not in iss   # ticked (his choice)
    assert "RegDeleteValue(HKCU, RunKey, 'MedSearch')" in iss and A._RUN_VALUE == "MedSearch"
    Image = pytest.importorskip("PIL.Image")
    sizes = Image.open(root / "icon.ico").info["sizes"]
    assert {(16, 16), (32, 32), (256, 256)} <= set(sizes)

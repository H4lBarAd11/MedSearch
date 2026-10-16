"""Settings ▸ Uninstall MedSearch: in the installed app only; the login item
goes at once, the rest to the Trash (Windows: the Recycle Bin) once MedSearch
has quit; keys and library sign-ins are kept. Nothing is moved or run here:
the helpers' scripts are read, not run."""
import shlex
import sys
import types
from pathlib import Path

import pytest

import app as A
from conftest import BASE


@pytest.fixture
def mac_app(monkeypatch, tmp_path):
    """This process as the installed Mac app, in tmp_path/Applications, with a
    home of its own holding everything MedSearch may leave."""
    home = tmp_path / "home"
    bundle = tmp_path / "Applications" / "MedSearch.app"
    (bundle / "Contents" / "MacOS").mkdir(parents=True)
    monkeypatch.setattr(A.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(A, "CONFIG_DIR", home / ".medsearch")
    monkeypatch.setattr(A.sys, "frozen", True, raising=False)
    monkeypatch.setattr(A.sys, "executable", str(bundle / "Contents" / "MacOS" / "MedSearch"))
    monkeypatch.setattr(A, "_LOGIN_AGENT", home / "Library" / "LaunchAgents" / "com.halbarad.medsearch.plist")
    lib = home / "Library"
    for d in (home / ".medsearch", home / "medsearch_exports", lib / "WebKit" / A.APP_ID,
              lib / "Caches" / A.APP_ID, lib / "HTTPStorages" / A.APP_ID,
              lib / "WebKit" / "org.python.python", home / "Downloads"):
        d.mkdir(parents=True)
    (lib / "Preferences").mkdir(parents=True)
    (lib / "Preferences" / f"{A.APP_ID}.plist").write_text("")
    started = []
    monkeypatch.setattr(A.threading, "Thread",
                        lambda target, args, daemon: types.SimpleNamespace(start=lambda: started.append(args[0])))
    return types.SimpleNamespace(home=home, bundle=bundle, lib=lib, started=started)


@pytest.mark.skipif(sys.platform != "darwin", reason="the Mac's Trash")
def test_the_mac_app_trashes_itself_its_data_and_web_data_and_nothing_else(client, auth, mac_app, monkeypatch):
    monkeypatch.setattr(A, "_app_bundle_id", lambda: A.APP_ID)
    A._set_open_at_login(True)
    r = client.post("/uninstall", headers=auth, base_url=BASE)
    assert r.status_code == 200 and r.json == {"ok": True}
    assert not A._LOGIN_AGENT.exists()                       # the login item goes at once
    [(kind, script)] = mac_app.started
    assert kind == "mac"
    wait, rest = script.split("; sleep 1; ")
    assert wait == f"while kill -0 {A.os.getpid()} 2>/dev/null; do sleep 0.2; done"
    words = shlex.split(rest)
    assert words[:4] == ["/usr/bin/osascript", "-l", "JavaScript", "-e"]
    assert "trashItemAtURLResultingItemURLError" in words[4] and "Finder" not in words[4]
    lib = mac_app.lib
    assert words[5:] == [str(p) for p in (
        mac_app.bundle, mac_app.home / ".medsearch", mac_app.home / "medsearch_exports",
        lib / "WebKit" / A.APP_ID, lib / "Caches" / A.APP_ID, lib / "HTTPStorages" / A.APP_ID,
        lib / "Preferences" / f"{A.APP_ID}.plist")]
    # Never Downloads, never the web data every Python app shares, never a key.
    assert not any("Downloads" in w or "org.python.python" in w for w in words)


def test_no_web_page_can_uninstall_it(client, mac_app):
    # The window's token is on every request it makes; a page elsewhere has none.
    assert client.post("/uninstall", base_url=BASE).status_code == 403
    assert client.post("/uninstall", headers={"X-MedSearch-Token": "guess"}, base_url=BASE).status_code == 403
    assert mac_app.started == []


def test_a_path_with_quotes_and_spaces_reaches_the_trash_whole():
    script = A._mac_trash_script(42, [Path("/Users/x/it's a folder")])
    assert shlex.split(script.split("; sleep 1; ")[1])[-1] == "/Users/x/it's a folder"


@pytest.mark.skipif(sys.platform != "darwin", reason="the Mac's Trash")
@pytest.mark.parametrize("where, says", [("/Volumes/MedSearch", "running from its disk image"),
                                         ("locked", "can't change")])
def test_the_mac_app_says_when_it_cannot_remove_itself(client, auth, mac_app, monkeypatch, where, says):
    if where == "locked":
        monkeypatch.setattr(A.os, "access", lambda p, mode: False)
    else:
        monkeypatch.setattr(A.sys, "executable", f"{where}/MedSearch.app/Contents/MacOS/MedSearch")
    r = client.post("/uninstall", headers=auth, base_url=BASE)
    assert r.status_code == 400 and says in r.json["message"] and mac_app.started == []


def test_a_copy_run_from_source_has_nothing_to_uninstall(client, auth, monkeypatch):
    monkeypatch.setattr(A.sys, "frozen", False, raising=False)
    r = client.post("/uninstall", headers=auth, base_url=BASE)
    assert r.status_code == 400 and "source code" in r.json["message"]
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert "uninstallField" not in page


def test_the_installed_app_offers_it_in_settings(client, mac_app):
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert 'id="uninstallField"' in page and 'onclick="uninstallMedSearch()">Uninstall MedSearch…' in page


def test_windows_recycles_the_data_then_runs_setups_uninstaller(monkeypatch, tmp_path):
    folder = tmp_path / "Programs" / "MedSearch"
    folder.mkdir(parents=True)
    (folder / "unins000.exe").write_text("")
    monkeypatch.setattr(A, "sys", types.SimpleNamespace(platform="win32", frozen=True,
                                                         executable=str(folder / "MedSearch.exe")))
    home = tmp_path / "home"
    (home / ".medsearch").mkdir(parents=True)
    monkeypatch.setattr(A.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(A, "CONFIG_DIR", home / ".medsearch")
    kind, script = A._uninstall_plan("windows_app")
    assert kind == "windows"
    assert script.startswith(f"Wait-Process -Id {A.os.getpid()} -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1; ")
    assert f"foreach ($p in @('{home / '.medsearch'}'))" in script        # the exports folder doesn't exist
    # Folders and files alike go to the Recycle Bin; nothing is deleted outright.
    assert "DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin')" in script
    assert "DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin')" in script
    assert "DeletePermanently" not in script
    assert script.endswith(f"& '{folder / 'unins000.exe'}' /VERYSILENT /SUPPRESSMSGBOXES /NORESTART")


def test_a_windows_path_with_an_apostrophe_is_quoted_for_powershell():
    script = A._windows_uninstall_script(7, [Path("C:/Users/O'Neil/.medsearch")], Path("C:/P/unins000.exe"))
    assert "@('C:/Users/O''Neil/.medsearch')" in script


def test_windows_without_setups_uninstaller_says_where_to_go(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "sys", types.SimpleNamespace(platform="win32", frozen=True,
                                                         executable=str(tmp_path / "MedSearch.exe")))
    with pytest.raises(A.UpdateRefused, match="Settings ▸ Apps"):
        A._uninstall_plan("windows_app")

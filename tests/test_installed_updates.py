"""Updates for the installers' MedSearch.

Nothing here reaches GitHub or touches an installed MedSearch: the Release is
faked, and every file the updates move lives in a temporary folder. The Mac's
own tools (hdiutil, ditto, codesign, sh) are real where the test says so.
"""
import os
import plistlib
import shutil
import subprocess
import sys
import types
import urllib.error
from pathlib import Path

import pytest

import app as A
from conftest import BASE

ON_MAC = sys.platform == "darwin" and shutil.which("hdiutil") is not None


def _published(monkeypatch, version, released=True):
    """GitHub, faked: main holds `version`; its installer is up or not yet."""
    files = {"VERSION": version + "\n", "CHANGELOG.md": f"## {version}\n\n- Something new.\n"}
    monkeypatch.setattr(A, "_published_commit", lambda: "c0ffee")
    monkeypatch.setattr(A, "_github_file", lambda name, commit: files.get(name))
    asked = []
    monkeypatch.setattr(A, "_release_published",
                        lambda v: asked.append(v) or released)
    return asked


def _kind(monkeypatch, kind, system="darwin"):
    monkeypatch.setattr(A, "_install_kind", lambda: kind)
    monkeypatch.setattr(A, "sys", types.SimpleNamespace(platform=system, executable=sys.executable))


def _check(client, auth):
    return client.get("/update/check", headers=auth, base_url=BASE).json


# ── the check ────────────────────────────────────────────────────────────────
def test_an_installed_app_is_offered_a_version_once_its_installer_is_up(client, auth, monkeypatch):
    _kind(monkeypatch, "mac_app")
    asked = _published(monkeypatch, "9.9")
    r = _check(client, auth)
    assert (r["kind"], r["update_available"], r["can_apply"]) == ("mac_app", True, True)
    assert r["changes"] == ["Something new."] and asked == ["9.9"]


def test_an_installed_app_is_not_offered_a_version_still_being_built(client, auth, monkeypatch):
    _kind(monkeypatch, "windows_app", system="win32")
    _published(monkeypatch, "9.9", released=False)
    r = _check(client, auth)
    assert r["update_available"] is False and r["changes"] == []


def test_an_installed_app_does_not_ask_about_a_release_it_already_runs(client, auth, monkeypatch):
    _kind(monkeypatch, "mac_app")
    asked = _published(monkeypatch, A.get_local_version())
    assert _check(client, auth)["update_available"] is False
    assert asked == []


def test_an_update_put_off_today_is_not_offered_by_itself(client, auth, monkeypatch):
    _kind(monkeypatch, "mac_app")
    _published(monkeypatch, "9.9")
    A.CONFIG["update_later"] = {"version": "9.9", "day": A._today()}
    assert _check(client, auth)["deferred"] is True


def test_run_from_source_it_says_it_cannot_update_itself(client, auth, monkeypatch):
    """The code's folder belongs to whoever keeps it: no git, no Release."""
    _kind(monkeypatch, "source")
    asked = _published(monkeypatch, "9.9")
    r = _check(client, auth)
    assert r["update_available"] is True and r["can_apply"] is False and asked == []
    r = client.post("/update/apply", headers=auth, base_url=BASE).json
    assert r["ok"] is False and "can't update itself" in r["message"]


def test_what_kind_of_install_this_is(monkeypatch):
    assert A._install_kind() == "source"
    monkeypatch.setattr(A.sys, "frozen", True, raising=False)
    assert A._install_kind() == {"darwin": "mac_app", "win32": "windows_app"}.get(sys.platform, "source")


# ── the Release ──────────────────────────────────────────────────────────────
def test_each_system_gets_its_own_installer():
    assert A._release_url("1.31", "darwin").endswith("/releases/download/v1.31/MedSearch-1.31-mac.dmg")
    assert A._release_url("1.31", "win32").endswith("/releases/download/v1.31/MedSearch-1.31-Setup.exe")


@pytest.mark.parametrize("answer, expected", [
    (200, True),
    (urllib.error.HTTPError("u", 404, "Not Found", {}, None), False),
    (urllib.error.HTTPError("u", 503, "Unavailable", {}, None), None),
    (OSError("no network"), None),
])
def test_whether_the_installer_is_up_is_asked_without_downloading_it(monkeypatch, answer, expected):
    asked = []

    class _Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def urlopen(req, timeout=None):
        asked.append((req.get_method(), req.full_url))
        if isinstance(answer, Exception):
            raise answer
        return _Response()
    monkeypatch.setattr(A.urllib.request, "urlopen", urlopen)
    assert A._release_published("1.31") is expected
    assert asked == [("HEAD", A._release_url("1.31"))]


# ── putting the new app in place ─────────────────────────────────────────────
def _open_recorder(tmp_path):
    """A stand-in for macOS's `open`, first on the PATH, noting what it opened."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "open").write_text(f'#!/bin/sh\necho "$@" >> "{tmp_path}/opened"\n')
    (bin_ / "open").chmod(0o755)
    return dict(os.environ, PATH=f"{bin_}:{os.environ['PATH']}")


def _app(path, version="1.0"):
    (path / "Contents").mkdir(parents=True)
    (path / "Contents" / "v").write_text(version)
    return path


@pytest.mark.skipif(os.name != "posix", reason="the swap is a shell's")
def test_the_swap_puts_the_new_app_in_place_and_opens_it(tmp_path):
    target = _app(tmp_path / "Applications" / "MedSearch.app", "old")
    staged = _app(tmp_path / "Applications" / ".MedSearch-update.app", "new")
    env = _open_recorder(tmp_path)
    subprocess.run(["/bin/sh", "-c", A._swap_script(99999999, staged, target)], env=env, check=True)
    assert (target / "Contents" / "v").read_text() == "new"
    assert not staged.exists() and not (target.parent / ".MedSearch-old.app").exists()
    assert (tmp_path / "opened").read_text().strip() == str(target)


@pytest.mark.skipif(os.name != "posix", reason="the swap is a shell's")
def test_the_swap_puts_the_old_app_back_if_the_new_one_is_gone(tmp_path):
    target = _app(tmp_path / "MedSearch.app", "old")
    env = _open_recorder(tmp_path)
    subprocess.run(["/bin/sh", "-c", A._swap_script(99999999, tmp_path / "missing.app", target)],
                   env=env, check=True)
    assert (target / "Contents" / "v").read_text() == "old"


@pytest.mark.skipif(os.name != "posix", reason="the swap is a shell's")
def test_the_swap_into_an_empty_place_just_moves_it_there(tmp_path):
    staged = _app(tmp_path / ".MedSearch-update.app", "new")
    env = _open_recorder(tmp_path)
    subprocess.run(["/bin/sh", "-c", A._swap_script(99999999, staged, tmp_path / "MedSearch.app")],
                   env=env, check=True)
    assert (tmp_path / "MedSearch.app" / "Contents" / "v").read_text() == "new"


@pytest.mark.skipif(os.name != "posix", reason="the swap is a shell's")
def test_the_swap_waits_for_medsearch_to_quit(tmp_path):
    target = _app(tmp_path / "MedSearch.app", "old")
    staged = _app(tmp_path / ".MedSearch-update.app", "new")
    running = subprocess.Popen(["sleep", "30"])
    try:
        swap = subprocess.Popen(["/bin/sh", "-c", A._swap_script(running.pid, staged, target)],
                                env=_open_recorder(tmp_path))
        with pytest.raises(subprocess.TimeoutExpired):
            swap.wait(timeout=0.6)
        assert (target / "Contents" / "v").read_text() == "old"     # not while it runs
    finally:
        running.kill()
        running.wait()
    swap.wait(timeout=10)
    assert (target / "Contents" / "v").read_text() == "new"


def test_windows_setup_runs_quietly_and_reopens_medsearch():
    cmd = A._setup_command(r"C:\Temp\MedSearch-1.31-Setup.exe")
    assert cmd[0].endswith("Setup.exe")
    assert {"/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1"} <= set(cmd)
    iss = (Path(A.__file__).parent / "packaging" / "MedSearch.iss").read_text(encoding="utf-8")
    assert "{param:RELAUNCH|0}" in iss and "Check: Relaunching" in iss


# ── the Mac's .dmg ───────────────────────────────────────────────────────────
def _signed_app(root, version, bundle_id=A.APP_ID, tamper=False):
    """A small signed app like the Release's, in `root`/MedSearch.app."""
    app = root / "MedSearch.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    with open(app / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump({"CFBundleIdentifier": bundle_id, "CFBundleShortVersionString": version,
                       "CFBundleExecutable": "MedSearch", "CFBundlePackageType": "APPL"}, fh)
    exe = app / "Contents" / "MacOS" / "MedSearch"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    subprocess.run(["codesign", "-s", "-", "-f", str(app)], check=True, capture_output=True)
    if tamper:
        exe.write_text("#!/bin/sh\necho changed\n")
    return root


@pytest.fixture
def disk_images(monkeypatch, tmp_path):
    """hdiutil attach and detach stood in for, over folders standing for .dmgs:
    an image takes seconds to make and to open, and one real one is enough
    (test_a_real_disk_image_is_staged). ditto and codesign stay real."""
    real = A.subprocess.run
    images = {}

    def run(argv, **kw):
        if argv[:2] == ["hdiutil", "attach"]:
            shutil.copytree(images[argv[-1]], argv[argv.index("-mountpoint") + 1], symlinks=True)
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:2] == ["hdiutil", "detach"]:
            shutil.rmtree(argv[2], ignore_errors=True)
            return subprocess.CompletedProcess(argv, 0, "", "")
        return real(argv, **kw)
    monkeypatch.setattr(A.subprocess, "run", run)

    def make(version, **kw):
        name = str(tmp_path / f"image-{len(images)}.dmg")
        images[name] = _signed_app(tmp_path / f"src-{len(images)}", version, **kw)
        return name
    return make


@pytest.fixture
def applications(tmp_path):
    folder = tmp_path / "Applications"
    folder.mkdir()
    return folder


@pytest.mark.skipif(not ON_MAC, reason="the Mac's disk images")
def test_a_real_disk_image_is_staged(tmp_path, applications):
    src = _signed_app(tmp_path / "src", "9.9")
    dmg = tmp_path / "MedSearch-9.9-mac.dmg"
    subprocess.run(["hdiutil", "create", "-volname", "MedSearch", "-srcfolder", str(src),
                    "-format", "UDZO", "-ov", str(dmg)], check=True, capture_output=True)
    staged = A._stage_mac_app(dmg, applications, "9.9")
    assert staged == applications / ".MedSearch-update.app"
    with open(staged / "Contents" / "Info.plist", "rb") as fh:
        assert plistlib.load(fh)["CFBundleShortVersionString"] == "9.9"
    mounts = subprocess.run(["hdiutil", "info"], capture_output=True, text=True).stdout
    assert str(dmg) not in mounts                                # and detached again


@pytest.mark.skipif(not ON_MAC, reason="codesign")
def test_a_download_of_another_version_or_app_is_refused(disk_images, applications):
    with pytest.raises(A.UpdateRefused, match="not MedSearch 9.9"):
        A._stage_mac_app(disk_images("9.8"), applications, "9.9")
    with pytest.raises(A.UpdateRefused, match="not MedSearch 9.9"):
        A._stage_mac_app(disk_images("9.9", bundle_id="com.example.other"), applications, "9.9")
    assert not (applications / ".MedSearch-update.app").exists()


@pytest.mark.skipif(not ON_MAC, reason="codesign")
def test_a_damaged_download_is_refused(disk_images, applications):
    with pytest.raises(A.UpdateRefused, match="damaged"):
        A._stage_mac_app(disk_images("9.9", tamper=True), applications, "9.9")
    assert not (applications / ".MedSearch-update.app").exists()


@pytest.mark.skipif(not ON_MAC, reason="codesign")
def test_a_leftover_from_an_earlier_try_is_replaced(disk_images, applications):
    (applications / ".MedSearch-update.app" / "stale").mkdir(parents=True)
    staged = A._stage_mac_app(disk_images("9.9"), applications, "9.9")
    assert not (staged / "stale").exists()


# ── the installed app's Update now ───────────────────────────────────────────
@pytest.fixture
def no_leaving(monkeypatch):
    """What would replace this process and quit: noted instead."""
    plans = []
    monkeypatch.setattr(A, "_replace_and_exit", plans.append)

    class _Thread:
        def __init__(self, target, args=(), daemon=None): self.run = lambda: target(*args)
        def start(self): self.run()
    monkeypatch.setattr(A.threading, "Thread", _Thread)
    return plans


def _installed_mac(monkeypatch, bundle):
    monkeypatch.setattr(A, "_install_kind", lambda: "mac_app")
    monkeypatch.setattr(A, "_this_bundle", lambda: bundle)
    monkeypatch.setattr(A, "_download", lambda url, dest: Path(dest).write_bytes(b"dmg"))


def test_update_now_stages_the_mac_app_and_restarts(client, auth, monkeypatch, tmp_path, no_leaving):
    bundle = tmp_path / "Applications" / "MedSearch.app"
    bundle.mkdir(parents=True)
    _installed_mac(monkeypatch, bundle)
    _published(monkeypatch, "9.9")
    monkeypatch.setattr(A, "_stage_mac_app", lambda dmg, folder, v: folder / ".MedSearch-update.app")
    r = client.post("/update/apply", headers=auth, base_url=BASE).json
    assert r == {"ok": True, "restarting": True, "new_version": "9.9"}
    assert no_leaving == [("mac", bundle.parent / ".MedSearch-update.app", bundle)]


def test_update_now_is_refused_while_the_installer_is_being_built(client, auth, monkeypatch,
                                                                  tmp_path, no_leaving):
    _installed_mac(monkeypatch, tmp_path / "MedSearch.app")
    _published(monkeypatch, "9.9", released=False)
    r = client.post("/update/apply", headers=auth, base_url=BASE).json
    assert r["ok"] is False and "being prepared" in r["message"] and no_leaving == []


@pytest.mark.skipif(sys.platform == "win32", reason="the Mac's paths")
@pytest.mark.parametrize("where", ["/private/var/folders/x/AppTranslocation/y/d/MedSearch.app",
                                   "/Volumes/MedSearch/MedSearch.app"])
def test_an_app_run_from_its_download_is_told_to_go_to_applications(client, auth, monkeypatch,
                                                                     where, no_leaving):
    _installed_mac(monkeypatch, Path(where))
    _published(monkeypatch, "9.9")
    r = client.post("/update/apply", headers=auth, base_url=BASE).json
    assert r["ok"] is False and "Drag MedSearch into Applications" in r["message"]
    assert no_leaving == []


def test_an_app_this_user_may_not_replace_says_so(client, auth, monkeypatch, tmp_path, no_leaving):
    _installed_mac(monkeypatch, tmp_path / "MedSearch.app")
    _published(monkeypatch, "9.9")
    monkeypatch.setattr(A.os, "access", lambda p, mode: False)
    r = client.post("/update/apply", headers=auth, base_url=BASE).json
    assert r["ok"] is False and "can't replace itself" in r["message"] and no_leaving == []


def test_update_now_on_windows_downloads_setup_and_hands_over_to_it(client, auth, monkeypatch,
                                                                     no_leaving):
    monkeypatch.setattr(A, "_install_kind", lambda: "windows_app")
    fetched = []
    monkeypatch.setattr(A, "_download", lambda url, dest: fetched.append((url, dest)))
    monkeypatch.setattr(A, "sys", types.SimpleNamespace(platform="win32", executable=sys.executable))
    _published(monkeypatch, "9.9")
    r = client.post("/update/apply", headers=auth, base_url=BASE).json
    assert r["restarting"] is True
    url, dest = fetched[0]
    assert url.endswith("/v9.9/MedSearch-9.9-Setup.exe") and dest.name == "MedSearch-9.9-Setup.exe"
    assert no_leaving == [("windows", dest)]

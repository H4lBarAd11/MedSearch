"""What an article window does with new tabs and files. The rules are tested here;
the real WebKit part runs in tests/webkit/article_windows_page.py.
"""
import subprocess
import sys
from pathlib import Path

import pytest

import article_windows as W

ROOT = Path(__file__).resolve().parent.parent
PDF = b"%PDF-1.4\n%%EOF\n"


@pytest.mark.parametrize("suggested,name", [
    ("paper.pdf", "paper.pdf"),
    ("../../Library/LaunchAgents/evil.plist", "evil.plist"),
    ("..\\..\\x.pdf", "x.pdf"),
    (".hidden", "hidden"),
    ("", "download"),
    ("   ", "download"),
    ("a:b\"c.pdf", "abc.pdf"),
    ("line\nbreak.pdf", "linebreak.pdf"),
])
def test_a_suggested_name_is_only_ever_a_plain_name(suggested, name):
    assert W.safe_name(suggested) == name


def test_a_download_never_replaces_a_file_already_there(tmp_path):
    assert W.free_path(tmp_path, "paper.pdf") == tmp_path / "paper.pdf"
    (tmp_path / "paper.pdf").write_bytes(b"x")
    assert W.free_path(tmp_path, "paper.pdf") == tmp_path / "paper (2).pdf"
    (tmp_path / "paper (2).pdf").write_bytes(b"x")
    assert W.free_path(tmp_path, "paper.pdf") == tmp_path / "paper (3).pdf"


def test_a_pdf_is_known_by_its_content_not_its_name(tmp_path):
    (tmp_path / "a.bin").write_bytes(PDF)
    (tmp_path / "b.pdf").write_bytes(b"<html>sign in</html>")
    assert W.is_pdf(tmp_path / "a.bin") is True
    assert W.is_pdf(tmp_path / "b.pdf") is False
    assert W.is_pdf(tmp_path / "missing.pdf") is False


def test_a_pdf_without_the_pdf_ending_gets_it(tmp_path):
    (tmp_path / "download").write_bytes(PDF)
    path, pdf = W.finished(tmp_path / "download")
    assert pdf and path == tmp_path / "download.pdf" and path.read_bytes() == PDF


def test_a_finished_pdf_keeps_its_name_and_other_files_are_left_alone(tmp_path):
    (tmp_path / "paper.PDF").write_bytes(PDF)
    (tmp_path / "data.zip").write_bytes(b"PK")
    assert W.finished(tmp_path / "paper.PDF") == (tmp_path / "paper.PDF", True)
    assert W.finished(tmp_path / "data.zip") == (tmp_path / "data.zip", False)


@pytest.mark.parametrize("url,method,window", [
    ("https://www.nejm.org/doi/pdf/10.1056/x", "GET", True),
    ("http://doi-org.ezp.biblio.unitn.it/10.1/x", "get", True),
    ("https://www.nejm.org/doi/pdf/10.1056/x", "POST", False),   # a form's reply
    ("", "GET", False),                                            # window.open('')
    ("about:blank", "GET", False),
    ("blob:https://site/1234", "GET", False),
    ("javascript:alert(1)", "GET", False),
    ("file:///etc/passwd", "GET", False),
])
def test_which_new_tabs_open_as_a_medsearch_window(url, method, window):
    assert W.opens_as_window(url, method) is window


@pytest.mark.parametrize("url,here", [
    ("blob:https://site/1234", True), ("data:application/pdf;base64,JVBERi0=", True),
    ("about:blank", False), ("javascript:alert(1)", False), ("https://x.org", False),
])
def test_only_what_the_page_made_itself_is_shown_in_place(url, here):
    assert W.loads_in_place(url) is here


def _webkit():
    if sys.platform != "darwin":
        return False
    try:
        import WebKit  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _webkit(), reason="needs macOS WebKit")
def test_a_real_page_keeps_its_tabs_and_files_in_medsearch():
    r = subprocess.run([sys.executable, "-B", str(ROOT / "tests" / "webkit" / "article_windows_page.py")],
                       capture_output=True, text=True, timeout=180, cwd=ROOT)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "ALL PASS" in r.stdout


def test_medsearch_installs_it_for_article_windows_only():
    app = (ROOT / "app.py").read_text()
    assert "article_windows.install(lambda w: w is not _MAIN_WINDOW, _open_article_window)" in app

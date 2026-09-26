"""The HTTP surface: the request guard, the search stream, settings, export,
the assistant, and the PDF proxy's allowlist."""
import json

import pytest

import app as A
from conftest import BASE, article, sse_events


# ── Request guard ───────────────────────────────────────────────────────────

def test_a_request_without_the_token_is_refused(client):
    assert client.post("/update/apply", base_url=BASE).status_code == 403
    assert client.get("/synthesis", base_url=BASE).status_code == 403


def test_a_foreign_hostname_is_refused_even_on_open_routes(client):
    assert client.get("/ping", base_url="http://attacker.example:5050").status_code == 403


def test_the_page_and_ping_need_no_token(client):
    assert client.get("/ping", base_url=BASE).json["app"] == "medsearch"
    page = client.get("/", base_url=BASE)
    assert page.status_code == 200
    assert A.APP_TOKEN in page.get_data(as_text=True)
    assert page.headers["X-Frame-Options"] == "DENY"


def test_eventsource_urls_may_carry_the_token_as_a_parameter(client):
    r = client.get(f"/synthesis?t={A.APP_TOKEN}", base_url=BASE)
    assert r.status_code == 200


def test_a_malformed_json_body_is_not_a_server_error(client, auth):
    r = client.post("/export", data="not json", headers=auth, base_url=BASE)
    assert r.status_code == 400          # "no articles", not a 500


# ── Search stream ───────────────────────────────────────────────────────────

def _fake_sources(monkeypatch, results, calls=None):
    """Replace every search function with one returning canned results and
    recording the offset it was asked for."""
    def make(key):
        def run(query, max_r, y_from, y_to, **kw):
            if calls is not None:
                calls.append((key, kw.get("offset")))
            return [dict(a) for a in results.get(key, [])], 0
        return run
    table = [(k, label, make(k), strict) for k, label, _fn, strict in A.SOURCES]
    monkeypatch.setattr(A, "SOURCES", table)
    monkeypatch.setattr(A, "get_mesh", lambda q: [])
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)


def _search(client, auth, **body):
    payload = {"query": "glioma", "sources": ["pubmed", "cochrane"], "max_results": 10, **body}
    return sse_events(client.post("/search_stream", json=payload, headers=auth, base_url=BASE))


def test_a_paper_in_two_sources_is_labelled_by_the_higher_priority_one(client, auth, monkeypatch):
    same = article(title="Cochrane review of gliomas", doi="10.1002/14651858.CD1")
    _fake_sources(monkeypatch, {"pubmed": [dict(same, source="PubMed")],
                                "cochrane": [dict(same, source="Cochrane")]})
    arts = [e for e in _search(client, auth) if e["type"] == "article"]
    assert [a["source"] for a in arts] == ["Cochrane"]


def test_indices_are_contiguous_across_parallel_sources(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {
        "pubmed":   [article(title=f"pm {i}") for i in range(3)],
        "cochrane": [article(title=f"co {i}") for i in range(2)]})
    arts = [e["article"] for e in _search(client, auth) if e["type"] == "article"]
    assert [a["_idx"] for a in arts] == list(range(5))


def test_load_more_asks_each_source_for_its_own_next_batch(client, auth, monkeypatch):
    calls = []
    _fake_sources(monkeypatch, {"pubmed": [article(title="x")]}, calls)
    _search(client, auth)
    calls.clear()
    _search(client, auth, load_more=True)
    # Each source continues from ITS OWN position (10), not from the number
    # of results shown across all sources.
    assert sorted(calls) == [("cochrane", 10), ("pubmed", 10)]


def test_load_more_for_a_different_query_is_refused(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {})
    _search(client, auth)
    events = _search(client, auth, query="something else", load_more=True)
    assert events[0]["type"] == "error"


def test_a_source_needing_a_key_reports_it_instead_of_returning_nothing(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {})
    events = _search(client, auth, sources=["scopus"])
    errs = [e for e in events if e["type"] == "source_error"]
    assert errs and "Scopus API key" in errs[0]["text"]


def test_a_failing_source_does_not_stop_the_others(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {"cochrane": [article(title="ok")]})
    def boom(*a, **k):
        raise RuntimeError("PubMed didn't respond.")
    monkeypatch.setattr(A, "SOURCES", [(k, l, boom if k == "pubmed" else f, s)
                                       for k, l, f, s in A.SOURCES])
    events = _search(client, auth)
    assert any(e["type"] == "source_error" and "PubMed" in e["text"] for e in events)
    assert [e["article"]["title"] for e in events if e["type"] == "article"] == ["ok"]
    assert events[-1]["type"] == "done"


def test_history_survives_a_restart(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {})
    _search(client, auth, query="first")
    _search(client, auth, query="second")
    _search(client, auth, query="first")
    assert A._load_history() == ["second", "first"]


# ── Settings ────────────────────────────────────────────────────────────────

def test_a_blank_field_keeps_the_saved_key_and_clear_removes_it(client, auth):
    client.post("/settings", json={"pubmed_api_key": "abcd1234"}, headers=auth, base_url=BASE)
    client.post("/settings", json={"pubmed_api_key": ""}, headers=auth, base_url=BASE)
    assert A.CONFIG["pubmed_api_key"] == "abcd1234"
    client.post("/settings", json={"clear": ["pubmed_api_key"]}, headers=auth, base_url=BASE)
    assert A.CONFIG["pubmed_api_key"] == ""


def test_clear_cannot_touch_non_secret_settings(client, auth):
    A.CONFIG["default_source"] = "pubmed"
    client.post("/settings", json={"clear": ["default_source"]}, headers=auth, base_url=BASE)
    assert A.CONFIG["default_source"] == "pubmed"


def test_saved_searches_keep_their_sort_order(client, auth):
    r = client.post("/saved", json={"query": "q", "sort": "date"}, headers=auth, base_url=BASE)
    assert r.json["saved"][-1]["sort"] == "date"


# ── Export selection ────────────────────────────────────────────────────────

def test_export_covers_only_the_filtered_articles_when_given(client, auth, tmp_path, monkeypatch):
    monkeypatch.setattr(A.Path, "home", staticmethod(lambda: tmp_path))
    A.SESSION["articles"] = [article(title=f"Paper {i}") for i in range(4)]
    A.SESSION["query"] = "q"
    r = client.post("/export", json={"format": "md", "indices": [1, 3, 99, "x"]},
                    headers=auth, base_url=BASE)
    assert r.json["count"] == 2
    text = open(r.json["paths"][0], encoding="utf-8").read()
    assert "Paper 1" in text and "Paper 3" in text and "Paper 0" not in text


def test_export_without_indices_covers_everything(client, auth, tmp_path, monkeypatch):
    monkeypatch.setattr(A.Path, "home", staticmethod(lambda: tmp_path))
    A.SESSION["articles"] = [article(title=f"Paper {i}") for i in range(3)]
    r = client.post("/export", json={"format": "bib"}, headers=auth, base_url=BASE)
    assert r.json["count"] == 3


# ── Assistant ───────────────────────────────────────────────────────────────

def test_the_conversation_sent_to_the_api_always_opens_with_a_user_turn(client, auth, monkeypatch):
    sent = {}
    def fake_stream(messages, query, articles):
        sent["messages"] = messages
        yield A._sse({"type": "done"})
    monkeypatch.setattr(A, "assistant_chat_stream", fake_stream)
    turns = []
    for i in range(4):
        turns += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]
    turns.append({"role": "user", "content": "last"})
    client.post("/assistant/chat", json={"messages": turns}, headers=auth, base_url=BASE).get_data()
    assert sent["messages"][0]["role"] == "user"
    assert sent["messages"][-1]["content"] == "last"


def test_malformed_chat_messages_are_dropped_not_crashed_on(client, auth):
    r = client.post("/assistant/chat", json={"messages": ["junk", None, {"role": "system"}]},
                    headers=auth, base_url=BASE)
    assert sse_events(r)[0]["type"] == "error"


# ── Claude streaming ────────────────────────────────────────────────────────

class _FakeStream:
    def __init__(self, lines):
        self.lines = [l.encode() for l in lines]
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def __iter__(self):
        return iter(self.lines)


def _stream(monkeypatch, lines):
    A.CONFIG["anthropic_api_key"] = "sk-test"
    monkeypatch.setattr(A, "_anthropic_open", lambda payload, timeout: _FakeStream(lines))
    return [json.loads(c[6:]) for c in A.claude_stream({"model": A.MODEL_MAIN, "messages": []})]


def test_only_text_deltas_become_chunks(monkeypatch):
    evs = _stream(monkeypatch, [
        'data: {"type":"message_start"}',
        'data: {"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"hmm"}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}',
        'data: {"type":"message_stop"}'])
    assert evs == [{"type": "chunk", "text": "Hello"}, {"type": "done"}]


def test_a_refusal_is_reported(monkeypatch):
    evs = _stream(monkeypatch, ['data: {"type":"message_delta","delta":{"stop_reason":"refusal"}}'])
    assert evs[0]["type"] == "error"


def test_no_key_is_an_error_not_a_crash():
    evs = [json.loads(c[6:]) for c in A.claude_stream({"messages": []})]
    assert evs[0]["type"] == "error" and evs[-1]["type"] == "done"


def test_ai_switched_off_refuses_even_with_a_key():
    A.CONFIG.update(anthropic_api_key="sk-test", ai_enabled=False)
    evs = [json.loads(c[6:]) for c in A.claude_stream({"messages": []})]
    assert "turned off" in evs[0]["text"]


def test_one_liners_use_the_fast_model(monkeypatch):
    A.CONFIG["anthropic_api_key"] = "sk-test"
    seen = {}
    monkeypatch.setattr(A, "claude_text", lambda payload, timeout=30, **kw: seen.update(payload) or "x")
    A.ai_oneliner("t", "abstract")
    assert seen["model"] == A.MODEL_FAST


# ── PDF proxy allowlist ─────────────────────────────────────────────────────

def test_the_proxy_refuses_a_url_that_merely_contains_a_known_doi(client, auth):
    A.SESSION["articles"] = [article(doi="10.1/known", access_kind="doi",
                                     access_link="https://doi.org/10.1/known")]
    for url in ("http://127.0.0.1:8080/?x=10.1/known", "https://evil.example/10.1/known"):
        r = client.get("/pdf_proxy", query_string={"url": url}, headers=auth, base_url=BASE)
        assert r.status_code == 403, url


def test_the_proxy_accepts_the_library_proxy_form_of_a_known_doi(client, auth, monkeypatch):
    A.CONFIG["institution_proxies"] = [{"label": "UniTN", "url": "https://ezp.biblio.unitn.it"}]
    A.SESSION["articles"] = [article(doi="10.1/known")]
    monkeypatch.setattr(A, "_fetch_url_bytes", lambda url, **k: (b"%PDF-1.4 x", "application/pdf"))
    r = client.get("/pdf_proxy", query_string={"url": "https://doi-org.ezp.biblio.unitn.it/10.1/known"},
                   headers=auth, base_url=BASE)
    assert r.status_code == 200 and r.mimetype == "application/pdf"


def test_local_addresses_are_private():
    for host in ("localhost", "127.0.0.1", "10.0.0.5", "192.168.1.20", "printer.local", None):
        assert A._is_private_host(host), host
    assert not A._is_private_host("93.184.216.34")


# ── The PDF viewer's Save ───────────────────────────────────────────────────
# Save used to be a download link in the page, which showed the PDF in place
# of MedSearch's window (26 Sep); the page now hands the bytes to /save_pdf.

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "DOWNLOADS_DIR", tmp_path / "Downloads")
    return tmp_path / "Downloads"


def _save(client, auth, body, name="recognition_of_white_matter.pdf"):
    return client.post(f"/save_pdf?name={name}", data=body, headers=auth, base_url=BASE,
                       content_type="application/pdf")


def test_save_puts_the_pdf_in_downloads_under_the_article_name(client, auth, downloads):
    r = _save(client, auth, PDF)
    assert r.status_code == 200 and r.json == {"name": "recognition_of_white_matter.pdf"}
    assert (downloads / "recognition_of_white_matter.pdf").read_bytes() == PDF


def test_save_never_replaces_a_file_already_there(client, auth, downloads):
    downloads.mkdir()
    (downloads / "paper.pdf").write_bytes(b"already here")
    assert _save(client, auth, PDF, "paper.pdf").json["name"] == "paper (2).pdf"
    assert _save(client, auth, PDF, "paper.pdf").json["name"] == "paper (3).pdf"
    assert (downloads / "paper.pdf").read_bytes() == b"already here"


def test_save_keeps_the_name_a_plain_pdf_name(client, auth, downloads):
    assert _save(client, auth, PDF, "..%2F..%2Fescape").json["name"] == "escape.pdf"
    assert sorted(p.name for p in downloads.iterdir()) == ["escape.pdf"]


def test_save_refuses_what_is_not_a_pdf(client, auth, downloads):
    r = _save(client, auth, b"<html>a login page</html>")
    assert r.status_code == 400 and "not a PDF" in r.json["error"]
    assert not downloads.exists()


def test_save_needs_the_window_token(client, downloads):
    r = client.post("/save_pdf?name=x.pdf", data=PDF, base_url=BASE)
    assert r.status_code == 403
    assert not downloads.exists()


# ── PubMed Central PDFs ─────────────────────────────────────────────────────
# PMC answers every program with a proof-of-work JavaScript page instead of the
# PDF, so the viewer's server-side fetch never got one: it fell through to the
# Sci-Hub mirrors for articles that are free, or dropped to the browser. NCBI's
# open-access dataset on AWS is the route it documents for programs.

POW_PAGE = b"<html><head><title>Preparing to download ...</title></head><body>POW CHALLENGE</body></html>"


def _listing(pmcid, versions):
    prefixes = "".join(f"<CommonPrefixes><Prefix>{pmcid}.{v}/</Prefix></CommonPrefixes>"
                       for v in versions)
    return (f"<ListBucketResult><Prefix>{pmcid}.</Prefix>{prefixes}</ListBucketResult>").encode()


def _fake_pmc(monkeypatch, pmcid, versions, seen, scihub_allowed=False, pdf=b"%PDF-1.7 "):
    def fetch(url, **k):
        seen.append(url)
        if url.startswith(A.PMC_OPENDATA + "/?"):
            return _listing(pmcid, versions), "application/xml"
        if url.startswith(A.PMC_OPENDATA + "/"):
            return pdf + url.encode(), "binary/octet-stream"
        return POW_PAGE, "text/html; charset=utf-8"
    monkeypatch.setattr(A, "_fetch_url_bytes", fetch)
    if scihub_allowed:
        monkeypatch.setattr(A, "_try_scihub_chain", lambda mirrors: seen.append("sci-hub") or None)
    else:
        monkeypatch.setattr(A, "_try_scihub_chain", lambda mirrors: (_ for _ in ()).throw(
            AssertionError("an open-access PMC article must not be fetched from Sci-Hub")))


@pytest.mark.parametrize("link", [
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC7188715/pdf/",     # MedSearch's own PMC link
    "https://www.ncbi.nlm.nih.gov/pmc/articles/7188715",         # the form Unpaywall returns
])
def test_an_open_access_pmc_article_opens_from_the_open_dataset(client, auth, monkeypatch, link):
    A.SESSION["articles"] = [article(doi="10.1/oa", access_kind="open", access_link=link,
                                     scihub=["https://sci-hub.ru/10.1/oa"])]
    seen = []
    _fake_pmc(monkeypatch, "PMC7188715", [1, 2], seen)
    r = client.get("/pdf_proxy", query_string={"url": link}, headers=auth, base_url=BASE)
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert r.data.endswith(b"/PMC7188715.2/PMC7188715.2.pdf"), "the latest version, not the first"
    assert link not in seen, "the challenge page is not fetched when the dataset answers"


def test_an_article_missing_from_the_dataset_takes_the_old_path(client, auth, monkeypatch):
    """Only PMC's open-access subset is in the dataset. For the rest nothing changes,
    including the Sci-Hub fallback, which stays by his decision of 23 September."""
    link = "https://pmc.ncbi.nlm.nih.gov/articles/PMC7188715/pdf/"
    A.SESSION["articles"] = [article(doi="10.1/oa", access_kind="open", access_link=link)]
    seen = []
    _fake_pmc(monkeypatch, "PMC7188715", [], seen, scihub_allowed=True)
    r = client.get("/pdf_proxy", query_string={"url": link}, headers=auth, base_url=BASE)
    assert link in seen and "sci-hub" in seen and r.status_code == 415


def test_a_dataset_answer_that_is_not_a_pdf_is_never_served_as_one(client, auth, monkeypatch):
    """An article listed without a PDF answers with S3's XML error. That must take the
    old path, not reach the viewer labelled application/pdf."""
    link = "https://pmc.ncbi.nlm.nih.gov/articles/PMC7188715/pdf/"
    A.SESSION["articles"] = [article(doi="10.1/oa", access_kind="open", access_link=link)]
    seen = []
    _fake_pmc(monkeypatch, "PMC7188715", [1], seen, scihub_allowed=True,
              pdf=b"<?xml version='1.0'?><Error><Code>NoSuchKey</Code></Error>")
    r = client.get("/pdf_proxy", query_string={"url": link}, headers=auth, base_url=BASE)
    assert r.status_code == 415 and link in seen


def test_a_non_pmc_link_never_asks_the_dataset(client, auth, monkeypatch):
    A.SESSION["articles"] = [article(doi="10.1/p", access_kind="open",
                                     access_link="https://publisher.example/p.pdf")]
    seen = []
    monkeypatch.setattr(A, "_fetch_url_bytes",
                        lambda url, **k: seen.append(url) or (b"%PDF-1.4 x", "application/pdf"))
    r = client.get("/pdf_proxy", query_string={"url": "https://publisher.example/p.pdf"},
                   headers=auth, base_url=BASE)
    assert r.status_code == 200 and seen == ["https://publisher.example/p.pdf"]


# ── One app: the window, the hand-off, and the installed launcher ───────────
# (the menu bar item lives in the same process since 20 Sep; these cover the
#  parts of that change that are testable without AppKit)

def test_queued_search_is_handed_over_once_and_then_cleared(client, auth):
    """A second launch POSTs its query here; the running window polls for it.
    Handing it over twice would run the same search twice."""
    r = client.post("/queue_search", json={"query": "glioma", "source": "pubmed"},
                    headers=auth, base_url=BASE)
    assert r.json["ok"] is True
    first = client.get("/pending_search", headers=auth, base_url=BASE).json
    assert (first["pending"], first["query"], first["source"]) == (True, "glioma", "pubmed")
    assert client.get("/pending_search", headers=auth, base_url=BASE).json["pending"] is False


def test_an_empty_queued_search_is_refused(client, auth):
    r = client.post("/queue_search", json={"query": "   "}, headers=auth, base_url=BASE)
    assert r.json["ok"] is False
    assert client.get("/pending_search", headers=auth, base_url=BASE).json["pending"] is False


def test_queueing_a_search_needs_the_token(client):
    assert client.post("/queue_search", json={"query": "x"}, base_url=BASE).status_code == 403


def test_focus_reports_whether_there_is_a_window_to_show(client, auth, monkeypatch):
    """The answer is what a second launch uses to decide between raising the
    window and falling back to the browser."""
    monkeypatch.setattr(A, "_MAIN_WINDOW", None)
    monkeypatch.setattr(A, "_STATUSBAR", None)
    assert client.post("/focus", headers=auth, base_url=BASE).json["ok"] is False


def test_open_at_login_writes_and_removes_the_agent(tmp_path, monkeypatch):
    agent = tmp_path / "LaunchAgents" / "com.halbarad.medsearch.plist"
    monkeypatch.setattr(A, "_LOGIN_AGENT", agent)
    monkeypatch.setattr(A, "_launcher_bundle_id", lambda: "com.halbarad.medsearch.launcher")
    A._set_open_at_login(True)
    text = agent.read_text()
    assert "com.halbarad.medsearch.launcher" in text and "--background" in text
    assert "<key>RunAtLoad</key><true/>" in text
    A._set_open_at_login(False)
    assert not agent.exists()


def test_open_at_login_without_a_launcher_runs_this_folder(tmp_path, monkeypatch):
    agent = tmp_path / "com.halbarad.medsearch.plist"
    monkeypatch.setattr(A, "_LOGIN_AGENT", agent)
    monkeypatch.setattr(A, "_launcher_bundle_id", lambda: "")
    A._set_open_at_login(True)
    assert str(A.APP_DIR_PATH / "app.py") in agent.read_text()


def test_a_failing_login_item_still_saves_the_settings(client, auth, monkeypatch):
    """The keys and libraries are already on disk by then, so the page must
    finish saving: a login item it couldn't write is a warning, not a failure."""
    monkeypatch.setattr(A, "_open_at_login_supported", lambda: True)

    def boom(_on):
        raise PermissionError("read-only LaunchAgents")
    monkeypatch.setattr(A, "_set_open_at_login", boom)
    r = client.post("/settings", json={"unpaywall_email": "you@example.com",
                                       "open_at_login": True}, headers=auth, base_url=BASE)
    assert r.json["ok"] is True
    assert "login" in r.json["warning"].lower()
    assert A.CONFIG["unpaywall_email"] == "you@example.com"


def test_settings_reports_the_login_state_it_can_see(client, auth, tmp_path, monkeypatch):
    agent = tmp_path / "com.halbarad.medsearch.plist"
    monkeypatch.setattr(A, "_LOGIN_AGENT", agent)
    assert client.get("/settings", headers=auth, base_url=BASE).json["open_at_login"] is False
    agent.write_text("<plist/>")
    assert client.get("/settings", headers=auth, base_url=BASE).json["open_at_login"] is True


def _bundle(tmp_path, exec_text):
    b = tmp_path / "MedSearch.app"
    (b / "Contents" / "MacOS").mkdir(parents=True)
    (b / "Contents" / "Resources").mkdir(parents=True)
    (b / "Contents" / "MacOS" / "MedSearch").write_text(exec_text)
    return b


def test_an_old_launcher_is_rewritten_to_run_launcher_sh(tmp_path, monkeypatch):
    """git pull cannot reach inside MedSearch.app, so the app converts the
    launcher that started it — once."""
    b = _bundle(tmp_path, f'#!/bin/bash\nexec python3 "{A.APP_DIR_PATH / "app.py"}" "$@"\n')
    monkeypatch.setattr(A.sys, "platform", "darwin")
    monkeypatch.setattr(A, "_bundle_path_for", lambda _bid: b)
    A._maintain_launcher("com.halbarad.medsearch.launcher", True)
    after = (b / "Contents" / "MacOS" / "MedSearch").read_text()
    assert "launcher.sh" in after and str(A.APP_DIR_PATH) in after


def test_a_launcher_for_another_folder_is_left_alone(tmp_path, monkeypatch):
    b = _bundle(tmp_path, '#!/bin/bash\nexec python3 "/somewhere/else/app.py" "$@"\n')
    monkeypatch.setattr(A.sys, "platform", "darwin")
    monkeypatch.setattr(A, "_bundle_path_for", lambda _bid: b)
    A._maintain_launcher("com.halbarad.medsearch.launcher", True)
    assert "/somewhere/else/app.py" in (b / "Contents" / "MacOS" / "MedSearch").read_text()


def test_the_launcher_icon_is_kept_in_step(tmp_path, monkeypatch):
    b = _bundle(tmp_path, '#!/bin/bash\nexec /bin/bash "/x/launcher.sh" "$@"\n')
    icon = b / "Contents" / "Resources" / "MedSearch.icns"
    icon.write_bytes(b"old icon")
    monkeypatch.setattr(A.sys, "platform", "darwin")
    monkeypatch.setattr(A, "_bundle_path_for", lambda _bid: b)
    A._maintain_launcher("com.halbarad.medsearch.launcher", False)
    assert icon.read_bytes() == (A.APP_DIR_PATH / "icon.icns").read_bytes()


def test_only_our_launcher_identifiers_are_recognised(monkeypatch):
    for bid, ours in (("com.halbarad.medsearch.launcher", True),
                      ("com.riccardonevoso.medsearch.launcher", True),   # built before the rename
                      ("org.python.python", False),
                      ("", False)):
        monkeypatch.setitem(A.os.environ, "__CFBundleIdentifier", bid)
        assert bool(A._launcher_bundle_id()) is ours


# ── API keys live in the Keychain, not in the config file ───────────────────

class _FakeKeychain:
    """Stands in for secrets_store: the Keychain's behaviour, in a dict."""
    def __init__(self, on=True, items=None):
        self.on, self.items = on, dict(items or {})
    def available(self):
        return self.on
    def get(self, name):
        return self.items.get(name, "") if self.on else ""
    def set(self, name, value):
        if not self.on:
            return False
        if value:
            self.items[name] = value
        else:
            self.items.pop(name, None)
        return True
    def delete(self, name):
        return self.set(name, "")


def _use(monkeypatch, fake):
    for f in ("available", "get", "set", "delete"):
        monkeypatch.setattr(A.secrets_store, f, getattr(fake, f))
    return fake


def test_saving_keeps_the_keys_out_of_the_config_file(tmp_path, monkeypatch):
    fake = _use(monkeypatch, _FakeKeychain())
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "CONFIG_FILE", tmp_path / "config.json")
    A.save_config({**A.DEFAULTS, "anthropic_api_key": "sk-ant-secret",
                   "unpaywall_email": "you@example.com"})
    on_disk = json.loads((tmp_path / "config.json").read_text())
    assert on_disk["anthropic_api_key"] == ""            # not in the file
    assert on_disk["unpaywall_email"] == "you@example.com"   # not a secret
    assert fake.items["anthropic_api_key"] == "sk-ant-secret"


def test_a_key_saved_by_an_older_version_moves_into_the_keychain(tmp_path, monkeypatch):
    """Upgrading must not lose the key, and must not leave it in the file."""
    fake = _use(monkeypatch, _FakeKeychain())
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"anthropic_api_key": "sk-ant-old", "ai_enabled": True}))
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "CONFIG_FILE", cfg_file)
    cfg = A.load_config()
    assert cfg["anthropic_api_key"] == "sk-ant-old"       # still usable
    assert fake.items["anthropic_api_key"] == "sk-ant-old"
    assert json.loads(cfg_file.read_text())["anthropic_api_key"] == ""


def test_the_keychain_is_used_when_the_file_has_nothing(tmp_path, monkeypatch):
    _use(monkeypatch, _FakeKeychain(items={"anthropic_api_key": "sk-ant-current"}))
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"anthropic_api_key": ""}))
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "CONFIG_FILE", cfg_file)
    assert A.load_config()["anthropic_api_key"] == "sk-ant-current"


def test_a_key_in_the_file_replaces_an_older_one_in_the_keychain(tmp_path, monkeypatch):
    """The case that cost a real key: a version that didn't use the Keychain
    saved a NEW key to the file while the Keychain still held a revoked one.
    Storing always blanks the file, so a value in the file is the newer one."""
    fake = _use(monkeypatch, _FakeKeychain(items={"anthropic_api_key": "sk-ant-revoked"}))
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"anthropic_api_key": "sk-ant-brand-new"}))
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "CONFIG_FILE", cfg_file)
    cfg = A.load_config()
    assert cfg["anthropic_api_key"] == "sk-ant-brand-new"
    assert fake.items["anthropic_api_key"] == "sk-ant-brand-new"
    assert json.loads(cfg_file.read_text())["anthropic_api_key"] == ""


def test_without_a_keychain_the_file_keeps_working(tmp_path, monkeypatch):
    """Not macOS, or the Keychain refused: MedSearch still has to run."""
    _use(monkeypatch, _FakeKeychain(on=False))
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "CONFIG_FILE", cfg_file)
    A.save_config({**A.DEFAULTS, "anthropic_api_key": "sk-ant-plain"})
    assert json.loads(cfg_file.read_text())["anthropic_api_key"] == "sk-ant-plain"
    assert A.load_config()["anthropic_api_key"] == "sk-ant-plain"


def test_removing_a_key_removes_it_from_the_keychain_too(tmp_path, monkeypatch):
    fake = _use(monkeypatch, _FakeKeychain(items={"wos_api_key": "old"}))
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "CONFIG_FILE", tmp_path / "config.json")
    A.save_config({**A.DEFAULTS, "wos_api_key": ""})
    assert "wos_api_key" not in fake.items


def test_the_config_file_is_readable_only_by_its_owner(tmp_path, monkeypatch):
    _use(monkeypatch, _FakeKeychain())
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "CONFIG_FILE", tmp_path / "config.json")
    A.save_config(dict(A.DEFAULTS))
    assert oct((tmp_path / "config.json").stat().st_mode)[-3:] == "600"


def test_a_refusing_keychain_never_costs_the_key(tmp_path, monkeypatch):
    """The Keychain is there but will not store (locked, or no login keychain
    — which is what a wrong HOME does). The key must stay in the file."""
    class Refusing(_FakeKeychain):
        def set(self, name, value):
            return False
    _use(monkeypatch, Refusing())
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "CONFIG_FILE", tmp_path / "config.json")
    A.save_config({**A.DEFAULTS, "anthropic_api_key": "sk-ant-keepme"})
    assert json.loads((tmp_path / "config.json").read_text())["anthropic_api_key"] == "sk-ant-keepme"
    assert A.load_config()["anthropic_api_key"] == "sk-ant-keepme"


# ── What the AI spends: the meter and the monthly limit ─────────────────────

def _usage_in(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(A, "USAGE_FILE", tmp_path / "usage.json")


def test_a_call_is_priced_from_what_the_api_reports(tmp_path, monkeypatch):
    _usage_in(tmp_path, monkeypatch)
    # Sonnet 5: $2 per 1M in, $10 per 1M out.
    u = A.record_usage("claude-sonnet-5", "syntheses", 1_000_000, 100_000)
    assert round(u["cost"], 6) == round(2.00 + 1.00, 6)
    assert u["calls"] == {"syntheses": 1}


def test_cached_tokens_are_priced_at_their_own_rates(tmp_path, monkeypatch):
    _usage_in(tmp_path, monkeypatch)
    # A cache write costs 1.25x the input rate, a read 0.1x.
    u = A.record_usage("claude-sonnet-5", "questions", 0, 0,
                       cache_write_tokens=1_000_000, cache_read_tokens=1_000_000)
    assert round(u["cost"], 6) == round(2.00 * 1.25 + 2.00 * 0.10, 6)


def test_an_unpriced_model_is_counted_but_not_costed(tmp_path, monkeypatch):
    _usage_in(tmp_path, monkeypatch)
    u = A.record_usage("some-future-model", "summaries", 1_000_000, 1_000_000)
    assert u["cost"] == 0.0 and u["unpriced_calls"] == 1
    assert u["input_tokens"] == 1_000_000


def test_a_new_month_starts_from_zero(tmp_path, monkeypatch):
    _usage_in(tmp_path, monkeypatch)
    (tmp_path / "usage.json").write_text(json.dumps(
        {"month": "1999-01", "cost": 99.0, "calls": {"syntheses": 12}}))
    assert A.load_usage()["cost"] == 0.0
    assert A.load_usage()["month"] == A._this_month()


def test_the_streamed_answer_is_metered(client, auth, monkeypatch, tmp_path):
    """The token counts arrive in two different events; both must be picked up."""
    _usage_in(tmp_path, monkeypatch)
    A.CONFIG["anthropic_api_key"] = "sk-test"
    lines = [
        'data: {"type":"message_start","message":{"usage":{"input_tokens":1000,'
        '"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hi"}}',
        'data: {"type":"message_delta","usage":{"output_tokens":500}}',
    ]
    monkeypatch.setattr(A, "_anthropic_open", lambda payload, timeout: _FakeStream(lines))
    list(A.claude_stream({"model": "claude-sonnet-5", "messages": []}, feature="explanations"))
    u = A.load_usage()
    assert u["calls"] == {"explanations": 1}
    assert round(u["cost"], 6) == round(1000 / 1e6 * 2.0 + 500 / 1e6 * 10.0, 6)


def test_the_limit_stops_the_ai_and_says_so(client, auth, monkeypatch, tmp_path):
    _usage_in(tmp_path, monkeypatch)
    A.CONFIG["anthropic_api_key"] = "sk-test"
    A.CONFIG["ai_monthly_cap"] = 5.0
    A.record_usage("claude-sonnet-5", "syntheses", 3_000_000, 0)   # $6, over the $5 limit
    assert A.ai_over_cap() is True

    attempts = []
    monkeypatch.setattr(A, "_anthropic_open",
                        lambda payload, timeout: attempts.append(payload))

    events = [json.loads(c[6:]) for c in
              A.claude_stream({"model": A.MODEL_MAIN, "messages": []}, feature="syntheses")]
    assert events[0]["type"] == "error" and "$5.00" in events[0]["text"]
    assert events[-1]["type"] == "done"                    # the stream still closes
    assert A.ai_oneliner("t", "abstract") is None          # the cheap calls stop too
    # Nothing was sent: the limit has to stop the request, not just its answer.
    assert attempts == []


def test_no_limit_means_no_limit(tmp_path, monkeypatch):
    _usage_in(tmp_path, monkeypatch)
    A.CONFIG["ai_monthly_cap"] = 0
    A.record_usage("claude-sonnet-5", "syntheses", 50_000_000, 0)   # $100
    assert A.ai_over_cap() is False


def test_the_usage_route_reports_the_month(client, auth, tmp_path, monkeypatch):
    _usage_in(tmp_path, monkeypatch)
    A.record_usage("claude-haiku-4-5", "summaries", 1_000_000, 200_000)
    r = client.get("/usage", headers=auth, base_url=BASE).json
    assert r["calls"] == {"summaries": 1}
    assert round(r["cost"], 4) == round(1.00 + 1.00, 4)
    assert r["month"] == A._this_month()


def test_the_limit_is_saved_from_settings(client, auth):
    client.post("/settings", json={"ai_monthly_cap": "12.5"}, headers=auth, base_url=BASE)
    assert A.CONFIG["ai_monthly_cap"] == 12.5
    assert client.get("/settings", headers=auth, base_url=BASE).json["ai_monthly_cap"] == 12.5
    client.post("/settings", json={"ai_monthly_cap": "rubbish"}, headers=auth, base_url=BASE)
    assert A.CONFIG["ai_monthly_cap"] == 0.0


# ── What a new version changes, and mirrors that learn ─────────────────────

CHANGELOG = """# What changed

## 1.5

- Keys in the Keychain.
- A monthly limit for the AI.

## 1.4

- The menu bar item is part of MedSearch now.
"""


def test_the_entry_for_a_version_is_read_from_the_changelog():
    assert A.changelog_entry(CHANGELOG, "1.5") == ["Keys in the Keychain.",
                                                   "A monthly limit for the AI."]
    assert A.changelog_entry(CHANGELOG, "1.4") == ["The menu bar item is part of MedSearch now."]


def test_a_version_with_nothing_written_about_it_invents_nothing():
    assert A.changelog_entry(CHANGELOG, "9.9") == []
    assert A.changelog_entry("", "1.5") == []
    assert A.changelog_entry(None, "1.5") == []


def test_the_update_check_reports_what_changed(client, auth, monkeypatch):
    calls = []

    def fake_get(url, timeout=8):
        calls.append(url)
        return ("9.9\n" if url.endswith("VERSION") else CHANGELOG.replace("1.5", "9.9")), 200
    monkeypatch.setattr(A, "http_get", fake_get)
    r = client.get("/update/check", headers=auth, base_url=BASE).json
    assert r["update_available"] is True
    assert r["changes"] == ["Keys in the Keychain.", "A monthly limit for the AI."]
    assert any(c.endswith("CHANGELOG.md") for c in calls)


def test_no_changelog_is_fetched_when_there_is_nothing_to_update(client, auth, monkeypatch):
    """The check runs at every launch: it must not fetch what it cannot use."""
    calls = []

    def fake_get(url, timeout=8):
        calls.append(url)
        return A.get_local_version(), 200
    monkeypatch.setattr(A, "http_get", fake_get)
    r = client.get("/update/check", headers=auth, base_url=BASE).json
    assert r["update_available"] is False and r["changes"] == []
    assert not any(c.endswith("CHANGELOG.md") for c in calls)


def test_the_mirror_that_worked_moves_to_the_front(monkeypatch):
    A.CONFIG["scihub_mirrors"] = ["https://dead.example", "https://alive.example"]
    monkeypatch.setattr(A, "save_config", lambda cfg: None)

    def fetch(url, referer=None):
        if "dead" in url:
            raise RuntimeError("no answer")
        return b"%PDF-1.7 ...", "application/pdf"
    monkeypatch.setattr(A, "_fetch_url_bytes", fetch)

    got = A._try_scihub_chain(["https://dead.example/10.1/x", "https://alive.example/10.1/x"])
    assert got is not None
    assert A.CONFIG["scihub_mirrors"][0] == "https://alive.example"


def test_a_mirror_that_is_not_ours_is_not_added(monkeypatch):
    A.CONFIG["scihub_mirrors"] = ["https://one.example", "https://two.example"]
    monkeypatch.setattr(A, "save_config", lambda cfg: None)
    A._promote_mirror("https://somewhere.else")
    A._promote_mirror("")
    assert A.CONFIG["scihub_mirrors"] == ["https://one.example", "https://two.example"]


def test_the_order_is_left_alone_when_the_first_mirror_works(monkeypatch):
    A.CONFIG["scihub_mirrors"] = ["https://one.example", "https://two.example"]
    saved = []
    monkeypatch.setattr(A, "save_config", lambda cfg: saved.append(cfg))
    A._promote_mirror("https://one.example")
    assert A.CONFIG["scihub_mirrors"] == ["https://one.example", "https://two.example"]
    assert saved == []          # nothing to write

"""The HTTP surface: the request guard, the search stream, settings, export,
the assistant, and the PDF proxy's allowlist."""
import json

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
    monkeypatch.setattr(A, "claude_text", lambda payload, timeout=30: seen.update(payload) or "x")
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

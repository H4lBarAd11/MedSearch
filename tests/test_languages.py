"""Languages: a search narrowed to English and the languages added, English
first; each database asked in its own way where it can be, and the others
saying so. Placeholder names only; nothing reaches the network."""
import json
import re
import urllib.parse

import pytest

import app as A
from conftest import BASE, article, sse_events


def params(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


@pytest.fixture
def asked(monkeypatch):
    """Every fetch_json / http_get answers `reply[0]`; the URLs asked are kept."""
    urls, reply = [], [({}, 200)]

    class Asked(list):
        pass
    urls = Asked()
    urls.reply = reply

    def fake(url, *a, **k):
        urls.append(url)
        return reply[0]
    monkeypatch.setattr(A, "fetch_json", fake)
    monkeypatch.setattr(A, "http_get", lambda url, *a, **k: (urls.append(url),
                        (reply[0][0] if isinstance(reply[0][0], str) else json.dumps(reply[0][0]),
                         reply[0][1]))[1])
    monkeypatch.setattr(A, "enrich_access", lambda arts: arts)
    monkeypatch.setattr(A, "fill_abstracts_from_pubmed", lambda arts: arts)
    return urls


# ── The languages ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("written, code", [("en", "en"), ("eng", "en"), ("English", "en"),
                                           (" ger ", "de"), ("deu", "de"), ("fre", "fr"), ("fra", "fr"),
                                           ("Italian", "it"), ("xx", None), ("", None), (None, None)])
def test_a_language_is_known_however_a_record_writes_it(written, code):
    assert A.language_code(written) == code


def test_the_languages_asked_for_are_checked_and_english_comes_first():
    assert A.language_filter(["it", "en", "ita", "nonsense", "de"]) == ["en", "it", "de"]
    assert A.language_filter(["de"]) == ["de"]
    assert A.language_filter("en") == [] and A.language_filter(None) == []


def test_results_are_kept_in_the_languages_asked_for_english_first_unknown_last():
    arts = [article(title="it", languages=["it"]), article(title="?"), article(title="de", languages=["de"]),
            article(title="en1", languages=["en"]), article(title="it+en", languages=["it", "en"]),
            article(title="en2", languages=["en"])]
    assert [a["title"] for a in A.by_language(arts, ["en", "it"])] == ["en1", "it+en", "en2", "it", "?"]
    assert A.by_language(arts, []) is arts


# ── Each database asked in its own way ──────────────────────────────────────

def test_pubmed_and_the_databases_built_on_it_ask_for_the_languages(asked):
    asked.reply[0] = ({"esearchresult": {"idlist": [], "count": "0"}}, 200)
    A.search_pubmed("glioma", 10, None, None, languages=["en", "it"])
    A.search_bookshelf("glioma", 10, None, None, languages=["de"])
    A.search_guidelines("glioma", 10, None, None, languages=["en"])
    A.search_cochrane("glioma", 10, None, None, languages=["en"])
    terms = [params(u)["term"] for u in asked]
    assert terms[0] == f"((glioma[tiab]) AND (eng[la] OR ita[la])) NOT {A.PUBMED_BOOKS}"
    assert terms[1] == f"((glioma[tiab]) AND {A.PUBMED_BOOKS}) AND ger[la]"
    assert terms[2].endswith("AND eng[la]") and terms[3].endswith("AND eng[la]")


def test_europe_pmc_openalex_and_scopus_ask_for_the_languages(asked, monkeypatch):
    asked.reply[0] = ({"hitCount": 0, "resultList": {"result": []}, "results": [], "meta": {"count": 0}}, 200)
    A.search_europepmc("glioma", 10, None, None, languages=["en", "fr"])
    # Its records mostly carry MEDLINE's "fre", some "fra".
    assert params(asked[-1])["query"].endswith(' AND (LANG:"eng" OR LANG:"fre" OR LANG:"fra")')
    A.search_openalex("glioma", 10, None, None, languages=["en", "it"])
    p = params(asked[-1])
    assert "language:en|it" in p["filter"].split(",") and "language" in p["select"].split(",")
    seen = []
    monkeypatch.setattr(A, "scopus_entries", lambda q, *a: (seen.append(q), ([], 0))[1])
    A.search_scopus("glioma", 10, None, None, languages=["en", "it"])
    assert seen == ["(glioma) AND (LANGUAGE(english) OR LANGUAGE(italian))"]


def test_open_library_asks_for_a_work_with_an_edition_in_the_languages(asked):
    asked.reply[0] = ({"numFound": 0, "docs": []}, 200)
    A.search_openlibrary("glioma", 10, 2000, None, languages=["en", "it"])
    assert params(asked[-1])["q"] == "((glioma) AND first_publish_year:[2000 TO *]) AND language:(eng OR ita)"
    assert "language" in params(asked[-1])["fields"].split(",")


def test_google_books_is_asked_for_one_language_and_checked_for_more(asked):
    A.CONFIG["google_books_api_key"] = "gb-key"
    asked.reply[0] = ({"totalItems": 0, "items": []}, 200)
    A.search_googlebooks("glioma", 10, None, None, languages=["it"])
    A.search_googlebooks("glioma", 10, None, None, languages=["en", "it"])
    assert params(asked[0])["langRestrict"] == "it" and "langRestrict" not in params(asked[1])


# ── Each record's languages ─────────────────────────────────────────────────

def test_each_source_says_its_records_languages(monkeypatch):
    efetch = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
      <Journal><Title>J</Title><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal>
      <ArticleTitle>T</ArticleTitle><Language>ger</Language><Language>eng</Language></Article></MedlineCitation>
      </PubmedArticle><PubmedBookArticle><BookDocument><PMID>2</PMID><Book><BookTitle>B</BookTitle>
      <PubDate><Year>2020</Year></PubDate></Book><Language>eng</Language></BookDocument></PubmedBookArticle>
      </PubmedArticleSet>"""
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (efetch, 200))
    assert [a["languages"] for a in A.pubmed_records(["1", "2"])] == [["de", "en"], ["en"]]
    assert A._europepmc_article({"title": "T", "language": "ita"})["languages"] == ["it"]
    assert A._openalex_article({"display_name": "T", "language": "fr"})["languages"] == ["fr"]
    assert A._openlibrary_article({"key": "/works/OL1W", "title": "T",
                                   "language": ["eng", "ita", "xxx"]})["languages"] == ["en", "it"]
    assert A._googlebooks_article({"volumeInfo": {"title": "T", "language": "es"}})["languages"] == ["es"]
    assert A._core_article({"title": "T", "language": {"code": "pt", "name": "Portuguese"}})["languages"] == ["pt"]
    assert A._core_article({"title": "T"})["languages"] == []
    assert A._crossref_article({"DOI": "10.9/x", "title": ["T"]})["languages"] == []


# ── The search ──────────────────────────────────────────────────────────────

def _fake_sources(monkeypatch, results, calls):
    def make(key):
        def run(query, max_r, y_from, y_to, **kw):
            calls[key] = kw.get("languages")
            return [dict(a) for a in results.get(key, [])], 0
        return run
    monkeypatch.setattr(A, "SOURCES", [(k, l, make(k), s) for k, l, _f, s in A.SOURCES])
    monkeypatch.setattr(A, "get_mesh", lambda q: [])
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)


def _search(client, auth, **body):
    payload = {"query": "glioma", "sources": ["pubmed", "crossref"], "max_results": 10, **body}
    return sse_events(client.post("/search_stream", json=payload, headers=auth, base_url=BASE))


def test_the_search_asks_who_can_be_asked_and_orders_and_explains_the_rest(client, auth, monkeypatch):
    calls = {}
    _fake_sources(monkeypatch, {
        "pubmed": [article(title="Italian paper", languages=["it"]), article(title="English paper", languages=["en"])],
        "crossref": [article(title="Unknown one", source="Crossref"),
                     article(title="German one", source="Crossref", languages=["de"])]}, calls)
    events = _search(client, auth, languages=["it", "en"])
    assert calls == {"pubmed": ["en", "it"], "crossref": None}
    assert [e["article"]["title"] for e in events if e["type"] == "article"] == [
        "English paper", "Italian paper", "Unknown one"]
    done = {e["source"]: e for e in events if e["type"] == "source_done"}
    assert "note" not in done["PubMed"]
    assert done["Crossref"]["note"] == ("Crossref can't be searched by language, so its results are not "
                                        "narrowed to English and Italian.")
    assert A.SESSION["query"] == "glioma (in English and Italian)"


def test_without_languages_nothing_changes(client, auth, monkeypatch):
    calls = {}
    _fake_sources(monkeypatch, {"crossref": [article(title="Unknown", source="Crossref"),
                                             article(title="German", source="Crossref", languages=["de"])]}, calls)
    events = _search(client, auth)
    assert calls == {"pubmed": None, "crossref": None}
    assert [e["article"]["title"] for e in events if e["type"] == "article"] == ["Unknown", "German"]
    assert not any(e.get("note") for e in events) and A.SESSION["query"] == "glioma"


def test_find_more_with_other_languages_is_another_search(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {}, {})
    _search(client, auth, languages=["en"])
    assert _search(client, auth, languages=["en", "it"], load_more=True)[0]["type"] == "error"
    assert _search(client, auth, languages=["en"], load_more=True)[0]["type"] != "error"


def test_a_doi_search_ignores_the_languages(client, auth, monkeypatch):
    seen = []
    monkeypatch.setattr(A, "doi_lookup", lambda key, fn, dois, reg=None: (seen.append(key), ([], 0))[1])
    monkeypatch.setattr(A, "crossref_records", lambda dois, reg=None: ([], 0))
    _fake_sources(monkeypatch, {}, {})
    _search(client, auth, query="10.1000/xyz", sources=["pubmed"], languages=["it"])
    assert seen == ["pubmed"] and A.SESSION["query"] == "10.1000/xyz"


def test_the_languages_are_kept_for_the_next_start(client, auth):
    r = client.post("/languages", json={"languages": ["it", "en", "zz"]}, headers=auth, base_url=BASE)
    assert r.json == {"ok": True, "languages": ["en", "it"]} and A.CONFIG["languages"] == ["en", "it"]
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert 'languages:          ["en", "it"],' in page and '["it", "Italian"]' in page
    assert 'id="languageChip"' in page and 'id="languageAdd"' in page
    assert client.post("/languages", json={"languages": "en"}, headers=auth,
                       base_url=BASE).status_code == 400


def test_clinicaltrials_gov_registers_its_trials_in_english(asked):
    asked.reply[0] = ({"studies": [{"protocolSection": {
        "identificationModule": {"nctId": "NCT00000001", "briefTitle": "A trial"},
        "statusModule": {"startDateStruct": {"date": "2020-01"}}}}]}, 200)
    arts, _ = A.search_clinicaltrials("glioma", 10, None, None)
    assert arts[0]["languages"] == ["en"]
    # So with English asked for, nothing is left out and there is nothing to explain.
    assert A.by_language(arts, ["en", "it"]) == arts

"""The six sources added in 2.1: OpenAlex, Europe PMC, Crossref, IEEE Xplore,
Semantic Scholar and CORE. What each is asked, how its answer is read, what it
says when it refuses, and that the window, the menus and Settings know every
source. The answers are shaped like the real ones (recorded 2 October 2026,
trimmed, with placeholder names); nothing reaches the network."""
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

import pytest

import app as A
import appmenu
from conftest import BASE, article, sse_events

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def no_enrich(monkeypatch):
    monkeypatch.setattr(A, "enrich_access", lambda arts: arts)
    monkeypatch.setattr(A, "fill_abstracts_from_pubmed", lambda arts: arts)
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)


class Calls(list):
    def params(self, i=-1):
        return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self[i]["url"]).query))

    def path(self, i=-1):
        return urllib.parse.urlsplit(self[i]["url"]).path


@pytest.fixture
def answer(monkeypatch, no_enrich):
    """answer(body, status) makes every call answer that, and returns the
    list of calls made (url, headers, data)."""
    calls, state = Calls(), {"answer": (None, 0)}

    def fetch_json(url, headers=None, timeout=None, error_body=False, data=None):
        calls.append({"url": url, "headers": headers or {}, "data": data})
        return state["answer"]

    def http_get(url, headers=None, timeout=None, error_body=False, data=None):
        calls.append({"url": url, "headers": headers or {}, "data": data})
        body, status = state["answer"]
        return (body if body is None or isinstance(body, str) else json.dumps(body)), status

    monkeypatch.setattr(A, "fetch_json", fetch_json)
    monkeypatch.setattr(A, "http_get", http_get)

    def set_answer(body, status=200):
        state["answer"] = (body, status)
        return calls
    return set_answer


# ── OpenAlex ────────────────────────────────────────────────────────────────

OPENALEX_WORK = {
    "id": "https://openalex.org/W1",
    "doi": "https://doi.org/10.1000/oa.1",
    "display_name": "Awake mapping of <i>language</i> areas",
    "publication_year": 2021,
    "authorships": [{"author": {"display_name": "Jane Doe"}},
                    {"author": {"display_name": "Ada Example"}},
                    {"author": {}, "raw_author_name": "R. Placeholder"},
                    {"author": {"display_name": "Sam Sample"}}],
    "primary_location": {"source": {"display_name": "Journal of Neurosurgery"}},
    "abstract_inverted_index": {"Mapping": [0], "language": [1, 4], "is": [2],
                                "safe;": [3], "matters.": [5]},
    "cited_by_count": 12,
    "ids": {"openalex": "https://openalex.org/W1", "pmid": "https://pubmed.ncbi.nlm.nih.gov/123456"},
    "type": "review",
    "is_retracted": True,
    "locations": [{"is_oa": False, "pdf_url": "https://publisher.example/closed.pdf"},
                  {"is_oa": True, "pdf_url": "https://europepmc.org/articles/PMC1/pdf",
                   "landing_page_url": "https://europepmc.org/articles/PMC1",
                   "source": {"type": "repository"}, "version": "publishedVersion"}],
}


def test_an_openalex_work_reads_as_an_article():
    a = A._openalex_article(OPENALEX_WORK)
    assert a["title"] == "Awake mapping of language areas"
    assert a["authors"] == "Jane Doe; Ada Example; R. Placeholder et al."
    assert a["author_list"] == ["Jane Doe", "Ada Example", "R. Placeholder", "Sam Sample"]
    assert (a["year"], a["journal"], a["quartile"]) == ("2021", "Journal of Neurosurgery", "Q1")
    assert (a["doi"], a["pmid"], a["cited_by"]) == ("10.1000/oa.1", "123456", 12)
    assert a["abstract"] == "Mapping language is safe; language matters."
    assert (a["access_kind"], a["access_link"]) == ("open", "https://europepmc.org/articles/PMC1/pdf")
    assert (a["retraction"], a["pub_types"], a["source"]) == ("retracted", ["Review"], "OpenAlex")


def test_an_openalex_work_with_nothing_free_is_left_for_the_open_access_lookup():
    w = dict(OPENALEX_WORK, locations=[], ids={}, is_retracted=False, type="article")
    a = A._openalex_article(w)
    assert (a["access_kind"], a["pmid"], a["retraction"], a["pub_types"]) == (None, None, None, [])


def test_openalex_strict_searches_title_and_abstract_with_years_and_page(answer):
    calls = answer({"meta": {"count": 2672}, "results": [OPENALEX_WORK]})
    arts, total = A.search_openalex("awake, craniotomy", 10, 2018, 2022, offset=20)
    p = calls.params()
    assert calls.path() == "/works"
    assert p["filter"] == ("title_and_abstract.search:awake  craniotomy,"
                           "from_publication_date:2018-01-01,to_publication_date:2022-12-31")
    assert (p["page"], p["per-page"]) == ("3", "10")
    assert "search" not in p and "sort" not in p and "api_key" not in p
    assert total == 2672 and [a["doi"] for a in arts] == ["10.1000/oa.1"]


@pytest.mark.parametrize("query, strict", [("awake craniotomy", False),
                                           ('glioma AND "awake"', True)])
def test_openalex_broad_or_operators_use_its_own_search(answer, query, strict):
    calls = answer({"meta": {}, "results": []})
    A.search_openalex(query, 10, None, None, strict=strict, sort="date")
    p = calls.params()
    assert p["search"] == query and "filter" not in p
    assert p["sort"] == "publication_date:desc"


def test_openalex_sends_the_key_only_when_there_is_one(answer):
    A.CONFIG["openalex_api_key"] = "oa-key"
    calls = answer({"meta": {}, "results": []})
    A.search_openalex("glioma", 10, None, None)
    assert calls.params()["api_key"] == "oa-key"


def test_openalex_out_of_allowance_says_when_it_renews_and_what_a_key_does(answer):
    answer({"error": "Rate limit exceeded"}, 429)
    with pytest.raises(RuntimeError, match="allowance is used up.*midnight.*API key"):
        A.search_openalex("glioma", 10, None, None)


def test_openalex_looks_dois_up_in_one_free_call(answer):
    calls = answer({"meta": {}, "results": [OPENALEX_WORK]})
    arts = A.openalex_by_dois(["10.1000/a", "10.1000/b"])
    assert calls.params()["filter"] == "doi:10.1000/a|10.1000/b"
    assert "search" not in calls.params() and len(arts) == 1


# ── Europe PMC ──────────────────────────────────────────────────────────────

EPMC_MEDLINE = {
    "id": "111", "source": "MED", "pmid": "111", "pmcid": "PMC9", "isOpenAccess": "Y",
    "doi": "10.1000/e.1", "title": "A <i>trial</i> of awake surgery",
    "authorList": {"author": [{"fullName": "Doe J"}, {"fullName": "Example A"}]},
    "pubYear": "2022", "journalInfo": {"journal": {"title": "Neurosurgery"}},
    "abstractText": "<title>Abstract</title><p><b>Background</b> First part.</p>"
                    "<title>Methods</title><p>Second part.</p>",
    "pubTypeList": {"pubType": ["review", "Journal Article", "Retracted Publication"]},
    "citedByCount": 4,
}
EPMC_PREPRINT = {
    "id": "PPR1", "source": "PPR", "doi": "10.1101/p.1", "title": "A preprint",
    "authorString": "Doe J, Example A.", "pubYear": "2026",
    "bookOrReportDetails": {"publisher": "medRxiv"}, "pubTypeList": {"pubType": ["Preprint"]},
    "isOpenAccess": "N", "citedByCount": 0,
}


def test_a_europe_pmc_record_reads_as_an_article():
    a = A._europepmc_article(EPMC_MEDLINE)
    assert (a["title"], a["authors"], a["year"]) == ("A trial of awake surgery", "Doe J; Example A", "2022")
    assert (a["journal"], a["quartile"], a["doi"], a["pmid"]) == ("Neurosurgery", "Q1", "10.1000/e.1", "111")
    assert a["abstract"] == "Background First part. Methods: Second part."
    assert a["pub_types"] == ["Review"] and a["retraction"] == "retracted"
    assert (a["access_kind"], a["access_link"]) == ("open", A._pmc_pdf_url("PMC9"))
    assert (a["cited_by"], a["source"]) == (4, "Europe PMC")


def test_a_preprint_names_its_server_as_the_journal():
    a = A._europepmc_article(EPMC_PREPRINT)
    assert (a["journal"], a["pub_types"], a["author_list"]) == ("medRxiv", ["Preprint"], ["Doe J", "Example A"])
    assert a["access_kind"] is None and a["cited_by"] is None


def test_europe_pmc_strict_wants_every_word_in_title_or_abstract():
    assert A._europepmc_term("awake craniotomy") == 'TITLE_ABS:"awake" AND TITLE_ABS:"craniotomy"'
    assert A._europepmc_term("awake craniotomy", strict=False) == "awake craniotomy"
    assert A._europepmc_term('"awake craniotomy" AND SRC:PPR') == '"awake craniotomy" AND SRC:PPR'


def test_europe_pmc_adds_years_and_orders_by_date(answer):
    calls = answer({"hitCount": 1, "resultList": {"result": [EPMC_PREPRINT]}})
    arts, total = A.search_europepmc("glioma", 10, 2018, None, sort="date")
    p = calls.params()
    assert p["query"] == '(TITLE_ABS:"glioma") AND PUB_YEAR:[2018 TO 3000]'
    assert (p["resultType"], p["pageSize"], p["sort"]) == ("core", "10", "FIRST_PDATE_D desc")
    assert total == 1 and len(arts) == 1


def test_europe_pmc_load_more_keeps_only_the_next_batch(answer):
    records = [dict(EPMC_PREPRINT, doi=f"10.1101/p.{i}", title=f"Paper {i}") for i in range(25)]
    calls = answer({"hitCount": 25, "resultList": {"result": records}})
    arts, _ = A.search_europepmc("glioma", 10, None, None, offset=10)
    assert calls.params()["pageSize"] == "20"
    assert [a["title"] for a in arts] == [f"Paper {i}" for i in range(10, 20)]


def test_a_europe_pmc_refusal_says_what_it_said(answer):
    answer({"errMsg": "Invalid query syntax"}, 400)
    with pytest.raises(RuntimeError, match="Europe PMC rejected the query \\(400\\): Invalid query syntax"):
        A.search_europepmc("glioma ((", 10, None, None)


# ── Crossref ────────────────────────────────────────────────────────────────

def test_crossref_asks_for_papers_only_with_years_order_and_offset(answer):
    A.CONFIG["unpaywall_email"] = "someone@example.org"
    calls = answer({"message": {"total-results": 99, "items": [
        {"DOI": "10.1000/c.1", "title": ["A paper"], "type": "journal-article",
         "issued": {"date-parts": [[2020]]}, "is-referenced-by-count": 7}]}})
    arts, total = A.search_crossref("glioma", 10, 2019, None, sort="date", offset=30)
    p = calls.params()
    assert p["filter"] == ("type:journal-article,type:posted-content,type:proceedings-article,"
                           "type:book-chapter,from-pub-date:2019")
    assert (p["query"], p["rows"], p["offset"], p["sort"], p["order"]) == \
        ("glioma", "10", "30", "published", "desc")
    assert "abstract" in p["select"].split(",")
    assert "institution" not in p["select"].split(",")     # Crossref refuses it in a search
    assert "mailto:someone@example.org" in calls[-1]["headers"]["User-Agent"]
    assert total == 99 and (arts[0]["doi"], arts[0]["cited_by"], arts[0]["year"]) == ("10.1000/c.1", 7, "2020")


def test_a_crossref_refusal_says_what_it_said(answer):
    answer({"status": "failed", "message": [{"message": "Unknown filter"}]}, 400)
    with pytest.raises(RuntimeError, match="Crossref rejected the query \\(400\\): Unknown filter"):
        A.search_crossref("glioma", 10, None, None)


# ── IEEE Xplore ─────────────────────────────────────────────────────────────

IEEE_RECORD = {
    "doi": "10.1109/x.1", "title": "Decoding speech from <i>cortex</i>",
    "authors": {"authors": [{"full_name": "Ada Example", "author_order": 2},
                            {"full_name": "Jane Doe", "author_order": 1}]},
    "publication_title": "IEEE Transactions on Biomedical Engineering",
    "publication_year": 2024, "abstract": "An abstract.", "citing_paper_count": 3,
}


def test_ieee_without_a_key_is_not_asked(answer):
    calls = answer({})
    with pytest.raises(RuntimeError, match="No IEEE Xplore API key set"):
        A.search_ieee("bci", 10, None, None)
    assert calls == []


def test_ieee_is_asked_with_its_key_years_order_and_first_record(answer):
    A.CONFIG["ieee_api_key"] = "ieee-key"
    calls = answer({"total_records": 40, "articles": [IEEE_RECORD]})
    arts, total = A.search_ieee("brain computer interface", 10, 2020, 2025, sort="date", offset=10)
    p = calls.params()
    assert (p["querytext"], p["max_records"], p["start_record"]) == ("brain computer interface", "10", "11")
    assert (p["start_year"], p["end_year"], p["apikey"], p["format"]) == ("2020", "2025", "ieee-key", "json")
    assert (p["sort_field"], p["sort_order"]) == ("publication_year", "desc")
    a = arts[0]
    assert total == 40 and a["author_list"] == ["Jane Doe", "Ada Example"]
    assert (a["title"], a["year"], a["doi"], a["cited_by"], a["source"]) == \
        ("Decoding speech from cortex", "2024", "10.1109/x.1", 3, "IEEE Xplore")


@pytest.mark.parametrize("said, status, expected", [
    ("<h1>Developer Inactive</h1>", 403, "did not accept the API key \\(403: Developer Inactive\\)"),
    ("<h1>Account Over Queries Per Day Limit</h1>", 403, "daily allowance.*renews tomorrow"),
    ("<h1>Account Over Queries Per Second Limit</h1>", 403, "asked too fast"),
    (None, 0, "didn't respond"),
])
def test_an_ieee_refusal_says_why(answer, said, status, expected):
    A.CONFIG["ieee_api_key"] = "ieee-key"
    answer(said, status)
    with pytest.raises(RuntimeError, match=expected):
        A.search_ieee("bci", 10, None, None)


def test_ieee_is_asked_only_about_its_own_dois(answer):
    A.CONFIG["ieee_api_key"] = "ieee-key"
    calls = answer({"articles": [IEEE_RECORD]})
    arts = A.ieee_by_dois(["10.1109/x.1", "10.1000/other"])
    assert [c["url"] for c in calls if "10.1000" in urllib.parse.unquote(c["url"])] == []
    assert calls.params()["doi"] == "10.1109/x.1" and len(calls) == 1 and len(arts) == 1
    with pytest.raises(A.SourceCannotAnswer, match="10.1109"):
        A.ieee_by_dois(["10.1000/other"])


# ── Semantic Scholar ────────────────────────────────────────────────────────

S2_PAPER = {
    "paperId": "abc", "title": "A meta-analysis of awake surgery", "year": 2023,
    "authors": [{"authorId": "1", "name": "Jane Doe"}],
    "venue": "Neurosurg Rev", "journal": {"name": "Neurosurgical Review"},
    "externalIds": {"DOI": "10.1000/s.1", "PubMed": 3456},
    "abstract": "Text.", "citationCount": 9,
    "openAccessPdf": {"url": "https://europepmc.org/articles/PMC2/pdf", "status": "GREEN"},
    "publicationTypes": ["MetaAnalysis", "JournalArticle", "Review"],
}


def test_a_semantic_scholar_paper_reads_as_an_article():
    a = A._s2_article(S2_PAPER)
    assert (a["title"], a["year"], a["journal"]) == ("A meta-analysis of awake surgery", "2023", "Neurosurgical Review")
    assert (a["doi"], a["pmid"], a["cited_by"]) == ("10.1000/s.1", "3456", 9)
    assert a["pub_types"] == ["Meta-analysis", "Review"]
    assert (a["access_kind"], a["access_link"]) == ("open", "https://europepmc.org/articles/PMC2/pdf")
    bare = A._s2_article(dict(S2_PAPER, journal=None, openAccessPdf={"url": "", "status": None}))
    assert (bare["journal"], bare["access_kind"]) == ("Neurosurg Rev", None)


def test_semantic_scholar_without_a_key_is_not_asked(answer):
    calls = answer({})
    with pytest.raises(RuntimeError, match="No Semantic Scholar API key set"):
        A.search_semantic_scholar("glioma", 10, None, None)
    assert calls == []


def test_semantic_scholar_by_relevance_pages_by_offset(answer):
    A.CONFIG["semantic_scholar_api_key"] = "s2-key"
    calls = answer({"total": 500, "data": [S2_PAPER]})
    arts, total = A.search_semantic_scholar("glioma", 10, 2018, None, offset=20)
    p = calls.params()
    assert calls.path() == "/graph/v1/paper/search"
    assert (p["offset"], p["limit"], p["year"]) == ("20", "10", "2018-")
    assert calls[-1]["headers"]["x-api-key"] == "s2-key"
    assert total == 500 and len(arts) == 1


def test_semantic_scholar_newest_first_reads_further_into_the_bulk_batch(answer):
    A.CONFIG["semantic_scholar_api_key"] = "s2-key"
    papers = [dict(S2_PAPER, title=f"Paper {i}", externalIds={}) for i in range(30)]
    calls = answer({"total": 30, "data": papers})
    arts, _ = A.search_semantic_scholar("glioma", 10, None, 2024, sort="date", offset=10)
    p = calls.params()
    assert calls.path() == "/graph/v1/paper/search/bulk"
    assert (p["sort"], p["year"]) == ("publicationDate:desc", "-2024")
    assert "offset" not in p and "limit" not in p
    assert [a["title"] for a in arts] == [f"Paper {i}" for i in range(10, 20)]


def test_semantic_scholar_looks_dois_up_in_one_call(answer):
    A.CONFIG["semantic_scholar_api_key"] = "s2-key"
    calls = answer([S2_PAPER, None])
    arts = A.semantic_scholar_by_dois(["10.1000/s.1", "10.1000/unknown"])
    assert calls.path() == "/graph/v1/paper/batch"
    assert json.loads(calls[-1]["data"]) == {"ids": ["DOI:10.1000/s.1", "DOI:10.1000/unknown"]}
    assert [a["doi"] for a in arts] == ["10.1000/s.1"]


def test_a_refused_semantic_scholar_key_says_so(answer):
    A.CONFIG["semantic_scholar_api_key"] = "s2-key"
    answer({"message": "Forbidden"}, 403)
    with pytest.raises(RuntimeError, match="did not accept the API key \\(403\\)"):
        A.search_semantic_scholar("glioma", 10, None, None)


# ── CORE ────────────────────────────────────────────────────────────────────

CORE_WORK = {
    "title": "An  open thesis", "authors": [{"name": "Doe, J."}], "yearPublished": 2019,
    "doi": "10.1000/core.1", "abstract": " Text. ", "downloadUrl": "https://core.ac.uk/download/1.pdf",
    "journals": [{"title": "Neurosurgical Focus"}], "publisher": "A Publisher",
    "pubmedId": "777", "citationCount": 2,
}


def test_a_core_work_reads_as_an_article():
    a = A._core_article(CORE_WORK)
    assert (a["title"], a["year"], a["journal"], a["quartile"]) == ("An open thesis", "2019", "Neurosurgical Focus", "Q2")
    assert (a["doi"], a["pmid"], a["abstract"], a["source"]) == ("10.1000/core.1", "777", "Text.", "CORE")
    assert (a["access_kind"], a["access_link"]) == ("open", "https://core.ac.uk/download/1.pdf")


def test_a_year_in_another_calendar_is_no_year():
    assert A._core_article(dict(CORE_WORK, yearPublished=2550))["year"] == "n.d."
    assert A._core_article(dict(CORE_WORK, yearPublished=None, journals=[]))["journal"] == "A Publisher"


def test_core_wants_every_word_and_the_years(answer):
    calls = answer({"totalHits": 3, "results": [CORE_WORK]})
    arts, total = A.search_core("awake craniotomy", 10, 2018, 2020, offset=10)
    p = calls.params()
    assert p["q"] == "(awake AND craniotomy) AND yearPublished>=2018 AND yearPublished<=2020"
    assert (p["limit"], p["offset"]) == ("10", "10") and "sort" not in p
    assert "Authorization" not in calls[-1]["headers"]
    assert total == 3 and len(arts) == 1


def test_core_newest_first_leaves_out_impossible_years_and_sends_the_key(answer):
    A.CONFIG["core_api_key"] = "core-key"
    calls = answer({"totalHits": 0, "results": []})
    A.search_core('"awake craniotomy"', 10, None, None, sort="date")
    p = calls.params()
    assert p["q"] == f'("awake craniotomy") AND yearPublished<={datetime.now().year + 1}'
    assert p["sort"] == "publishedDate:desc"
    assert calls[-1]["headers"]["Authorization"] == "Bearer core-key"


def test_core_busy_without_a_key_says_what_a_key_does(answer):
    answer(None, 429)
    with pytest.raises(RuntimeError, match="few searches a minute.*CORE API key"):
        A.search_core("glioma", 10, None, None)


# ── Search by DOI ───────────────────────────────────────────────────────────

def _asking(asked):
    def fn(query, max_r, y_from, y_to, **kw):
        asked.append((query, y_from, y_to))
        return [], 0
    return fn


@pytest.mark.parametrize("key, term", [
    ("europepmc", 'DOI:"10.1000/a" OR DOI:"10.1000/b"'),
    ("core", 'doi:"10.1000/a" OR doi:"10.1000/b"'),
])
def test_each_new_database_is_asked_by_its_own_doi_field(key, term):
    asked = []
    A.doi_lookup(key, _asking(asked), ["10.1000/a", "10.1000/b"])
    assert asked == [(term, None, None)]


@pytest.mark.parametrize("key, helper", [("openalex", "openalex_by_dois"),
                                         ("semanticscholar", "semantic_scholar_by_dois"),
                                         ("ieee", "ieee_by_dois")])
def test_the_others_look_dois_up_their_own_way(monkeypatch, key, helper):
    monkeypatch.setattr(A, helper, lambda dois: [article(doi=d) for d in reversed(dois)])
    arts, n = A.doi_lookup(key, None, ["10.1000/a", "10.1000/b"])
    assert [a["doi"] for a in arts] == ["10.1000/a", "10.1000/b"] and n == 2


def test_a_ticked_crossref_is_asked_once_and_still_reports_unknown_dois(client, auth, monkeypatch):
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)
    pubmed = lambda q, *a, **k: ([article(doi="10.1000/a")], 0)  # noqa: E731
    monkeypatch.setattr(A, "SOURCES", [(k, l, pubmed if k == "pubmed" else f, s)
                                       for k, l, f, s in A.SOURCES])
    asked = []

    def records(dois, report=None):
        asked.append(list(dois))
        report["unknown"], report["failed"] = ["10.1000/typo"], []
        return [article(doi="10.1000/a", source="Crossref")], 0
    monkeypatch.setattr(A, "crossref_records", records)
    events = sse_events(client.post("/search_stream", headers=auth, base_url=BASE, json={
        "query": "10.1000/a 10.1000/typo", "sources": ["pubmed", "crossref"]}))
    assert asked == [["10.1000/a", "10.1000/typo"]]
    assert [e["source"] for e in events if e["type"] == "source_start"] == ["PubMed", "Crossref"]
    missing = [e for e in events if e["type"] == "doi_missing"]
    assert len(missing) == 1 and missing[0]["count"] == 1 and "10.1000/typo" in missing[0]["text"]


# ── Keys: without one the source says so; Settings keeps them ───────────────

@pytest.mark.parametrize("key, name", [("ieee", "an IEEE Xplore"),
                                       ("semanticscholar", "a Semantic Scholar")])
def test_a_keyed_source_without_its_key_says_so_in_the_window(client, auth, monkeypatch, key, name):
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)
    events = sse_events(client.post("/search_stream", headers=auth, base_url=BASE,
                                    json={"query": "glioma", "sources": [key]}))
    err = next(e for e in events if e["type"] == "source_error")
    assert err["text"] == f"Add {name} API key in Settings to search this source."


def test_merged_search_reports_a_missing_key_never_as_zero(monkeypatch):
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)
    rep = A.merged_search("glioma", sources=("ieee", "semanticscholar"))["sources"]
    assert {k: r["status"] for k, r in rep.items()} == {"semanticscholar": "no key", "ieee": "no key"}


NEW_KEYS = ("ieee_api_key", "semantic_scholar_api_key", "openalex_api_key", "core_api_key")


def test_settings_keeps_the_new_keys_and_shows_them_masked(client, auth):
    body = {k: f"{k}-value-1234" for k in NEW_KEYS}
    assert client.post("/settings", json=body, headers=auth, base_url=BASE).json["ok"]
    shown = client.get("/settings", headers=auth, base_url=BASE).json
    for k in NEW_KEYS:
        assert A.CONFIG[k] == f"{k}-value-1234"
        assert shown[k].endswith("1234") and "value" not in shown[k]
    client.post("/settings", json={"clear": ["core_api_key"]}, headers=auth, base_url=BASE)
    assert A.CONFIG["core_api_key"] == ""


def test_the_new_keys_are_secrets():
    assert set(NEW_KEYS) <= set(A.SECRET_KEYS)


def test_a_keyed_database_is_ticked_at_start_only_with_its_key(client, auth):
    client.post("/sources", json={"sources": ["pubmed", "ieee", "openalex"]}, headers=auth, base_url=BASE)
    html = client.get("/", headers=auth, base_url=BASE).get_data(as_text=True)
    assert re.findall(r'class="db-item checked" data-db="([a-z]+)"', html) == ["pubmed", "openalex"]
    A.CONFIG["ieee_api_key"] = "ieee-key"
    html = client.get("/", headers=auth, base_url=BASE).get_data(as_text=True)
    assert re.findall(r'class="db-item checked" data-db="([a-z]+)"', html) == ["pubmed", "openalex", "ieee"]


# ── Every source is known everywhere it is listed ───────────────────────────

def test_every_source_is_in_the_panel_the_chip_and_the_menus():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    keys = [k for k, *_ in A.SOURCES]
    assert sorted(re.findall(r'data-db="([a-z]+)"', html)) == sorted(keys)
    short = re.search(r"const _DB_SHORT = \{(.*?)\};", js, re.S).group(1)
    assert sorted(re.findall(r"(\w+):", short)) == sorted(keys)
    assert [k for k, _ in appmenu.SOURCES if k != "all"] and \
        sorted(k for k, _ in appmenu.SOURCES if k != "all") == sorted(keys)


def test_every_keyed_source_has_its_prompt_badge_and_settings_field():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    needs = dict(re.findall(r'data-db="([a-z]+)" data-needs-key="([a-z]+)"', html))
    assert needs == {k: k for k in A._KEY_REQUIRED}
    setting = dict(re.findall(r"(\w+): '(\w+_api_key)'",
                              re.search(r"const DB_KEY_SETTING = \{(.*?)\};", js, re.S).group(1)))
    assert setting == {k: s for k, (s, _name) in A._KEY_REQUIRED.items()}
    info = re.search(r"const DB_KEY_INFO = \{(.*?)\n\};", js, re.S).group(1)
    for k in A._KEY_REQUIRED:
        assert re.search(rf"^  {k}: \{{", info, re.M), k
        assert f'id="badge_{k}"' in html
    for secret in A.SECRET_KEYS:
        assert re.search(rf"{secret}:\s+'set_\w+'", js), secret                    # loaded
        assert re.search(rf"{secret}:\s+document\.getElementById\('set_\w+'\)", js), secret  # saved


# ── Google Scholar: opened, not asked ───────────────────────────────────────

def test_the_scholar_button_sits_in_the_databases_panel_and_opens_a_window():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    panel = re.search(r'<div class="dock-panel" id="panelSources".*?\n</div>', html, re.S).group(0)
    assert 'onclick="openGoogleScholar()"' in panel
    fn = re.search(r"\nfunction openGoogleScholar\(\) \{.*?\n\}", js, re.S).group(0)
    assert "openInAppBrowser(scholarUrl(" in fn          # its own window, never the main one
    # nothing to search for (no words, no author) is a popup, not a blank Scholar page
    assert re.search(r"if \(!q && !author\) \{\s*fail\(", fn)
    assert "google" not in [k for k, *_ in A.SOURCES]      # not a source: nothing is merged from it

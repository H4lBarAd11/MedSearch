"""A search narrowed to an author or an institution: how a name is read, how
each source is asked for it in its own syntax, the sources that can't and
say so, the stream with an empty box, the suggestions while typing, and saved
searches keeping both. Placeholder names only; nothing reaches the network."""
import json
import urllib.parse

import pytest

import app as A
from conftest import BASE, article, sse_events

ORCID = "0000-0002-1825-0097"          # ORCID's own documentation example
OPENALEX_GET = A._openalex_get         # the real one, for tests that fake the names lookup


def picked_author(**kw):
    return A.people_filter({"name": "Jane A. Doe", "orcid": f"https://orcid.org/{ORCID}",
                            "openalex": ["https://openalex.org/A111", "A222"], **kw})


@pytest.fixture
def institution_names(monkeypatch):
    """OpenAlex knows I900 by three names; every lookup is counted."""
    asked = []

    def get(path, params, missing=None):
        asked.append(path)
        return {"display_name": "Example University Hospital",
                "display_name_alternatives": ["Ospedale Universitario Esempio", "EUH",
                                              "example university hospital"]}
    monkeypatch.setattr(A, "_openalex_get", get)
    A._INSTITUTION_NAMES.clear()
    yield asked
    A._INSTITUTION_NAMES.clear()


@pytest.fixture
def both(institution_names):
    return A.people_filter({"name": "Jane A. Doe", "orcid": ORCID, "openalex": ["A111"]},
                           {"name": "Example University Hospital", "openalex": "I900"})


@pytest.fixture
def no_enrich(monkeypatch):
    monkeypatch.setattr(A, "enrich_access", lambda arts: arts)
    monkeypatch.setattr(A, "fill_abstracts_from_pubmed", lambda arts: arts)
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)


class Asked(list):
    """The URLs asked, and `reply[0]`: what every call answers."""


@pytest.fixture
def calls(monkeypatch, no_enrich):
    """Every fetch_json / http_get answers `reply[0]`; returns the URLs asked."""
    asked, reply = Asked(), [({}, 200)]

    def fake(url, *a, **k):
        asked.append(url)
        body, status = reply[0]
        return body, status
    monkeypatch.setattr(A, "fetch_json", fake)
    monkeypatch.setattr(A, "http_get", lambda url, *a, **k:
                        (asked.append(url), (reply[0][0] if isinstance(reply[0][0], str)
                                             else json.dumps(reply[0][0]), reply[0][1]))[1])
    asked.reply = reply
    return asked


def params(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


# ── Reading a name ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, parts", [
    ("Doe, Jane A.", ("Doe", "Jane A.")),
    ("Jane A. Doe", ("Doe", "Jane A.")),
    ("Ludwig van Gogh", ("van Gogh", "Ludwig")),
    ("Ana de la Cruz", ("de la Cruz", "Ana")),
    ("Doe JA", ("Doe", "JA")),
    ("van Gogh L.", ("van Gogh", "L.")),
    ("Doe", ("Doe", "")),
])
def test_a_name_is_read_either_way_round(name, parts):
    assert A._name_parts(name) == parts


def test_a_picked_author_keeps_its_orcid_and_openalex_ids():
    au = picked_author()["author"]
    assert (au["name"], au["family"], au["initial"]) == ("Jane A. Doe", "Doe", "J")
    assert au["orcid"] == ORCID and au["openalex"] == ["A111", "A222"]


def test_what_is_not_an_id_or_an_orcid_is_dropped_and_quotes_are_taken_out():
    au = A.people_filter({"name": 'Jane "x" (Doe)', "orcid": "not-an-orcid",
                          "openalex": ["W123", "A1", 5]})["author"]
    assert au["name"] == "Jane x Doe" and au["orcid"] is None and au["openalex"] == ["A1"]


@pytest.mark.parametrize("given", [None, "", "   ", "1234", {"name": ""}, {"name": "()"}, 7])
def test_no_name_is_no_filter(given):
    assert A.people_filter(given, given) is None


def test_a_typed_author_is_the_words_as_written():
    au = A.people_filter("Doe J")["author"]
    assert (au["family"], au["initial"], au["openalex"], au["orcid"]) == ("Doe", "J", [], None)
    assert A.people_filter("Doe, J")["author"]["family"] == "Doe"


def test_a_picked_institution_goes_by_all_its_names_asked_once(institution_names):
    inst = A.people_filter(None, {"name": "Example University Hospital", "openalex": "I900"})
    assert inst["institution"]["names"] == ["Example University Hospital",
                                            "Ospedale Universitario Esempio"]   # no acronym, no repeat
    A.people_filter(None, {"name": "Example University Hospital", "openalex": "I900"})
    assert institution_names == ["/institutions/I900"]


def test_an_institution_openalex_cannot_describe_is_searched_by_its_name(monkeypatch):
    A._INSTITUTION_NAMES.clear()

    def down(*a, **k):
        raise RuntimeError("OpenAlex didn't respond.")
    monkeypatch.setattr(A, "_openalex_get", down)
    inst = A.people_filter(None, {"name": "Example Hospital", "openalex": "I901"})["institution"]
    assert inst["names"] == ["Example Hospital"] and "I901" not in A._INSTITUTION_NAMES


@pytest.mark.parametrize("person, wrote", [
    ("Doe, Jane", True), ("J. Doe", True), ("Doe J", True), ("John Doe", True),
    ("Doe A", False), ("Doegan J", False), ("Jane Doer", False),
])
def test_a_paper_is_checked_for_the_author_by_family_name_and_initial(person, wrote):
    au = A.people_filter("Jane Doe")["author"]
    assert A._wrote({"author_list": [person]}, au) is wrote


def test_accents_and_hyphens_do_not_hide_an_author():
    au = A.people_filter("María García-López")["author"]
    assert A._wrote({"author_list": ["Garcia-Lopez, M."]}, au)
    assert A._wrote({"author_list": ["M García López"]}, au)


# ── Each source, in its own syntax ──────────────────────────────────────────

def test_pubmed_by_name_or_orcid_and_by_each_name_of_the_place(calls, both):
    calls.reply[0] = ({"esearchresult": {"idlist": [], "count": "0"}}, 200)
    A.search_pubmed("glioma", 10, None, None, people=both)
    assert params(calls[0])["term"] == (
        f'((glioma[tiab]) AND (Doe J[au] OR {ORCID}[auid])) AND '
        '("Example University Hospital"[ad] OR "Ospedale Universitario Esempio"[ad])')


def test_cochrane_keeps_its_journal_and_an_empty_box_asks_only_for_the_author(calls):
    calls.reply[0] = ({"esearchresult": {"idlist": [], "count": "0"}}, 200)
    A.search_cochrane("", 10, None, None, people=A.people_filter("Jane Doe"))
    assert params(calls[0])["term"] == '("Cochrane Database Syst Rev"[ta]) AND Doe J[au]'


def test_europe_pmc_by_name_or_orcid_and_affiliation(calls, both):
    calls.reply[0] = ({"hitCount": 0, "resultList": {"result": []}}, 200)
    A.search_europepmc("glioma", 10, None, None, people=both)
    assert params(calls[0])["query"] == (
        f'(TITLE_ABS:"glioma") AND (AUTH:"Doe J" OR AUTHORID:"{ORCID}") AND '
        '(AFF:"Example University Hospital" OR AFF:"Ospedale Universitario Esempio")')


def test_scopus_by_author_name_or_orcid_and_affiliation(monkeypatch, no_enrich, both):
    asked = []
    monkeypatch.setattr(A, "scopus_entries", lambda q, *a: (asked.append(q), ([], 0))[1])
    A.search_scopus("glioma", 10, 2020, None, people=both)
    assert asked == [f"(glioma) AND (AUTHOR-NAME(Doe, J) OR ORCID({ORCID})) AND "
                     '(AFFIL("Example University Hospital") OR AFFIL("Ospedale Universitario Esempio"))'
                     " AND PUBYEAR > 2019 AND PUBYEAR < 2100"]


def test_web_of_science_by_author_identifier_and_organisation(calls, both):
    A.CONFIG["wos_api_key"] = "wos-key"
    calls.reply[0] = ({"hits": []}, 200)
    A.search_wos("glioma", 10, None, None, people=both)
    assert params(calls[0])["q"] == (
        f'(TS=(glioma)) AND (AU=(Doe J*) OR AI=({ORCID})) AND '
        'OG=("Example University Hospital" OR "Ospedale Universitario Esempio")')


def test_openalex_picked_is_exact_by_id_and_typed_is_by_the_printed_words(calls, both, monkeypatch):
    monkeypatch.setattr(A, "_openalex_get", OPENALEX_GET)    # `both` faked it to name I900
    calls.reply[0] = ({"meta": {}, "results": []}, 200)
    A.search_openalex("glioma", 10, None, None, people=both)
    assert params(calls[0])["filter"] == ("authorships.author.id:A111,"
                                          "authorships.institutions.lineage:I900,"
                                          "title_and_abstract.search:glioma")
    A.search_openalex("glioma", 10, None, None,
                      people=A.people_filter("Doe, Jane", "Example, Hospital"))
    assert params(calls[1])["filter"].startswith("raw_author_name.search:Doe  Jane,"
                                                 "raw_affiliation_strings.search:Example  Hospital,")


def test_openalex_with_an_empty_box_lists_the_most_cited_first(calls):
    calls.reply[0] = ({"meta": {}, "results": []}, 200)
    A.search_openalex("", 10, None, None, people=picked_author())
    p = params(calls[0])
    assert p["filter"] == "authorships.author.id:A111|A222" and "search" not in p
    assert p["sort"] == "cited_by_count:desc"
    A.search_openalex("", 10, None, None, sort="date", people=picked_author())
    assert params(calls[1])["sort"] == "publication_date:desc"


def test_crossref_ranks_by_author_and_keeps_only_their_papers(calls):
    calls.reply[0] = ({"message": {"total-results": 2, "items": [
        {"DOI": "10.1/a", "title": ["Theirs"], "author": [{"family": "Doe", "given": "Jane"}]},
        {"DOI": "10.1/b", "title": ["Not"], "author": [{"family": "Doe", "given": "Adam"}]}]}}, 200)
    arts, _ = A.search_crossref("", 10, None, None, people=A.people_filter("Jane Doe"))
    p = params(calls[0])
    assert p["query.author"] == "Jane Doe" and "query" not in p
    assert [a["doi"] for a in arts] == ["10.1/a"]


def test_ieee_by_author_and_affiliation_with_no_words_needed(calls, both):
    A.CONFIG["ieee_api_key"] = "ieee-key"
    calls.reply[0] = ({"articles": []}, 200)
    A.search_ieee("", 10, None, None, people=both)
    p = params(calls[0])
    assert (p["author"], p["affiliation"]) == ("Jane A. Doe", "Example University Hospital")
    assert "querytext" not in p


def test_core_by_family_name_then_checked_for_the_initial(calls):
    calls.reply[0] = ({"totalHits": 2, "results": [
        {"title": "Theirs", "authors": [{"name": "Doe, Jane"}]},
        {"title": "Not", "authors": [{"name": "Doe, Adam"}]}]}, 200)
    arts, _ = A.search_core("glioma", 10, None, None, people=A.people_filter("Jane Doe"))
    assert params(calls[0])["q"] == '((title:"glioma" OR abstract:"glioma")) AND authors:"Doe"'
    assert [a["title"] for a in arts] == ["Theirs"]


def test_arxiv_by_family_and_first_name_then_checked(calls):
    calls.reply[0] = ("""<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Theirs</title><published>2024-01-01</published><id>http://arxiv.org/abs/1</id>
        <author><name>Jane Doe</name></author></entry>
      <entry><title>Not</title><published>2024-01-01</published><id>http://arxiv.org/abs/2</id>
        <author><name>Adam Doe</name></author></entry></feed>""", 200)
    arts, _ = A.search_arxiv("neural networks", 10, None, None,
                             people=A.people_filter("Jane A. Doe"))
    assert params(calls[0])["search_query"] == "(all:neural networks) AND au:Doe AND au:Jane"
    assert [a["title"] for a in arts] == ["Theirs"]


def test_clinicaltrials_by_official_and_by_sponsor_or_site(calls, both):
    calls.reply[0] = ({"studies": []}, 200)
    A.search_clinicaltrials("glioma", 10, None, None, people=both)
    assert params(calls[0])["query.term"] == (
        '(glioma) AND AREA[OverallOfficialName]"Doe" AND '
        '(AREA[LeadSponsorName]"Example University Hospital" OR '
        'AREA[LocationFacility]"Example University Hospital" OR '
        'AREA[LeadSponsorName]"Ospedale Universitario Esempio" OR '
        'AREA[LocationFacility]"Ospedale Universitario Esempio")')


@pytest.mark.parametrize("fn, label, author_ok", [
    (A.search_semantic_scholar, "Semantic Scholar", False),
    (A.search_core, "CORE", True),
    (A.search_crossref, "Crossref", True),
    (A.search_arxiv, "arXiv", True),
])
def test_a_source_that_keeps_no_institutions_says_so_and_asks_nothing(calls, fn, label, author_ok):
    with pytest.raises(A.SourceCannotAnswer, match=f"{label} can't be searched by institution, "
                                                    "so it was left out of this search"):
        fn("glioma", 10, None, None, people=A.people_filter(None, "Example Hospital"))
    if not author_ok:
        with pytest.raises(A.SourceCannotAnswer, match="by author"):
            fn("glioma", 10, None, None, people=A.people_filter("Jane Doe"))
    assert calls == []


# ── The search stream ───────────────────────────────────────────────────────

def _fake_sources(monkeypatch, asked):
    def make(key):
        def run(query, max_r, y_from, y_to, **kw):
            asked.append((key, query, kw.get("people")))
            if key == "semanticscholar" and kw.get("people"):
                raise A.SourceCannotAnswer("Semantic Scholar can't be searched by author.")
            return [article(title=f"{key} paper", doi=f"10.1/{key}")], 0
        return run
    monkeypatch.setattr(A, "SOURCES", [(k, l, make(k), s) for k, l, _f, s in A.SOURCES])
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)
    monkeypatch.setattr(A, "get_mesh", lambda q: pytest.fail("MeSH asked with nothing to map"))


def _search(client, auth, **body):
    payload = {"query": "", "sources": ["pubmed"], "max_results": 10, **body}
    return sse_events(client.post("/search_stream", json=payload, headers=auth, base_url=BASE))


def test_an_empty_box_with_an_author_lists_their_papers(client, auth, monkeypatch):
    asked = []
    _fake_sources(monkeypatch, asked)
    A.CONFIG["semantic_scholar_api_key"] = "s2-key"
    events = _search(client, auth, sources=["pubmed", "semanticscholar"],
                     author={"name": "Jane Doe", "openalex": ["A111"]})
    assert sorted((k, q) for k, q, _p in asked) == [("pubmed", ""), ("semanticscholar", "")]
    assert next(p for k, _q, p in asked if k == "pubmed")["author"]["openalex"] == ["A111"]
    assert [e["article"]["title"] for e in events if e["type"] == "article"] == ["pubmed paper"]
    s2 = next(e for e in events if e["type"] == "source_done" and e["source"] == "Semantic Scholar")
    assert "can't be searched by author" in s2["note"]
    assert not any(e["type"] == "source_error" for e in events)
    assert A.SESSION["query"] == "author: Jane Doe"     # what the AI and the export are told
    assert A.SESSION["history"] == []                   # nothing to put back in the box


def test_an_empty_box_and_no_filter_is_still_refused(client, auth, monkeypatch):
    _fake_sources(monkeypatch, [])
    assert _search(client, auth)[0] == {"type": "error", "text": "Empty query"}


def test_words_and_filters_are_described_and_the_words_kept_in_history(client, auth, monkeypatch):
    asked = []
    _fake_sources(monkeypatch, asked)
    monkeypatch.setattr(A, "get_mesh", lambda q: [])
    _search(client, auth, query="glioma", institution={"name": "Example Hospital"})
    assert A.SESSION["query"] == "glioma (institution: Example Hospital)"
    assert A.SESSION["history"] == ["glioma"]
    assert asked[0][2]["institution"]["names"] == ["Example Hospital"]


def test_load_more_for_another_author_is_refused(client, auth, monkeypatch):
    _fake_sources(monkeypatch, [])
    _search(client, auth, author={"name": "Jane Doe"})
    assert _search(client, auth, author={"name": "Jane Doe"}, load_more=True)[0]["type"] != "error"
    events = _search(client, auth, author={"name": "Adam Doe"}, load_more=True)
    assert events[0]["type"] == "error"


def test_a_doi_search_ignores_the_filters(client, auth, monkeypatch):
    asked = []
    _fake_sources(monkeypatch, asked)
    monkeypatch.setattr(A, "crossref_records", lambda dois, report=None: ([], 0))
    _search(client, auth, query="10.1000/pubmed", author={"name": "Jane Doe"})
    assert asked == [("pubmed", '"10.1000/pubmed"[AID]', None)]
    assert A.SESSION["query"] == "10.1000/pubmed"


def test_merged_search_takes_an_author_and_reports_who_could_not(monkeypatch):
    asked = []
    _fake_sources(monkeypatch, asked)
    A.CONFIG["semantic_scholar_api_key"] = "s2-key"
    out = A.merged_search("", sources=("pubmed", "semanticscholar"), author="Jane Doe")
    assert out["sources"]["pubmed"]["status"] == "ok"
    assert out["sources"]["semanticscholar"]["status"] == "not indexed"
    assert next(p for k, _q, p in asked if k == "pubmed")["author"]["family"] == "Doe"


# ── Suggestions while typing ────────────────────────────────────────────────

def test_one_person_split_across_openalex_records_is_one_suggestion(client, auth, monkeypatch):
    seen = []

    def get(path, params, missing=None):
        seen.append((path, params))
        return {"results": [
            {"id": "https://openalex.org/A1", "display_name": "Jane Doe", "hint": "A Hospital, Italy",
             "works_count": 700, "external_id": f"https://orcid.org/{ORCID}"},
            {"id": "https://openalex.org/A2", "display_name": "Jane Doe", "hint": "A Hospital, Italy",
             "works_count": 20, "external_id": f"https://orcid.org/{ORCID}"},
            {"id": "https://openalex.org/A3", "display_name": "Jane Doe", "hint": "Elsewhere",
             "works_count": 5, "external_id": None}]}
    monkeypatch.setattr(A, "_openalex_get", get)
    r = client.get("/people/suggest?kind=author&q=jane doe", headers=auth, base_url=BASE)
    assert seen == [("/autocomplete/authors", {"q": "jane doe"})]
    assert r.json["items"] == [
        {"name": "Jane Doe", "hint": "A Hospital, Italy", "works": 720, "orcid": ORCID,
         "openalex": ["A1", "A2"]},
        {"name": "Jane Doe", "hint": "Elsewhere", "works": 5, "orcid": None, "openalex": ["A3"]}]


def test_an_institution_suggestion_carries_its_id(client, auth, monkeypatch):
    monkeypatch.setattr(A, "_openalex_get", lambda path, params, missing=None: {"results": [
        {"id": "https://openalex.org/I9", "display_name": "Example Hospital", "hint": "Milan, Italy",
         "works_count": 100, "external_id": "https://ror.org/x"}]})
    r = client.get("/people/suggest?kind=institution&q=exam", headers=auth, base_url=BASE)
    assert r.json["items"] == [{"name": "Example Hospital", "hint": "Milan, Italy", "works": 100,
                                "openalex": "I9"}]


def test_suggestions_are_refused_for_anything_else_and_say_why_they_failed(client, auth, monkeypatch):
    assert client.get("/people/suggest?kind=journal&q=xy", headers=auth, base_url=BASE).status_code == 400
    assert client.get("/people/suggest?kind=author&q=x", headers=auth, base_url=BASE).json["items"] == []

    def down(*a, **k):
        raise RuntimeError("OpenAlex didn't respond. Check your connection and try again.")
    monkeypatch.setattr(A, "_openalex_get", down)
    r = client.get("/people/suggest?kind=author&q=jane", headers=auth, base_url=BASE)
    assert r.status_code == 502 and "didn't respond" in r.json["message"]
    assert client.get("/people/suggest?kind=author&q=jane", base_url=BASE).status_code == 403


# ── Saved searches keep both ────────────────────────────────────────────────

def test_a_saved_search_keeps_the_author_and_institution_and_shows_them(client, auth):
    A.write_saved([])
    r = client.post("/saved", headers=auth, base_url=BASE, json={
        "name": "", "query": "", "sources": ["pubmed"],
        "author": {"name": "Jane Doe", "orcid": ORCID, "openalex": ["A1", "W9"], "hint": "A Hospital",
                   "extra": "dropped"},
        "institution": {"name": "Example Hospital", "openalex": "I9"}})
    s = r.json["saved"][-1]
    assert s["name"] == "Untitled"
    assert s["author"] == {"name": "Jane Doe", "openalex": ["A1"], "orcid": ORCID, "hint": "A Hospital"}
    assert s["institution"] == {"name": "Example Hospital", "openalex": "I9"}
    html = client.get("/", headers=auth, base_url=BASE).get_data(as_text=True)
    assert "author: Jane Doe; institution: Example Hospital" in html


def test_the_same_words_with_another_author_is_another_saved_search(client, auth):
    A.write_saved([])
    for who in ("Jane Doe", "Adam Doe"):
        client.post("/saved", headers=auth, base_url=BASE,
                    json={"name": "glioma", "query": "glioma", "author": {"name": who}})
    assert [s["author"]["name"] for s in A.load_saved()] == ["Jane Doe", "Adam Doe"]


# ── The window's wiring ─────────────────────────────────────────────────────

from pathlib import Path                                         # noqa: E402
import re                                                        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def js_function(name):
    return re.search(rf"\n(?:async )?function {name}\(.*?\n\}}", JS, re.S).group(0)


def test_the_fields_sit_in_options_and_the_chips_in_the_top_bar():
    options = re.search(r'<div class="dock-panel" id="panelOptions".*?\n</div>', HTML, re.S).group(0)
    for kind in ("author", "institution"):
        assert f'id="{kind}Input" data-kind="{kind}"' in options
        assert f'id="{kind}List" role="listbox"' in options
    topbar = re.search(r'<header class="topbar".*?</header>', HTML, re.S).group(0)
    assert 'id="peopleChips"' in topbar


def test_a_search_sends_both_and_find_more_keeps_them():
    run = js_function("runSearch")
    assert "author:      who.author," in run and "institution: who.institution," in run
    assert "author: prev.author, institution: prev.institution" in run
    assert re.search(r"if \(!query && !who\.author && !who\.institution\) \{\s*fail\(", run)


def test_home_clears_them_and_a_saved_search_puts_them_back():
    home, saved = js_function("resetToHome"), js_function("runSaved")
    assert "clearPeople('author');" in home and "clearPeople('institution');" in home
    assert "setPerson('author', s.author || null);" in saved
    assert "setPerson('institution', s.institution || null);" in saved


def test_a_search_by_filter_alone_is_not_put_in_the_history():
    assert "if (query) updateHistory(query);" in js_function("finishSearch")


def test_typing_over_a_picked_name_makes_it_a_typed_one():
    listener = re.search(r"document\.querySelectorAll\('\.people-input'\)\.forEach.*?\n\}\);", JS, re.S).group(0)
    assert "people[kind] = text ? {name: text} : null;" in listener
    assert re.search(r"e\.key === 'Escape' && !list\.hidden\) \{\s*e\.preventDefault\(\); e\.stopPropagation\(\);",
                     listener)     # Escape closes the list, not the whole Options panel

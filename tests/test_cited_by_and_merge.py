""""Cited by", Scopus abstracts from PubMed, and the merged multi-source list.
Every outside service is faked at the HTTP helpers (fetch_json / http_get),
routed by URL, so the parsing of each answer is exercised too."""
import re
import urllib.parse

import pytest

import app as A
from conftest import BASE, article


# ── Fakes ───────────────────────────────────────────────────────────────────

def pm_xml(*recs):
    """An efetch answer holding (pmid, doi, abstract, year) records."""
    arts = "".join(f"""<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article>
      <Journal><Title>NeuroImage</Title><JournalIssue><PubDate><Year>{year}</Year></PubDate></JournalIssue></Journal>
      <ArticleTitle>Paper {pmid}</ArticleTitle>
      <Abstract><AbstractText>{abstract}</AbstractText></Abstract>
      <AuthorList><Author><LastName>Olivetti</LastName><ForeName>Emanuele</ForeName></Author></AuthorList>
      </Article></MedlineCitation>
      <PubmedData><ArticleIdList><ArticleId IdType="doi">{doi}</ArticleId></ArticleIdList></PubmedData>
      </PubmedArticle>""" for pmid, doi, abstract, year in recs)
    return f"<PubmedArticleSet>{arts}</PubmedArticleSet>"


def scopus_page(entries, total=None):
    return {"search-results": {"opensearch:totalResults": str(len(entries) if total is None else total),
                               "entry": entries or [{"@_fa": "true", "error": "Result set was empty"}]}}


def scopus_entry(doi, title="A Scopus paper", year="2024", eid=None):
    e = {"dc:title": title, "dc:creator": "Porro-Muñoz D.", "prism:coverDate": f"{year}-01-01",
         "prism:publicationName": "Data Min Knowl Discov", "prism:doi": doi, "citedby-count": "3"}
    if eid:
        e["eid"] = eid
    return e


def pubmed_knows(records):
    """A fake PubMed that answers esearch by [AID] and efetch by id from
    `records` = {pmid: (doi, abstract, year)}; returns the list of esearch
    terms it was asked, to count lookups."""
    asked = []

    def esearch(url):
        term = urllib.parse.unquote(re.search(r"term=([^&]*)", url).group(1))
        asked.append(term)
        wanted = {d.lower() for d in re.findall(r'"([^"]+)"\[AID\]', term)}
        ids = [p for p, (doi, *_r) in records.items() if doi.lower() in wanted]
        return {"esearchresult": {"idlist": ids, "count": str(len(ids))}}, 200

    def efetch(url):
        ids = re.search(r"id=([^&]*)", url).group(1).split(",")
        return pm_xml(*[(p, *records[p]) for p in ids if p in records]), 200
    return asked, esearch, efetch


@pytest.fixture
def no_enrich(monkeypatch):
    monkeypatch.setattr(A, "enrich_access", lambda arts: arts)
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)


def route(monkeypatch, json_routes, get_routes=()):
    """Answer fetch_json / http_get by the first URL fragment that matches."""
    def pick(routes, url):
        for frag, answer in routes:
            if frag in url:
                return answer(url) if callable(answer) else answer
        raise AssertionError(f"unexpected request: {url}")
    monkeypatch.setattr(A, "fetch_json", lambda url, *a, **k: pick(json_routes, url))
    monkeypatch.setattr(A, "http_get", lambda url, *a, **k: pick(get_routes, url))


# ── Scopus records get their abstracts from PubMed ──────────────────────────

def test_scopus_records_get_pubmed_abstracts_in_one_lookup(monkeypatch, no_enrich):
    A.CONFIG["scopus_api_key"] = "k" * 32
    asked, esearch, efetch = pubmed_knows({"111": ("10.1/IN-PUBMED", "What we did.", "2024")})
    route(monkeypatch,
          [("api.elsevier.com", (scopus_page([scopus_entry("10.1/in-pubmed", "One"),
                                              scopus_entry("10.1/not-there", "Two"),
                                              scopus_entry(None, "Three")]), 200)),
           ("esearch.fcgi", esearch)],
          [("efetch.fcgi", efetch)])
    res, total = A.search_scopus("streamline warping", 10, None, None)
    one, two, three = res
    assert one["abstract"] == "What we did." and one["pmid"] == "111"
    assert one["abstract_from"] == "PubMed" and "abstract_note" not in one
    assert two["abstract"] == "" and "not in PubMed" in two["abstract_note"]
    assert three["abstract"] == "" and "no DOI" in three["abstract_note"]
    assert len(asked) == 1 and total == 3


def test_many_dois_go_to_pubmed_in_batches_not_one_by_one(monkeypatch):
    asked, esearch, efetch = pubmed_knows({})
    route(monkeypatch, [("esearch.fcgi", esearch)], [("efetch.fcgi", efetch)])
    arts = [article(doi=f"10.1/{i}", source="Scopus") for i in range(120)]
    A.fill_abstracts_from_pubmed(arts)
    assert len(asked) == 3                       # 50 + 50 + 20
    assert all("not in PubMed" in a["abstract_note"] for a in arts)


def test_a_pubmed_outage_is_marked_on_the_record_not_called_absence(monkeypatch, no_enrich):
    A.CONFIG["scopus_api_key"] = "k" * 32
    route(monkeypatch, [("api.elsevier.com", (scopus_page([scopus_entry("10.1/x")]), 200)),
                        ("esearch.fcgi", (None, 503))])
    res, _ = A.search_scopus("q", 10, None, None)     # Scopus results survive
    assert res[0]["abstract"] == ""
    assert "could not be asked" in res[0]["abstract_note"] and "503" in res[0]["abstract_note"]
    assert "not in PubMed" not in res[0]["abstract_note"]


def test_more_than_25_scopus_results_are_asked_for_in_pages_of_25(monkeypatch, no_enrich):
    A.CONFIG["scopus_api_key"] = "k" * 32
    counts = []

    def scopus(url):
        start = int(re.search(r"start=(\d+)", url).group(1))
        count = int(re.search(r"count=(\d+)", url).group(1))
        counts.append(count)
        return scopus_page([scopus_entry(f"10.1/{start + i}") for i in range(count)], total=500), 200
    route(monkeypatch, [("api.elsevier.com", scopus),
                        ("esearch.fcgi", ({"esearchresult": {"idlist": []}}, 200))])
    res, total = A.search_scopus("q", 60, None, None)
    assert counts == [25, 25, 10]
    assert [a["doi"] for a in res] == [f"10.1/{i}" for i in range(60)]
    assert total == 500


def test_a_doi_given_only_as_the_electronic_location_is_read(monkeypatch):
    xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>7</PMID><Article>
      <Journal><Title>J</Title><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal>
      <ArticleTitle>T</ArticleTitle><ELocationID EIdType="pii">S1</ELocationID>
      <ELocationID EIdType="doi">10.1/eloc</ELocationID></Article></MedlineCitation>
      </PubmedArticle></PubmedArticleSet>"""
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (xml, 200))
    assert A.pubmed_records(["7"])[0]["doi"] == "10.1/eloc"


def test_a_long_list_of_pmids_is_fetched_in_chunks(monkeypatch):
    urls = []
    monkeypatch.setattr(A, "http_get", lambda url, *a, **k: urls.append(url) or (pm_xml(), 200))
    A.pubmed_records([str(i) for i in range(250)])
    assert [u.count(",") + 1 for u in urls] == [200, 50]


# ── Cited by ────────────────────────────────────────────────────────────────

TRACTOME = "10.1007/s10618-015-0408-z"


def elink(*pmids):
    return {"linksets": [{"dbfrom": "pubmed", "ids": ["900"], "linksetdbs": [
        {"dbto": "pubmed", "linkname": "pubmed_pubmed_citedin", "links": list(pmids)}]}]}, 200


def test_cited_by_merges_pubmed_and_scopus_and_says_who_found_what(monkeypatch, no_enrich):
    A.CONFIG["scopus_api_key"] = "k" * 32
    asked, esearch, efetch = pubmed_knows({
        "900": (TRACTOME, "Tractome itself.", "2016"),
        "1": ("10.1/both", "Cites Tractome.", "2020"),
        "2": ("10.1/pubmed-only", "Also cites it.", "2023")})

    def scopus(url):
        q = urllib.parse.unquote(re.search(r"query=([^&]*)", url).group(1))
        if q.startswith("DOI("):
            return scopus_page([scopus_entry(TRACTOME, eid="2-s2.0-84")]), 200
        assert q == "REFEID(2-s2.0-84)"
        return scopus_page([scopus_entry("10.1/BOTH", "Cites", "2020"),
                            scopus_entry("10.1/scopus-only", "Only in Scopus", "2025")]), 200
    # PubMed can list a paper among its own citers; it is not one.
    route(monkeypatch, [("api.elsevier.com", scopus), ("elink.fcgi", elink("1", "2", "900")),
                        ("esearch.fcgi", esearch)],
          [("efetch.fcgi", efetch)])
    out = A.cited_by("https://doi.org/" + TRACTOME)
    assert out["doi"] == TRACTOME
    found = {a["doi"].lower(): a["found_in"] for a in out["articles"]}
    assert found == {"10.1/both": ["PubMed", "Scopus"], "10.1/pubmed-only": ["PubMed"],
                     "10.1/scopus-only": ["Scopus"]}
    assert [a["year"] for a in out["articles"]] == ["2025", "2023", "2020"]   # newest first
    assert out["sources"]["pubmed"]["status"] == "ok" and out["sources"]["pubmed"]["count"] == 2
    assert out["sources"]["scopus"]["count"] == 2


def test_cited_by_without_a_scopus_key_says_no_key_not_zero(monkeypatch, no_enrich):
    asked, esearch, efetch = pubmed_knows({"900": (TRACTOME, "", "2016")})
    route(monkeypatch, [("elink.fcgi", elink()), ("esearch.fcgi", esearch)])
    out = A.cited_by(TRACTOME)
    assert out["sources"]["scopus"]["status"] == "no key"
    assert out["sources"]["scopus"]["count"] is None
    assert "Scopus API key" in out["sources"]["scopus"]["error"]
    assert out["sources"]["pubmed"] == dict(out["sources"]["pubmed"], status="ok", count=0)


def test_a_paper_pubmed_does_not_have_is_reported_as_such(monkeypatch, no_enrich):
    asked, esearch, efetch = pubmed_knows({})
    route(monkeypatch, [("esearch.fcgi", esearch)])
    rep = A.cited_by(TRACTOME, sources=["pubmed"])["sources"]["pubmed"]
    assert rep["status"] == "not indexed" and rep["count"] is None
    assert "no record with this DOI" in rep["error"]


def test_a_failed_cited_in_lookup_is_a_failure_with_its_reason(monkeypatch, no_enrich):
    asked, esearch, efetch = pubmed_knows({"900": (TRACTOME, "", "2016")})
    route(monkeypatch, [("elink.fcgi", (None, 502)), ("esearch.fcgi", esearch)])
    rep = A.cited_by(TRACTOME, sources=["pubmed"])["sources"]["pubmed"]
    assert rep["status"] == "failed" and rep["count"] is None
    assert "cited-in" in rep["error"] and "502" in rep["error"]


def test_cited_by_refuses_an_unknown_source_by_name():
    with pytest.raises(ValueError, match="'wos'"):
        A.cited_by(TRACTOME, sources=["wos"])


# ── Merging ─────────────────────────────────────────────────────────────────

def test_the_same_paper_is_one_entry_by_doi_pmid_or_title():
    merged = A.merge_articles([
        ("PubMed", [article(title="Tractome", doi="10.1/T", pmid="9", abstract="abs"),
                    article(title="Only a PMID", pmid="5"),
                    article(title="Title only: streamline warping")]),
        ("Scopus", [article(title="TRACTOME.", doi="10.1/t", cited_by="40"),
                    article(title="Different wording", pmid="5", doi="10.1/p5"),
                    article(title="title only — streamline WARPING")])])
    assert [a["found_in"] for a in merged] == [["PubMed", "Scopus"]] * 3
    assert merged[0]["abstract"] == "abs" and merged[0]["cited_by"] == "40"
    assert merged[1]["doi"] == "10.1/p5"               # filled from the later source


def test_a_shared_title_with_different_dois_is_two_papers():
    merged = A.merge_articles([
        ("PubMed", [article(title="Erratum", doi="10.1/a")]),
        ("Scopus", [article(title="Erratum", doi="10.1/b")])])
    assert len(merged) == 2


def _fake_rows(monkeypatch, runners):
    rows = [(k, label, runners.get(k, f), strict) for k, label, f, strict in A.SOURCES]
    monkeypatch.setattr(A, "SOURCES", rows)
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)


def test_merged_search_reports_failures_and_missing_keys_never_as_zero(monkeypatch):
    A.CONFIG["scopus_api_key"] = "k" * 32
    sent = {}

    def pubmed(q, max_r, y_from, y_to, strict=True, sort="relevance", offset=0):
        sent["pubmed"] = q
        return [], 0

    def scopus(q, max_r, y_from, y_to, sort="relevance", offset=0):
        sent["scopus"] = q
        raise RuntimeError("Scopus quota exceeded (429).")

    def arxiv(q, max_r, y_from, y_to, sort="relevance", offset=0):      # no `strict`
        return [article(title="Streamline warping", source="arXiv")], 0
    _fake_rows(monkeypatch, {"pubmed": pubmed, "scopus": scopus, "arxiv": arxiv})
    out = A.merged_search("has anyone warped streamlines between subjects?",
                          sources=["pubmed", "scopus", "wos", "arxiv"],
                          keywords="streamline warping")
    s = out["sources"]
    assert s["pubmed"]["status"] == "ok" and s["pubmed"]["count"] == 0
    assert s["scopus"] == dict(s["scopus"], status="failed", count=None,
                               error="Scopus quota exceeded (429).")
    assert s["wos"]["status"] == "no key" and s["wos"]["count"] is None
    assert "Web of Science API key" in s["wos"]["error"]
    assert s["arxiv"]["count"] == 1
    # The long question went to Scopus only; the rest got the keywords.
    assert sent == {"pubmed": "streamline warping",
                    "scopus": "has anyone warped streamlines between subjects?"}
    assert s["arxiv"]["query"] == "streamline warping"
    assert [a["found_in"] for a in out["articles"]] == [["arXiv"]]


def test_merged_search_refuses_an_unknown_source_by_name():
    with pytest.raises(ValueError, match="'medline'"):
        A.merged_search("q", sources=["pubmed", "medline"])


def test_the_compact_form_has_one_line_per_paper_and_states_failures():
    result = {"articles": [dict(article(title="Tractome", year="2016", journal="Data Min Knowl Discov",
                                        doi="10.1007/s10618-015-0408-z",
                                        author_list=["Porro-Muñoz, Diego", "Olivetti, E"]),
                                found_in=["PubMed", "Scopus"])],
              "sources": {"pubmed": {"label": "PubMed", "status": "ok", "count": 1, "total": 1,
                                     "error": None, "query": "tractome"},
                          "wos": {"label": "Web of Science", "status": "no key", "count": None,
                                  "total": None, "error": "No Web of Science API key is set.",
                                  "query": None}}}
    lines = A.compact_report(result).splitlines()
    assert lines[0] == "PubMed: 1  [sent: tractome]"
    assert lines[1] == "Web of Science: NO KEY — No Web of Science API key is set."
    assert lines[-1] == ("2016 · Porro-Muñoz · Data Min Knowl Discov · Tractome · "
                         "doi:10.1007/s10618-015-0408-z · PubMed+Scopus")
    assert A._first_author({"authors": "Porro-Muñoz D."}) == "Porro-Muñoz"


# ── The citation window ─────────────────────────────────────────────────────

def test_the_citation_window_merges_all_three_and_reports_each(client, auth, monkeypatch):
    A.SESSION["articles"] = [article(title="Tractome", doi=TRACTOME)]
    monkeypatch.setattr(A, "get_citation_graph", lambda doi, cap, cit_cap: {
        "references": [], "citations": [], "ref_total": 0, "cit_total": 2,
        "cit_dois": ["10.1/BOTH", "10.1/oc-only"], "doi": doi})
    monkeypatch.setattr(A, "cited_by", lambda doi, enrich: {"doi": doi, "articles": [
        dict(article(title="Both", doi="10.1/both"), found_in=["PubMed"])],
        "sources": {"pubmed": {"label": "PubMed", "status": "ok", "count": 1, "total": 1,
                               "error": None, "query": ""},
                    "scopus": {"label": "Scopus", "status": "failed", "count": None, "total": None,
                               "error": "Scopus quota exceeded (429).", "query": ""}}})
    resolved = []
    monkeypatch.setattr(A, "_resolve_dois", lambda dois, limit: resolved.extend(dois) or
                        [{"doi": d, "title": "OC", "year": "2021", "authors": "", "journal": ""}
                         for d in dois])
    data = client.get("/citations/0", headers=auth, base_url=BASE).get_json()
    assert resolved == ["10.1/oc-only"]                  # the DOI PubMed had is not re-resolved
    assert [c["found_in"] for c in data["citations"]] == [["PubMed"], ["OpenCitations"]]
    assert data["cit_total"] == 2
    assert "cit_dois" not in data
    by_label = {r["label"]: r for r in data["cit_sources"]}
    assert by_label["Scopus"]["status"] == "failed" and "429" in by_label["Scopus"]["error"]
    assert by_label["OpenCitations"] == {"label": "OpenCitations", "status": "ok",
                                         "count": 1, "error": None}


def test_scopus_out_of_reach_is_said_as_such(monkeypatch):
    A.CONFIG["scopus_api_key"] = "k" * 32
    monkeypatch.setattr(A, "fetch_json", lambda *a, **k: (None, 0))
    with pytest.raises(RuntimeError, match="no connection to api.elsevier.com"):
        A.search_scopus("q", 5, None, None)


def test_a_scopus_refusal_says_what_scopus_said(monkeypatch):
    """Found live, 23 Sep 2026: the key may not use REFEID, and Scopus says so in the body.
    The message must carry that, not guess at the query's syntax."""
    import app
    body = {"service-error": {"status": {"statusCode": "INVALID_INPUT", "statusText":
            "Use of certain field restrictions in the search query is not allowed for this requestor."}}}
    monkeypatch.setitem(app.CONFIG, "scopus_api_key", "k" * 32)
    monkeypatch.setattr(app, "fetch_json", lambda *a, **k: (body, 400))
    import pytest
    with pytest.raises(RuntimeError, match="entitlement of the key"):
        app._scopus_get("REFEID(2-s2.0-1)", 0, 1)

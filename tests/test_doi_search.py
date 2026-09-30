"""Search by DOI: what the search box counts as DOIs, how each database is
asked for them, Crossref for the ones no database returned, and the stream
the page reads. Every outside service is faked."""
import subprocess
import sys
from pathlib import Path

import pytest

import app as A
from conftest import BASE, article, sse_events


# ── What counts as a DOI search ─────────────────────────────────────────────

@pytest.mark.parametrize("query, dois", [
    ("10.1056/NEJMoa2034577", ["10.1056/NEJMoa2034577"]),
    ("doi:10.1056/NEJMoa2034577", ["10.1056/NEJMoa2034577"]),
    ("DOI: 10.1056/NEJMoa2034577", ["10.1056/NEJMoa2034577"]),
    ("DOI 10.1056/NEJMoa2034577", ["10.1056/NEJMoa2034577"]),
    ("https://doi.org/10.1056/NEJMoa2034577", ["10.1056/NEJMoa2034577"]),
    ("doi.org/10.1056/NEJMoa2034577.", ["10.1056/NEJMoa2034577"]),
    ("http://dx.doi.org/10.1016/S0140-6736%2820%2930183-5", ["10.1016/S0140-6736(20)30183-5"]),
    ("(10.1016/S0140-6736(20)30183-5)", ["10.1016/S0140-6736(20)30183-5"]),
    ("https://www.nejm.org/doi/full/10.1056/NEJMoa2034577?query=featured_home",
     ["10.1056/NEJMoa2034577"]),
    ("https://link.springer.com/content/pdf/10.1007/s00701-020-04321-1.pdf",
     ["10.1007/s00701-020-04321-1"]),
    ("https://www.frontiersin.org/articles/10.3389/fonc.2020.00001/full", ["10.3389/fonc.2020.00001"]),
    ("https://www.medrxiv.org/content/10.1101/2020.12.01.20241234v2.full.pdf",
     ["10.1101/2020.12.01.20241234"]),
    ("https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0123456",
     ["10.1371/journal.pone.0123456"]),
    ("10.48550/arXiv.1706.03762", ["10.48550/arXiv.1706.03762"]),
])
def test_every_way_of_writing_a_doi_is_read(query, dois):
    assert A.dois_in_query(query) == dois


@pytest.mark.parametrize("query", [
    "glioma 10.1056/NEJMoa2034577",
    "https://www.sciencedirect.com/science/article/pii/S0140673620301835",
    "https://pubmed.ncbi.nlm.nih.gov/33301246/",
    "10.1056",
    "awake craniotomy",
    "",
])
def test_anything_else_in_the_box_makes_it_an_ordinary_search(query):
    assert A.dois_in_query(query) == []


def test_several_dois_are_all_read_each_once():
    q = "10.1056/NEJMoa2034577, 10.1016/S0140-6736(20)30183-5;\n10.1056/nejmoa2034577 10.1000/x"
    assert A.dois_in_query(q) == ["10.1056/NEJMoa2034577", "10.1016/S0140-6736(20)30183-5", "10.1000/x"]


def test_a_semicolon_inside_an_old_wiley_doi_does_not_split_it():
    sici = "10.1002/(SICI)1097-4636(199709)36:3<385::AID-JBM13>3.0.CO;2-8"
    assert A.dois_in_query(sici) == [sici]
    assert A.dois_in_query(f"{sici}; 10.1000/x") == [sici, "10.1000/x"]


# ── How each database is asked ──────────────────────────────────────────────

def _asked_fn(asked, results=()):
    def fn(query, max_r, y_from, y_to, **kw):
        asked.append((query, max_r, y_from, y_to))
        return [dict(a) for a in results], 0
    return fn


@pytest.mark.parametrize("key, term", [
    ("pubmed", '"10.1000/a"[AID] OR "10.1000/b"[AID]'),
    ("cochrane", '"10.1000/a"[AID] OR "10.1000/b"[AID]'),
    ("guidelines", '"10.1000/a"[AID] OR "10.1000/b"[AID]'),
    ("scopus", "DOI({10.1000/a}) OR DOI({10.1000/b})"),
    ("wos", 'DO=("10.1000/a" OR "10.1000/b")'),
])
def test_each_database_is_asked_by_its_own_doi_field_with_no_years(key, term):
    asked = []
    A.doi_lookup(key, _asked_fn(asked), ["10.1000/a", "10.1000/b"])
    assert [(q, y_from, y_to) for q, _n, y_from, y_to in asked] == [(term, None, None)]


def test_only_the_records_asked_for_are_kept_in_the_order_asked():
    # PubMed's DOI field also returns the other versions of a Cochrane review.
    got = [article(doi="10.1002/14651858.CD000031.pub2", title="v2"),
           article(doi="10.1000/B", title="b"),
           article(doi=None, title="no doi"),
           article(doi="10.1002/14651858.cd000031", title="v1")]
    arts, total = A.doi_lookup("pubmed", _asked_fn([], got), ["10.1002/14651858.CD000031", "10.1000/b"])
    assert [a["title"] for a in arts] == ["v1", "b"] and total == 2


def test_web_of_science_is_never_asked_for_more_than_a_page():
    asked = []
    A.doi_lookup("wos", _asked_fn(asked), [f"10.1000/{i}" for i in range(A.MAX_DOIS)])
    assert asked[0][1] == A.MAX_DOIS            # its Starter API refuses a larger limit


def test_clinicaltrials_cannot_be_searched_by_doi():
    with pytest.raises(A.SourceCannotAnswer, match="Can't be searched by DOI"):
        A.doi_lookup("clinicaltrials", _asked_fn([]), ["10.1000/a"])


def test_arxiv_looks_up_only_its_own_dois_by_their_arxiv_id(monkeypatch):
    with pytest.raises(A.SourceCannotAnswer, match="10.48550/arXiv"):
        A.doi_lookup("arxiv", None, ["10.1000/a"])
    feed = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <id>http://arxiv.org/abs/1706.03762v7</id><published>2017-06-12T00:00:00Z</published>
      <title>Attention Is All You Need</title><summary>Transformers.</summary>
      <author><name>Ashish Vaswani</name></author></entry></feed>"""
    urls = []
    monkeypatch.setattr(A, "http_get", lambda url, *a, **k: (urls.append(url), (feed, 200))[1])
    arts, _ = A.doi_lookup("arxiv", None, ["10.1000/a", "10.48550/arXiv.1706.03762"])
    assert "id_list=1706.03762" in urls[0] and "search_query" not in urls[0]
    assert [(a["doi"], a["title"]) for a in arts] == [("10.48550/arXiv.1706.03762",
                                                       "Attention Is All You Need")]


# ── Crossref, for the DOIs no database returned ─────────────────────────────

CROSSREF_WORK = {
    "DOI": "10.1007/978-3-030-58452-8_13", "type": "book-chapter",
    "title": ["End-to-End Object Detection with <i>Transformers</i>"],
    "container-title": ["Lecture Notes in Computer Science"],
    "published-print": {"date-parts": [[2020]]},
    "author": [{"family": "Carion", "given": "Nicolas"}, {"family": "Massa", "given": "Francisco"},
               {"family": "Synnaeve", "given": "Gabriel"}, {"name": "The DETR group"}],
    "abstract": "<jats:title>Abstract</jats:title><jats:sec><jats:title>Background</jats:title>"
                "<jats:p>CO<jats:sub>2</jats:sub> &amp; more.</jats:p></jats:sec>",
}


@pytest.fixture
def crossref(monkeypatch):
    """A fake Crossref: {doi: (message or None, status)}. No enrichment."""
    answers = {}
    monkeypatch.setattr(A, "enrich_access", lambda arts: arts)

    def fetch(url, *a, **k):
        if "esearch.fcgi" in url:                    # PubMed, for missing abstracts
            return {"esearchresult": {"idlist": []}}, 200
        doi = A.urllib.parse.unquote(url.split("/works/", 1)[1])
        msg, status = answers.get(doi, (None, 404))
        return ({"message": msg} if msg else None), status
    monkeypatch.setattr(A, "fetch_json", fetch)
    return answers


def test_a_crossref_record_reads_as_an_article(crossref):
    crossref["10.1000/x"] = (CROSSREF_WORK, 200)
    (a,), _ = A.crossref_records(["10.1000/x"])
    assert a["title"] == "End-to-End Object Detection with Transformers"
    assert a["authors"] == "Carion, N.; Massa, F.; Synnaeve, G. et al."
    assert a["author_list"][-1] == "The DETR group"
    assert (a["year"], a["journal"], a["source"]) == ("2020", "Lecture Notes in Computer Science",
                                                      "Crossref")
    assert a["abstract"] == "Background: CO2 & more."
    assert a["doi"] == "10.1007/978-3-030-58452-8_13" and a["pub_types"] == []


def test_a_crossref_preprint_is_marked_as_one(crossref):
    crossref["10.1101/x"] = ({"DOI": "10.1101/x", "type": "posted-content", "title": ["P"],
                              "institution": [{"name": "medRxiv"}]}, 200)
    (a,), _ = A.crossref_records(["10.1101/x"])
    assert a["pub_types"] == ["Preprint"] and a["journal"] == "medRxiv"


def test_a_doi_crossref_does_not_know_is_told_from_one_it_did_not_answer_for(crossref):
    crossref["10.1000/found"] = (CROSSREF_WORK, 200)
    crossref["10.1000/silent"] = (None, 0)
    report = {}
    arts, _ = A.crossref_records(["10.1000/found", "10.1000/unknown", "10.1000/silent"], report)
    assert len(arts) == 1
    assert report == {"unknown": ["10.1000/unknown"], "failed": ["10.1000/silent"]}


def test_crossref_answering_for_none_is_a_failure_not_an_absence(crossref):
    crossref["10.1000/a"] = (None, 0)
    with pytest.raises(RuntimeError, match="Crossref didn't respond"):
        A.crossref_records(["10.1000/a"])


# ── The search stream ───────────────────────────────────────────────────────

def _fake_sources(monkeypatch, results, asked):
    """Every source answers from `results` and records what it was asked."""
    def make(key):
        def run(query, max_r, y_from, y_to, **kw):
            asked.append((key, query, y_from, y_to))
            return [dict(a) for a in results.get(key, [])], 0
        return run
    monkeypatch.setattr(A, "SOURCES", [(k, l, make(k), s) for k, l, _f, s in A.SOURCES])
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)


def _fake_crossref(monkeypatch, known=(), unknown=(), failed=()):
    asked = []

    def records(dois, report=None):
        asked.append(list(dois))
        report["unknown"] = [d for d in dois if d in unknown]
        report["failed"] = [d for d in dois if d in failed]
        return [article(doi=d, title=f"From Crossref {d}", source="Crossref")
                for d in dois if d in known], 0
    monkeypatch.setattr(A, "crossref_records", records)
    return asked


def _search(client, auth, query, sources, **body):
    payload = {"query": query, "sources": sources, "max_results": 10, **body}
    return sse_events(client.post("/search_stream", json=payload, headers=auth, base_url=BASE))


def test_a_doi_search_asks_each_source_by_doi_and_ignores_the_years(client, auth, monkeypatch):
    asked = []
    _fake_sources(monkeypatch, {"pubmed": [article(doi="10.1000/a")]}, asked)
    monkeypatch.setattr(A, "get_mesh", lambda q: pytest.fail("MeSH asked about a DOI"))
    events = _search(client, auth, "https://doi.org/10.1000/a", ["pubmed", "cochrane"],
                     year_from=2023, year_to=2024)
    assert events[0] == {"type": "doi_lookup", "dois": ["10.1000/a"]}
    assert sorted(asked) == [("cochrane", '"10.1000/a"[AID]', None, None),
                             ("pubmed", '"10.1000/a"[AID]', None, None)]
    assert [e["article"]["doi"] for e in events if e["type"] == "article"] == ["10.1000/a"]


def test_an_ordinary_search_is_not_a_doi_lookup(client, auth, monkeypatch):
    asked = []
    _fake_sources(monkeypatch, {}, asked)
    monkeypatch.setattr(A, "get_mesh", lambda q: [])
    events = _search(client, auth, "glioma", ["pubmed"], year_from=2023)
    assert not any(e["type"] == "doi_lookup" for e in events)
    assert asked == [("pubmed", "glioma", 2023, None)]


def test_crossref_is_asked_only_for_the_dois_no_source_returned(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {"pubmed": [article(doi="10.1000/A")]}, [])
    cr = _fake_crossref(monkeypatch, known={"10.1000/b"})
    events = _search(client, auth, "10.1000/a 10.1000/b", ["pubmed"])
    assert cr == [["10.1000/b"]]
    starts = [e for e in events if e["type"] == "source_start"]
    assert [s["source"] for s in starts] == ["PubMed", "Crossref"]
    assert (starts[-1]["total"], starts[-1]["done"]) == (2, 1)
    arts = [(e["source"], e["article"]["doi"]) for e in events if e["type"] == "article"]
    assert arts == [("PubMed", "10.1000/A"), ("Crossref", "10.1000/b")]
    done = [e for e in events if e["type"] == "source_done"]
    assert (done[-1]["source"], done[-1]["done_sources"], done[-1]["total_sources"]) == ("Crossref", 2, 2)
    assert not any(e["type"] == "doi_missing" for e in events)


def test_crossref_is_not_asked_when_every_doi_was_found(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {"pubmed": [article(doi="10.1000/a")]}, [])
    cr = _fake_crossref(monkeypatch)
    events = _search(client, auth, "10.1000/a", ["pubmed"])
    assert cr == [] and not any(e.get("source") == "Crossref" for e in events)


def test_crossref_is_asked_even_when_no_ticked_source_can_search_by_doi(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {}, [])
    cr = _fake_crossref(monkeypatch, known={"10.1000/a"})
    events = _search(client, auth, "10.1000/a", ["clinicaltrials"])
    assert cr == [["10.1000/a"]]
    assert [e["article"]["doi"] for e in events if e["type"] == "article"] == ["10.1000/a"]


def test_crossref_is_asked_when_the_only_ticked_source_has_no_key(client, auth, monkeypatch):
    # Nothing is left to wait for, so Crossref is started before any waiting.
    _fake_sources(monkeypatch, {}, [])
    cr = _fake_crossref(monkeypatch, known={"10.1000/a"})
    events = _search(client, auth, "10.1000/a", ["scopus"])
    assert cr == [["10.1000/a"]]
    assert [e["article"]["doi"] for e in events if e["type"] == "article"] == ["10.1000/a"]


def test_a_source_that_cannot_search_by_doi_says_so_without_an_error(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {"pubmed": [article(doi="10.1000/a")]}, [])
    _fake_crossref(monkeypatch)
    events = _search(client, auth, "10.1000/a", ["pubmed", "clinicaltrials"])
    ct = next(e for e in events if e["type"] == "source_done" and e["source"] == "ClinicalTrials.gov")
    assert ct["note"] == "Can't be searched by DOI." and ct["count"] == 0
    assert not any(e["type"] == "source_error" for e in events)


def test_a_doi_nobody_knows_is_reported_and_one_crossref_missed_is_told_apart(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {}, [])
    _fake_crossref(monkeypatch, unknown={"10.1000/typo"}, failed={"10.1000/later"})
    events = _search(client, auth, "10.1000/typo 10.1000/later", ["pubmed"])
    missing = [e for e in events if e["type"] == "doi_missing"]
    assert len(missing) == 1 and missing[0]["count"] == 2
    text = missing[0]["text"]
    assert "Nothing was found for 10.1000/typo" in text and "check it for a typo" in text
    assert "Crossref did not answer for 10.1000/later" in text
    assert "10.1000/later in the databases" not in text        # never "no record" for an outage
    assert events[-1]["type"] == "done"


def test_crossref_down_is_a_source_error_and_not_a_missing_doi(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {}, [])

    def down(dois, report=None):
        raise RuntimeError("Crossref didn't respond. Check your connection and try again.")
    monkeypatch.setattr(A, "crossref_records", down)
    events = _search(client, auth, "10.1000/a", ["pubmed"])
    assert any(e["type"] == "source_error" and e["source"] == "Crossref" for e in events)
    assert not any(e["type"] == "doi_missing" for e in events)


def test_more_dois_than_one_lookup_takes_are_refused(client, auth, monkeypatch):
    _fake_sources(monkeypatch, {}, [])
    q = " ".join(f"10.1000/{i}" for i in range(A.MAX_DOIS + 1))
    events = _search(client, auth, q, ["pubmed"])
    assert events == [{"type": "error", "text": f"Look up at most {A.MAX_DOIS} DOIs at a time. "
                                                f"This search has {A.MAX_DOIS + 1}."}]


# ── The page ────────────────────────────────────────────────────────────────

def _webkit():
    if sys.platform != "darwin":
        return False
    try:
        import WebKit  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _webkit(), reason="needs macOS WebKit")
def test_a_doi_search_in_a_real_page():
    """The note, the Crossref group, no Find more, and the DOI-not-found
    dialog, in the real page (tests/webkit/doi_search_page.py), without a window."""
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, "-B", str(root / "tests" / "webkit" / "doi_search_page.py")],
                       capture_output=True, text=True, timeout=120, cwd=root)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert "ALL PASS" in r.stdout

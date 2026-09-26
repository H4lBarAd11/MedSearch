"""Pure logic: dedup, versions, PubMed query building, exports, parsers."""
import re
from pathlib import Path

import app as A
from conftest import article


# ── Deduplication ───────────────────────────────────────────────────────────

def test_dois_are_compared_case_insensitively():
    seen = set()
    A.register(seen, "10.1016/J.WNEU.2020.01.001", "One title")
    assert A.is_duplicate(seen, "10.1016/j.wneu.2020.01.001", "A different title")


def test_titles_match_ignoring_case_and_punctuation():
    seen = set()
    A.register(seen, None, "Awake craniotomy: a review.")
    assert A.is_duplicate(seen, None, "AWAKE CRANIOTOMY — A REVIEW")
    assert not A.is_duplicate(seen, None, "Asleep craniotomy: a review")


def test_an_empty_title_never_matches_another_empty_title():
    seen = set()
    A.register(seen, None, "")
    assert not A.is_duplicate(seen, None, "")


# ── Versions ────────────────────────────────────────────────────────────────

def test_a_release_sorts_above_every_beta():
    assert A._version_tuple("1.0") > A._version_tuple("Beta 99")
    assert A._version_tuple("1.3") > A._version_tuple("1.2.9")
    assert A._version_tuple("Beta 7") > A._version_tuple("Beta 6")


# ── PubMed query building ───────────────────────────────────────────────────

def test_strict_tags_every_word_title_abstract_and_ands_them():
    assert A.build_pubmed_term("glioma awake") == "glioma[tiab] AND awake[tiab]"


def test_broad_passes_the_words_through():
    assert A.build_pubmed_term("glioma awake", strict=False) == "glioma awake"


def test_a_power_query_is_never_rewritten():
    for q in ('glioma AND awake', '"awake craniotomy"', 'smith[au]'):
        assert A.build_pubmed_term(q) == q


# ── Publication types ───────────────────────────────────────────────────────

def test_badges_keep_only_informative_types_strongest_first():
    raw = ["Journal Article", "Review", "Meta-Analysis", "Research Support, N.I.H."]
    assert A._pub_type_badges(raw) == ["Meta-analysis", "Review"]


def test_guideline_types_collapse_to_one_badge():
    assert A._pub_type_badges(["Guideline", "Practice Guideline"]) == ["Guideline"]


# ── Exports ─────────────────────────────────────────────────────────────────

def _export(tmp_path, monkeypatch, articles, fmt):
    monkeypatch.setattr(A.Path, "home", staticmethod(lambda: tmp_path))
    paths = A.do_export(articles, "test query", fmt)
    return Path(paths[0]).read_text(encoding="utf-8")


def test_bibtex_separates_authors_with_and(tmp_path, monkeypatch):
    a = article(author_list=["Smith, John", "Doe, Anna", "Rossi, Mario"], year="2021")
    bib = _export(tmp_path, monkeypatch, [a], "bib")
    assert "author = {Smith, John and Doe, Anna and Rossi, Mario}" in bib
    assert ";" not in re.search(r"author = \{(.*)\}", bib).group(1)


def test_bibtex_escapes_what_would_break_the_file(tmp_path, monkeypatch):
    a = article(title="IL-6 {unbalanced & 50% of_cases", author_list=["Smith, J"])
    bib = _export(tmp_path, monkeypatch, [a], "bib")
    title = re.search(r"title = \{\{(.*)\}\}", bib).group(1)
    assert title == r"IL-6 \{unbalanced \& 50\% of\_cases"
    assert bib.count("{") - bib.count(r"\{") == bib.count("}") - bib.count(r"\}")


def test_bibtex_keys_are_unique(tmp_path, monkeypatch):
    same = [article(title=f"Paper {i}", author_list=["Smith, J"], year="2020") for i in range(3)]
    bib = _export(tmp_path, monkeypatch, same, "bib")
    keys = re.findall(r"@article\{([^,]+),", bib)
    assert len(keys) == 3 and len(set(keys)) == 3


def test_ris_has_one_au_line_per_author(tmp_path, monkeypatch):
    a = article(author_list=["Smith, John", "Doe, Anna"], doi="10.1/x", pmid="123")
    ris = _export(tmp_path, monkeypatch, [a], "ris")
    assert re.findall(r"^AU  - (.*)$", ris, re.M) == ["Smith, John", "Doe, Anna"]
    assert "DO  - 10.1/x" in ris and "AN  - 123" in ris
    assert ris.rstrip().endswith("ER  -")


def test_export_falls_back_to_the_display_authors_minus_et_al():
    a = article(authors="Smith, J.; Doe, A. et al.")
    assert A._author_names(a) == ["Smith, J.", "Doe, A."]


def test_a_retracted_paper_is_marked_in_every_format(tmp_path, monkeypatch):
    a = article(author_list=["Smith, J"], retraction="retracted")
    monkeypatch.setattr(A.Path, "home", staticmethod(lambda: tmp_path))
    for p in A.do_export([a], "q", "all"):
        assert "RETRACTED" in Path(p).read_text(encoding="utf-8")


# ── Parsers for outside services ────────────────────────────────────────────

def test_opencitations_v2_ids_yield_the_doi():
    assert A._doi_from_ids("omid:br/0615 doi:10.1093/nar/gkq1041 pmid:21062814") == "10.1093/nar/gkq1041"
    assert A._doi_from_ids("omid:br/0615 pmid:1") == ""


def test_retraction_is_read_from_crossref_updates(monkeypatch):
    body = {"message": {"items": [
        {"update-to": [{"DOI": "10.1016/s0140-6736(97)11096-0", "type": "correction"}]},
        {"update-to": [{"DOI": "10.1016/s0140-6736(97)11096-0", "type": "retraction"}]},
    ]}}
    monkeypatch.setattr(A, "fetch_json", lambda *a, **k: (body, 200))
    assert A.retraction_status("10.1016/S0140-6736(97)11096-0") == "retracted"


def test_an_expression_of_concern_is_not_a_retraction(monkeypatch):
    body = {"message": {"items": [{"update-to": [{"DOI": "10.1/x", "type": "expression_of_concern"}]}]}}
    monkeypatch.setattr(A, "fetch_json", lambda *a, **k: (body, 200))
    assert A.retraction_status("10.1/x") == "concern"


def test_updates_to_a_different_doi_are_ignored(monkeypatch):
    body = {"message": {"items": [{"update-to": [{"DOI": "10.1/other", "type": "retraction"}]}]}}
    monkeypatch.setattr(A, "fetch_json", lambda *a, **k: (body, 200))
    assert A.retraction_status("10.1/x") is None


def test_mesh_reads_espell_xml_and_esummary_json(monkeypatch):
    espell = ("<?xml version='1.0'?><eSpellResult><Query>glioblastma</Query>"
              "<CorrectedQuery>glioblastoma</CorrectedQuery></eSpellResult>")
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (espell, 200))

    def fake_json(url, *a, **k):
        if "esearch" in url:
            return {"esearchresult": {"idlist": ["68005909"]}}, 200
        return {"result": {"uids": ["68005909"],
                           "68005909": {"ds_meshterms": ["Glioblastoma", "Glioblastomas"]}}}, 200
    monkeypatch.setattr(A, "fetch_json", fake_json)
    assert A.get_mesh("glioblastma") == [{"type": "spelling", "text": "glioblastoma"},
                                         {"type": "mesh", "text": "Glioblastoma"}]


def test_arxiv_skips_a_malformed_entry_and_keeps_the_rest(monkeypatch):
    feed = """<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Good paper</title><published>2023-01-02</published>
             <id>http://arxiv.org/abs/2301.00001</id><summary>s</summary>
             <author><name>Ada Lovelace</name></author></entry>
      <entry><published>not-a-date</published></entry>
    </feed>"""
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (feed, 200))
    res, _ = A.search_arxiv("q", 10, None, None)
    assert [r["title"] for r in res][0] == "Good paper"
    assert res[0]["access_link"] == "http://arxiv.org/pdf/2301.00001"
    assert res[0]["pub_types"] == ["Preprint"]


def test_a_pubmed_record_marked_retracted_is_flagged(monkeypatch):
    esearch = {"esearchresult": {"idlist": ["1"], "count": "1"}}
    efetch = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
      <Journal><Title>Lancet</Title><JournalIssue><PubDate><Year>1998</Year></PubDate></JournalIssue></Journal>
      <ArticleTitle>Old paper</ArticleTitle>
      <AuthorList><Author><LastName>Wake</LastName><ForeName>Andrew</ForeName></Author></AuthorList>
      <PublicationTypeList><PublicationType>Journal Article</PublicationType>
        <PublicationType>Retracted Publication</PublicationType></PublicationTypeList>
      </Article></MedlineCitation>
      <PubmedData><ArticleIdList><ArticleId IdType="pmc">PMC1</ArticleId></ArticleIdList></PubmedData>
      </PubmedArticle></PubmedArticleSet>"""
    monkeypatch.setattr(A, "fetch_json", lambda *a, **k: (esearch, 200))
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (efetch, 200))
    res, total = A.search_pubmed("q", 10, None, None)
    assert res[0]["retraction"] == "retracted"
    assert res[0]["author_list"] == ["Wake, Andrew"]
    assert res[0]["access_link"].endswith("/PMC1/pdf/")


def test_pubmed_articles_skip_the_slow_crossref_retraction_call(monkeypatch):
    calls = []
    monkeypatch.setattr(A, "check_oa", lambda doi: None)
    monkeypatch.setattr(A, "pmcids_for_dois", lambda dois: {})
    monkeypatch.setattr(A, "retraction_status", lambda doi: calls.append(doi))
    A.enrich_access([article(doi="10.1/pm", pmid="1"), article(doi="10.1/sc", source="Scopus")])
    assert calls == ["10.1/sc"]


def test_enrichment_is_cached_per_doi(monkeypatch):
    calls = []
    monkeypatch.setattr(A, "check_oa", lambda doi: calls.append(doi) or "https://oa.example/x.pdf")
    monkeypatch.setattr(A, "retraction_status", lambda doi: None)
    for _ in range(2):
        a = A._article(doi="10.1/cached", source="Scopus")
        A.enrich_access([a])
        assert a["access_kind"] == "open"
    assert calls == ["10.1/cached"]


# ── Open access: what counts as a free copy ────────────────────────────────
# The payloads are Unpaywall's and OpenAlex's own answers of 26 Sep, trimmed.
# Both list Elsevier's graphical abstract as the article's PDF.

GARYFALLIDIS = "10.1016/j.neuroimage.2017.07.015"      # paywalled (bronze)
CLASSIFYBER = "10.1016/j.neuroimage.2020.117402"       # CC BY (gold)
ABSTRACT_JPG = "https://ars.els-cdn.com/content/image/1-s2.0-S1053811917305839-fx1_lrg.jpg"

UNPAYWALL = {
    GARYFALLIDIS: {"is_oa": True, "oa_status": "bronze", "oa_locations": [
        {"url": ABSTRACT_JPG, "url_for_pdf": ABSTRACT_JPG, "license": None,
         "url_for_landing_page": f"https://doi.org/{GARYFALLIDIS}",
         "host_type": "publisher", "version": "publishedVersion"}]},
    CLASSIFYBER: {"is_oa": True, "oa_status": "gold", "oa_locations": [
        {"url": ABSTRACT_JPG, "url_for_pdf": ABSTRACT_JPG, "license": "cc-by",
         "url_for_landing_page": f"https://doi.org/{CLASSIFYBER}",
         "host_type": "publisher", "version": "publishedVersion"},
        {"url": "https://doaj.org/article/8889caff0b464aa4aed1c5c495033f1b", "url_for_pdf": None,
         "url_for_landing_page": "https://doaj.org/article/8889caff0b464aa4aed1c5c495033f1b",
         "host_type": "repository", "version": "submittedVersion", "license": "cc-by"},
        {"url": "https://www.sciencedirect.com/science/article/pii/S1053811920308879",
         "url_for_pdf": None, "host_type": "repository", "version": "submittedVersion",
         "url_for_landing_page": "https://www.sciencedirect.com/science/article/pii/S1053811920308879",
         "license": None}]},
}

OPENALEX = {
    GARYFALLIDIS: {"open_access": {"is_oa": True, "oa_url": ABSTRACT_JPG}, "locations": [
        {"is_oa": True, "pdf_url": ABSTRACT_JPG, "license": None, "version": "publishedVersion",
         "landing_page_url": f"https://doi.org/{GARYFALLIDIS}", "source": {"type": "journal"}},
        {"is_oa": False, "pdf_url": None, "landing_page_url": "https://pubmed.ncbi.nlm.nih.gov/28712994",
         "source": {"type": "repository"}}]},
    CLASSIFYBER: {"open_access": {"is_oa": True, "oa_url": ABSTRACT_JPG}, "locations": [
        {"is_oa": True, "pdf_url": ABSTRACT_JPG, "license": "cc-by", "version": "publishedVersion",
         "landing_page_url": f"https://doi.org/{CLASSIFYBER}", "source": {"type": "journal"}},
        {"is_oa": True, "pdf_url": None, "version": "submittedVersion",
         "landing_page_url": "https://doaj.org/article/8889caff0b464aa4aed1c5c495033f1b",
         "source": {"type": "repository"}}]},
}


def _indexes(monkeypatch, email):
    monkeypatch.setitem(A.CONFIG, "unpaywall_email", email)
    asked = []

    def fetch_json(url, *a, **k):
        asked.append(url)
        for doi, body in (UNPAYWALL if "unpaywall" in url else OPENALEX).items():
            if doi in A.urllib.parse.unquote(url):
                return body, 200
        return None, 404
    monkeypatch.setattr(A, "fetch_json", fetch_json)
    return asked


def test_a_picture_is_never_the_free_copy():
    assert not A._is_full_text(ABSTRACT_JPG)
    assert not A._is_full_text("https://example.org/figure.PNG?size=large")
    assert A._is_full_text("https://hal.science/hal-01622403v1/file/paper.pdf")
    assert A._is_full_text("https://doi.org/10.1016/j.neuroimage.2017.07.015")


def test_an_article_called_open_only_for_its_graphical_abstract_is_not_open(monkeypatch):
    for email in ("you@example.com", ""):            # Unpaywall, then OpenAlex alone
        _indexes(monkeypatch, email)
        assert A.check_oa(GARYFALLIDIS) is None, email


def test_so_it_is_offered_through_the_library_instead(monkeypatch):
    _indexes(monkeypatch, "you@example.com")
    monkeypatch.setattr(A, "pmcids_for_dois", lambda dois: {})
    monkeypatch.setattr(A, "retraction_status", lambda doi: None)
    a = A._article(doi=GARYFALLIDIS, source="Scopus")
    A.enrich_access([a])
    assert (a["access_kind"], a["access_link"]) == ("doi", f"https://doi.org/{GARYFALLIDIS}")


def test_an_openly_licensed_article_opens_at_its_publisher_not_at_doaj(monkeypatch):
    for email in ("you@example.com", ""):
        _indexes(monkeypatch, email)
        assert A.check_oa(CLASSIFYBER) == f"https://doi.org/{CLASSIFYBER}", email


def test_a_doaj_record_is_still_used_when_it_is_all_there_is():
    record = "https://doaj.org/article/8889caff0b464aa4aed1c5c495033f1b"
    assert A._best_oa_url([{"url": record, "url_for_landing_page": record,
                            "host_type": "repository"}]) == record


def test_a_repository_pdf_still_beats_the_publisher():
    pmc = "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/pdf/"
    assert A._best_oa_url([
        {"url": "https://www.sciencedirect.com/x.pdf", "url_for_pdf": "https://www.sciencedirect.com/x.pdf",
         "host_type": "publisher", "version": "publishedVersion"},
        {"url": pmc, "url_for_pdf": pmc, "host_type": "repository"}]) == pmc


def test_openalex_is_asked_only_when_unpaywall_cannot_answer(monkeypatch):
    asked = _indexes(monkeypatch, "you@example.com")
    A.check_oa(GARYFALLIDIS)
    assert [u for u in asked if "openalex" in u] == []


def test_an_answer_cached_under_the_old_rules_is_looked_up_again(monkeypatch):
    calls = []
    monkeypatch.setattr(A, "check_oa", lambda doi: calls.append(doi) or None)
    monkeypatch.setattr(A, "pmcids_for_dois", lambda dois: {})
    monkeypatch.setattr(A, "retraction_status", lambda doi: None)
    A._DOI_CACHE[GARYFALLIDIS] = {"t": A.time.time(), "kind": "open",     # as 1.25 left it
                                  "link": ABSTRACT_JPG, "retraction": None}
    a = A._article(doi=GARYFALLIDIS, source="Scopus")
    A.enrich_access([a])
    assert calls == [GARYFALLIDIS]
    assert a["access_kind"] == "doi"


# ── Scopus: why a request was refused ───────────────────────────────────────

def test_scopus_says_the_key_is_wrong_when_elsevier_says_so(monkeypatch):
    import pytest
    monkeypatch.setitem(A.CONFIG, "scopus_api_key", "not-a-real-key")
    body = {"error-response": {"error-code": "APIKEY_INVALID",
                               "error-message": "The provided apiKey is invalid."}}
    monkeypatch.setattr(A, "fetch_json", lambda *a, **k: (body, 401))
    with pytest.raises(RuntimeError) as e:
        A.search_scopus("awake craniotomy", 5, None, None)
    assert "does not recognise this API key" in str(e.value)
    assert "campus" not in str(e.value)


def test_scopus_points_to_the_network_for_any_other_401(monkeypatch):
    import pytest
    monkeypatch.setitem(A.CONFIG, "scopus_api_key", "0" * 32)
    for body in ({"service-error": {"status": {"statusCode": "AUTHORIZATION_ERROR"}}}, None):
        monkeypatch.setattr(A, "fetch_json", lambda *a, _b=body, **k: (_b, 401))
        with pytest.raises(RuntimeError) as e:
            A.search_scopus("awake craniotomy", 5, None, None)
        assert "campus" in str(e.value)


def test_an_error_body_is_only_returned_when_asked_for(monkeypatch):
    import io, urllib.error
    def refuse(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"why":"x"}'))
    monkeypatch.setattr(A.urllib.request, "urlopen", refuse)
    monkeypatch.setattr(A, "_throttle", lambda url: None)
    assert A.http_get("https://api.example/x") == (None, 401)
    assert A.http_get("https://api.example/x", error_body=True) == ('{"why":"x"}', 401)
    assert A.fetch_json("https://api.example/x", error_body=True) == ({"why": "x"}, 401)

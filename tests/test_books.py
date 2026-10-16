"""Books: NCBI Bookshelf's books and chapters, which PubMed indexes as records
of their own; which PubMed-based database asks for them; and books exported
as books. Placeholder names only; nothing reaches the network."""
import json
import re
import urllib.parse
from pathlib import Path

import pytest

import app as A
from conftest import BASE, article, sse_events

CHAPTER = """<PubmedBookArticle><BookDocument><PMID Version="1">900001</PMID>
  <ArticleIdList><ArticleId IdType="bookaccession">NBK900001</ArticleId></ArticleIdList>
  <Book><Publisher><PublisherName>Example Publishing</PublisherName>
    <PublisherLocation>Example City</PublisherLocation></Publisher>
    <BookTitle book="example">Example Handbook</BookTitle>
    <PubDate><Year>2025</Year><Month>01</Month></PubDate>
    <AuthorList Type="editors"><Author><LastName>Moe</LastName><ForeName>Mary</ForeName></Author></AuthorList>
  </Book>
  <ArticleTitle book="example" part="a1">Low-Grade <i>Gliomas</i></ArticleTitle>
  <AuthorList Type="authors">
    <Author><LastName>Doe</LastName><ForeName>Jane</ForeName></Author>
    <Author><LastName>Roe</LastName><ForeName>Richard</ForeName></Author></AuthorList>
  <PublicationType UI="D016454">Review</PublicationType>
  <Abstract><AbstractText Label="INTRODUCTION">First part.</AbstractText>
    <AbstractText>Second part.</AbstractText></Abstract>
  <ReferenceList><Reference><Citation>A cited paper.</Citation>
    <ArticleIdList><ArticleId IdType="doi">10.9/a-reference</ArticleId></ArticleIdList></Reference></ReferenceList>
</BookDocument></PubmedBookArticle>"""

WHOLE_BOOK = """<PubmedBookArticle><BookDocument><PMID Version="1">900002</PMID>
  <ArticleIdList><ArticleId IdType="bookaccession">NBK900002</ArticleId></ArticleIdList>
  <Book><Publisher><PublisherName>Example Institute</PublisherName></Publisher>
    <BookTitle book="ex2">Back pain in adults: an example guideline</BookTitle>
    <PubDate><Year>2024</Year></PubDate>
    <AuthorList Type="authors"><Author><LastName>Doe</LastName><ForeName>Jane</ForeName></Author></AuthorList>
    <ELocationID EIdType="doi">10.9/report</ELocationID>
    <Isbn>978-1-4731-9490-x</Isbn>
  </Book>
  <PublicationType UI="D017065">Practice Guideline</PublicationType>
</BookDocument></PubmedBookArticle>"""

PAPER = """<PubmedArticle><MedlineCitation><PMID>900003</PMID><Article>
  <Journal><Title>Example Journal</Title><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal>
  <ArticleTitle>A paper</ArticleTitle>
  <AuthorList><Author><LastName>Doe</LastName><ForeName>Jane</ForeName></Author></AuthorList>
  </Article></MedlineCitation></PubmedArticle>"""


class Terms(list):
    """The esearch terms asked, with what the fake answers."""


def efetch(*records):
    return f"<PubmedArticleSet>{''.join(records)}</PubmedArticleSet>"


@pytest.fixture
def pubmed(monkeypatch):
    """A fake PubMed: esearch answers `ids[0]`, efetch `body[0]`; the esearch
    terms asked are recorded."""
    terms, ids, body = Terms(), [[]], [efetch()]

    def esearch(url, *a, **k):
        terms.append(dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))["term"])
        return {"esearchresult": {"idlist": ids[0], "count": str(len(ids[0]))}}, 200
    monkeypatch.setattr(A, "fetch_json", esearch)
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (body[0], 200))
    monkeypatch.setattr(A, "enrich_access", lambda arts: arts)
    terms.ids, terms.body = ids, body
    return terms


def records(*recs, ids=None):
    body = efetch(*recs)
    found = re.findall(r"<PMID[^>]*>(\d+)</PMID>", body)
    return A.pubmed_records(ids or found)


# ── Reading a Bookshelf record ──────────────────────────────────────────────

def test_a_bookshelf_chapter_is_read_as_a_chapter_of_its_book(monkeypatch):
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (efetch(CHAPTER), 200))
    [a] = records(CHAPTER)
    assert a["title"] == "Low-Grade Gliomas"
    assert a["journal"] == "Example Handbook"          # where a paper shows its journal
    assert (a["year"], a["pmid"], a["source"]) == ("2025", "900001", "PubMed")
    assert a["author_list"] == ["Doe, Jane", "Roe, Richard"]
    assert a["authors"] == "Doe, J.; Roe, R."
    assert a["abstract"] == "INTRODUCTION: First part. Second part."
    assert a["pub_types"] == ["Book", "Review"]
    # Bookshelf's own copy is free to read.
    assert (a["access_kind"], a["access_link"]) == ("open", "https://www.ncbi.nlm.nih.gov/books/NBK900001/")
    assert a["book"] == {"kind": "chapter", "title": "Example Handbook",
                         "publisher": "Example Publishing", "place": "Example City",
                         "isbn": [], "editors": ["Moe, Mary"], "bookshelf": "NBK900001"}
    # A DOI in the chapter's references is not the chapter's own.
    assert a["doi"] is None and a["scihub"] is None


def test_a_bookshelf_record_without_a_chapter_title_is_a_whole_book(monkeypatch):
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (efetch(WHOLE_BOOK), 200))
    [a] = records(WHOLE_BOOK)
    assert a["title"] == "Back pain in adults: an example guideline"
    assert a["journal"] == "Example Institute"         # a whole book shows its publisher
    assert a["book"]["kind"] == "book"
    assert a["author_list"] == ["Doe, Jane"] and a["book"]["editors"] == []
    assert a["book"]["isbn"] == ["978147319490X"]
    assert a["doi"] == "10.9/report"
    assert a["pub_types"] == ["Book", "Guideline"]


def test_books_and_papers_in_one_answer_keep_the_order_asked(monkeypatch):
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (efetch(PAPER, CHAPTER, WHOLE_BOOK), 200))
    arts = A.pubmed_records(["900002", "900003", "900001"])
    assert [a["pmid"] for a in arts] == ["900002", "900003", "900001"]
    paper = arts[1]
    assert paper["book"] is None and paper["journal"] == "Example Journal"
    assert "Book" not in paper["pub_types"]


def test_the_years_asked_for_apply_to_books_too(monkeypatch):
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (efetch(CHAPTER, WHOLE_BOOK), 200))
    arts = A.pubmed_records(["900001", "900002"], y_from=2025, y_to=2026)
    assert [a["pmid"] for a in arts] == ["900001"]


def test_a_book_record_with_no_book_in_it_is_skipped(monkeypatch):
    empty = "<PubmedBookArticle><BookDocument><PMID>900009</PMID></BookDocument></PubmedBookArticle>"
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (efetch(empty, PAPER), 200))
    assert [a["pmid"] for a in A.pubmed_records(["900009", "900003"])] == ["900003"]


# ── Which database asks PubMed for the books ────────────────────────────────

def test_pubmed_leaves_the_books_to_bookshelf(pubmed):
    A.search_pubmed("glioma", 10, None, None)
    assert pubmed[-1] == f"(glioma[tiab]) NOT {A.PUBMED_BOOKS}"


def test_bookshelf_asks_pubmed_for_the_books_only(pubmed):
    pubmed.ids[0], pubmed.body[0] = ["900001"], efetch(CHAPTER)
    arts, total = A.search_bookshelf("glioma", 10, None, None,
                                     people=A.people_filter("Jane Doe"))
    assert pubmed[-1] == f"((glioma[tiab]) AND {A.PUBMED_BOOKS}) AND Doe J[au]"
    assert [a["source"] for a in arts] == ["NCBI Bookshelf"] and total == 1


def test_guidelines_and_cochrane_ask_for_books_and_papers_alike(pubmed):
    A.search_guidelines("back pain", 10, None, None)
    A.search_cochrane("back pain", 10, None, None)
    assert "pubmed books" not in pubmed[0] + pubmed[1]


def test_the_subset_of_books_leaves_out_the_journals_bookshelf_hosts():
    # Bookshelf hosts some journals, filed by PubMed in the same subset;
    # those papers are in MEDLINE.
    assert A.PUBMED_BOOKS == '("pubmed books"[sb] NOT medline[sb])'


def test_a_doi_search_asks_bookshelf_by_its_doi_field(pubmed):
    pubmed.ids[0], pubmed.body[0] = ["900002"], efetch(WHOLE_BOOK)
    arts, n = A.doi_lookup("bookshelf", A.search_bookshelf, ["10.9/report"])
    assert pubmed[-1] == f'("10.9/report"[AID]) AND {A.PUBMED_BOOKS}'
    assert [a["pmid"] for a in arts] == ["900002"] and n == 1


# ── Bookshelf as a database ─────────────────────────────────────────────────

def test_bookshelf_is_a_database_released_with_the_pubmed_family():
    keys = [k for k, *_ in A.SOURCES]
    assert "bookshelf" in keys and "bookshelf" in A._PRIORITY_SOURCES
    # Guidelines comes first, so a guideline both find is shown under Guidelines.
    assert keys.index("guidelines") < keys.index("bookshelf")
    assert dict((k, (label, fn)) for k, label, fn, _s in A.SOURCES)["bookshelf"] == \
        ("NCBI Bookshelf", A.search_bookshelf)


def test_the_bookshelf_tick_is_drawn_and_remembered(client, auth):
    r = client.post("/sources", json={"sources": ["pubmed", "bookshelf"]}, headers=auth, base_url=BASE)
    assert r.get_json()["sources"] == ["pubmed", "bookshelf"]
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert re.search(r'<div class="db-item checked" data-db="bookshelf">\s*<div class="db-check"></div>\s*'
                     r'<span class="db-name">NCBI Bookshelf</span>', page)


def test_a_guideline_found_by_guidelines_and_bookshelf_shows_once_under_guidelines(
        client, auth, monkeypatch):
    nice = article(title="Back pain in adults", pmid="900002", pub_types=["Book", "Guideline"])

    def make(key):
        def run(query, max_r, y_from, y_to, **kw):
            if key == "bookshelf":
                return [dict(nice, source="NCBI Bookshelf")], 1
            if key == "guidelines":
                return [dict(nice, source="Guidelines")], 1
            return [], 0
        return run
    monkeypatch.setattr(A, "SOURCES", [(k, l, make(k), s) for k, l, _f, s in A.SOURCES])
    monkeypatch.setattr(A, "get_mesh", lambda q: [])
    monkeypatch.setattr(A, "save_doi_cache", lambda: None)
    events = sse_events(client.post("/search_stream", json={
        "query": "back pain", "sources": ["bookshelf", "guidelines"], "max_results": 10},
        headers=auth, base_url=BASE))
    assert [e["article"]["source"] for e in events if e["type"] == "article"] == ["Guidelines"]


# ── Books exported as books ─────────────────────────────────────────────────

def _book_results(monkeypatch):
    monkeypatch.setattr(A, "http_get", lambda *a, **k: (efetch(CHAPTER, WHOLE_BOOK, PAPER), 200))
    return A.pubmed_records(["900001", "900002", "900003"])


def _export(tmp_path, monkeypatch, articles, fmt):
    monkeypatch.setattr(A.Path, "home", staticmethod(lambda: tmp_path))
    return Path(A.do_export(articles, "q", fmt)[0]).read_text(encoding="utf-8")


def _bib_entries(bib):
    return {m.group(1): m.group(2) for m in re.finditer(r"@(\w+)\{[^,]+,\n(.*?)\n\}", bib, re.S)}


def test_bibtex_writes_a_chapter_as_incollection_and_a_book_as_book(tmp_path, monkeypatch):
    bib = _export(tmp_path, monkeypatch, _book_results(monkeypatch), "bib")
    entries = _bib_entries(bib)
    assert set(entries) == {"incollection", "book", "article"}
    chapter, book, paper = entries["incollection"], entries["book"], entries["article"]
    assert "booktitle = {{Example Handbook}}" in chapter and "editor = {Moe, Mary}" in chapter
    assert "publisher = {Example Publishing}" in chapter and "address = {Example City}" in chapter
    assert "url = {https://www.ncbi.nlm.nih.gov/books/NBK900001/}" in chapter
    assert "journal" not in chapter + book
    assert "publisher = {Example Institute}" in book and "isbn = {978147319490X}" in book
    assert "booktitle" not in book and "doi = {10.9/report}" in book
    assert "journal = {Example Journal}" in paper and "publisher" not in paper


def test_ris_writes_a_chapter_as_chap_and_a_book_as_book(tmp_path, monkeypatch):
    ris = _export(tmp_path, monkeypatch, _book_results(monkeypatch), "ris")
    chapter, book, paper = [r for r in ris.split("ER  -") if r.strip()]
    assert chapter.split("\n")[0] == "TY  - CHAP"
    for line in ("T2  - Example Handbook", "A2  - Moe, Mary", "PB  - Example Publishing",
                 "CY  - Example City"):
        assert line in chapter.split("\n")
    lines = book.strip().split("\n")
    assert lines[0] == "TY  - BOOK" and "SN  - 978147319490X" in lines
    assert "PB  - Example Institute" in lines and not any(l.startswith("T2") for l in lines)
    assert paper.strip().split("\n")[0] == "TY  - JOUR" and "T2  - Example Journal" in paper


def test_markdown_names_the_book_its_editors_and_bookshelf(tmp_path, monkeypatch):
    md = _export(tmp_path, monkeypatch, _book_results(monkeypatch)[:1], "md")
    for line in ("**In:** Example Handbook", "**Editors:** Moe, Mary",
                 "**Publisher:** Example Publishing", "**Type:** Book, Review",
                 "**NCBI Bookshelf:** https://www.ncbi.nlm.nih.gov/books/NBK900001/"):
        assert line in md


def test_zotero_gets_a_book_section_and_a_book(monkeypatch):
    chapter, book, paper = (A.article_to_zotero_item(a) for a in _book_results(monkeypatch))
    assert chapter["itemType"] == "bookSection" and chapter["bookTitle"] == "Example Handbook"
    assert {"creatorType": "editor", "firstName": "Mary", "lastName": "Moe"} in chapter["creators"]
    assert (chapter["publisher"], chapter["place"]) == ("Example Publishing", "Example City")
    assert chapter["url"] == "https://www.ncbi.nlm.nih.gov/books/NBK900001/"
    assert "publicationTitle" not in chapter
    assert book["itemType"] == "book" and book["ISBN"] == "978147319490X"
    # Zotero keeps a DOI field on articles only: a book's goes in Extra.
    assert "DOI" not in book and book["extra"] == "DOI: 10.9/report\nPMID: 900002"
    assert paper["itemType"] == "journalArticle" and paper["publicationTitle"] == "Example Journal"
    assert paper["extra"] == "PMID: 900003"

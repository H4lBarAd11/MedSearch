"""Books: NCBI Bookshelf's books and chapters, which PubMed indexes as records
of their own; which PubMed-based database asks for them; Open Library's books,
read free, borrowed or found in a library; and books exported as books.
Placeholder names only; nothing reaches the network."""
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


# ── Open Library ────────────────────────────────────────────────────────────

def work(**kw):
    """An Open Library search answer's work, with placeholder values."""
    return {"key": "/works/OL1W", "title": "Example Handbook", "author_name": ["Jane A. Doe"],
            "first_publish_year": 1990, **kw}


@pytest.fixture
def openlibrary(monkeypatch):
    """A fake Open Library answering `docs[0]`; records the URLs and headers asked."""
    asked, docs = Terms(), [[]]

    def get(url, headers=None, **k):
        asked.append((url, headers))
        return {"numFound": 42, "docs": docs[0]}, 200
    monkeypatch.setattr(A, "fetch_json", get)
    asked.docs = docs
    return asked


@pytest.fixture
def ol(openlibrary):
    return openlibrary


def ol_params(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


def test_an_open_library_work_is_read_as_a_book():
    a = A._openlibrary_article(work(title="Example Handbook", subtitle=" a  guide ",
                                    author_name=["Jane A. Doe", "Richard Roe", "Mary Moe", "Ann Poe"]))
    assert a["title"] == "Example Handbook: a guide"
    assert a["author_list"] == ["Doe, Jane A.", "Roe, Richard", "Moe, Mary", "Poe, Ann"]
    assert a["authors"] == "Doe, J.; Roe, R.; Moe, M. et al."
    assert (a["year"], a["source"], a["pub_types"]) == ("1990", "Open Library", ["Book"])
    assert a["book"]["kind"] == "book" and a["book"]["openlibrary"] == "https://openlibrary.org/works/OL1W"
    assert a["doi"] is None and a["scihub"] is None


def test_an_isbn_and_a_publisher_are_kept_only_when_the_work_has_one_edition():
    one = A._openlibrary_article(work(isbn=["0306406152", "9780306406157"], publisher=["Example Press"]))
    assert one["book"]["isbn"] == ["9780306406157"]           # the same book, 10 and 13 digits
    assert one["journal"] == one["book"]["publisher"] == "Example Press"
    many = A._openlibrary_article(work(isbn=["9780306406157", "9780962638459"],
                                       publisher=["Example Press", "Other Press"]))
    assert many["book"]["isbn"] == [] and many["journal"] == many["book"]["publisher"] == ""


@pytest.mark.parametrize("isbn, thirteen", [
    ("0-306-40615-2", "9780306406157"), ("978-0-306-40615-7", "9780306406157"),
    ("080442957X", "9780804429573"), ("12345", None), ("", None)])
def test_an_isbn_10_becomes_its_isbn_13(isbn, thirteen):
    assert A._isbn13(isbn) == thirteen


def test_a_public_domain_book_is_read_free_in_the_internet_archives_reader():
    a = A._openlibrary_article(work(ebook_access="public", ia=["first_scan", "lent_scan"],
                                    lending_identifier_s="lent_scan"))
    assert (a["access_kind"], a["access_link"]) == ("open", "https://archive.org/details/lent_scan")
    assert a["book"]["borrow"] is None
    plain = A._openlibrary_article(work(ebook_access="public", ia=["first_scan"]))
    assert plain["access_link"] == "https://archive.org/details/first_scan"


def test_a_lent_book_is_borrowed_at_its_editions_page():
    a = A._openlibrary_article(work(ebook_access="borrowable", lending_edition_s="OL2M",
                                    lending_identifier_s="lent_scan"))
    assert a["book"]["borrow"] == "https://openlibrary.org/books/OL2M"
    assert (a["access_kind"], a["access_link"]) == ("none", None)
    no_edition = A._openlibrary_article(work(ebook_access="borrowable"))
    assert no_edition["book"]["borrow"] == "https://openlibrary.org/works/OL1W"


@pytest.mark.parametrize("access", ["printdisabled", "no_ebook", None])
def test_a_book_lent_only_to_print_disabled_readers_or_not_at_all_has_no_borrow(access):
    a = A._openlibrary_article(work(ebook_access=access, ia=["scan"], lending_edition_s="OL2M"))
    assert a["book"]["borrow"] is None and a["access_kind"] == "none"


def test_open_library_is_asked_with_years_order_page_and_author(ol):
    ol.docs[0] = [work(author_name=["Jane A. Doe"], first_publish_year=2005),
                  work(key="/works/OL2W", author_name=["John Roe"], first_publish_year=2005),
                  work(key="/works/OL3W", author_name=["Jane A. Doe"], first_publish_year=1990)]
    arts, total = A.search_openlibrary("glioma", 10, 2000, None, sort="date", offset=20,
                                       people=A.people_filter("Jane Doe"))
    url, headers = ol[0]
    assert url.startswith("https://openlibrary.org/search.json?")
    p = ol_params(url)
    assert p["q"] == "(glioma) AND first_publish_year:[2000 TO *]"
    assert (p["author"], p["sort"], p["offset"], p["limit"]) == ("Jane Doe", "new", "20", "10")
    assert set(p["fields"].split(",")) >= {"ebook_access", "lending_edition_s", "lending_identifier_s", "isbn"}
    # Open Library ranks by the name; a book by someone else is left out, and
    # so is one outside the years.
    assert [a["book"]["openlibrary"] for a in arts] == ["https://openlibrary.org/works/OL1W"]
    assert total == 42


def test_an_author_alone_asks_open_library_without_words(ol):
    A.search_openlibrary("", 10, None, None, people=A.people_filter("Jane Doe"))
    p = ol_params(ol[0][0])
    assert "q" not in p and p["author"] == "Jane Doe" and "sort" not in p


def test_open_library_is_told_who_asks_when_a_contact_is_set(ol):
    A.search_openlibrary("glioma", 10, None, None)
    A.CONFIG["unpaywall_email"] = "reader@example.org"
    A.search_openlibrary("glioma", 10, None, None)
    assert [h["User-Agent"] for _u, h in ol] == ["MedSearch/1.0", "MedSearch/1.0 (reader@example.org)"]


def test_open_library_calls_are_spaced_as_it_asks(monkeypatch):
    rates = []
    monkeypatch.setattr(A._OPENLIBRARY_LIMITER, "wait", rates.append)
    A._throttle("https://openlibrary.org/search.json?q=x")
    A.CONFIG["unpaywall_email"] = "reader@example.org"
    A._throttle("https://openlibrary.org/search.json?q=x")
    A._throttle("https://archive.org/details/x")
    assert rates == [0.9, 2.8]


def test_open_library_cannot_be_narrowed_to_an_institution_or_asked_by_doi(ol):
    with pytest.raises(A.SourceCannotAnswer, match="institution"):
        A.search_openlibrary("glioma", 10, None, None, people=A.people_filter(None, "Example Hospital"))
    with pytest.raises(A.SourceCannotAnswer):
        A.doi_lookup("openlibrary", A.search_openlibrary, ["10.9/x"])
    assert ol == []


def test_open_library_failing_says_so(monkeypatch):
    monkeypatch.setattr(A, "fetch_json", lambda *a, **k: (None, 0))
    with pytest.raises(RuntimeError, match="didn't respond"):
        A.search_openlibrary("glioma", 10, None, None)
    monkeypatch.setattr(A, "fetch_json", lambda *a, **k: (None, 503))
    with pytest.raises(RuntimeError, match="HTTP 503"):
        A.search_openlibrary("glioma", 10, None, None)


def test_open_library_is_a_database_after_bookshelf():
    keys = [k for k, *_ in A.SOURCES]
    assert keys.index("openlibrary") == keys.index("bookshelf") + 1
    assert "openlibrary" not in A._PRIORITY_SOURCES


def test_an_open_library_book_is_exported_with_its_page_and_its_one_isbn(tmp_path, monkeypatch):
    a = A._openlibrary_article(work(isbn=["9780306406157"], publisher=["Example Press"]))
    bib = _export(tmp_path, monkeypatch, [a], "bib")
    assert bib.startswith("@book{") and "isbn = {9780306406157}" in bib
    assert "url = {https://openlibrary.org/works/OL1W}" in bib and "publisher = {Example Press}" in bib
    md = _export(tmp_path, monkeypatch, [a], "md")
    assert "**Open Library:** https://openlibrary.org/works/OL1W" in md
    item = A.article_to_zotero_item(a)
    assert (item["itemType"], item["url"], item["ISBN"]) == (
        "book", "https://openlibrary.org/works/OL1W", "9780306406157")


# ── Books with one title are not one book ───────────────────────────────────

def book(title, first_author, year, **kw):
    return article(title=title, author_list=[first_author], year=year, pub_types=["Book"],
                   book={"kind": "book", "isbn": [], "openlibrary": None}, source="Open Library", **kw)


def shown(arts):
    seen, out = set(), []
    for a in arts:
        if not A.is_duplicate(seen, a):
            out.append(a)
        A.register(seen, a)
    return [(a["title"], a["author_list"][0], a["year"]) for a in out]


def test_books_sharing_a_short_title_are_all_shown_but_one_book_twice_is_not():
    arts = [book("Glioma", "Doe, Jane", "2012"), book("Glioma", "Roe, Richard", "1991"),
            book("Glioma", "Doe, J.", "2012"),               # the same book, listed again
            book("Glioma", "Doe, Jane", "2016")]             # its next edition
    assert shown(arts) == [("Glioma", "Doe, Jane", "2012"), ("Glioma", "Roe, Richard", "1991"),
                           ("Glioma", "Doe, Jane", "2016")]


def test_a_paper_and_a_book_with_one_title_are_two():
    assert len(shown([article(title="Glioma", author_list=["Doe, Jane"], year="2012"),
                      book("Glioma", "Doe, Jane", "2012")])) == 2


def test_papers_still_meet_by_their_whole_title():
    assert len(shown([article(title="A trial of something", author_list=["Doe, Jane"], year="2012"),
                      article(title="A trial of something", author_list=["Roe, R"], year="2013")])) == 1


def test_the_merged_list_tells_books_apart_the_same_way():
    merged = A.merge_articles([("Open Library", [book("Glioma", "Doe, Jane", "2012"),
                                                 book("Glioma", "Roe, Richard", "1991")]),
                               ("Other", [book("Glioma", "Doe, J.", "2012")])])
    assert [(m["author_list"][0], m["found_in"]) for m in merged] == [
        ("Doe, Jane", ["Open Library", "Other"]), ("Roe, Richard", ["Open Library"])]


# ── The books OpenAlex and Crossref return ──────────────────────────────────

def oa_work(type_, locations=(), **kw):
    return {"id": "https://openalex.org/W1", "display_name": "Example Handbook", "type": type_,
            "publication_year": 2016, "doi": "https://doi.org/10.9/book",
            "authorships": [{"author": {"display_name": "Jane Doe"}}],
            "primary_location": {"source": {"display_name": "Example eBooks",
                                            "host_organization_name": "Example Publishing"}},
            "locations": list(locations), **kw}


LANDING_ONLY = {"is_oa": True, "license": "cc-by-nc-nd", "pdf_url": None, "version": "publishedVersion",
                "landing_page_url": "https://doi.org/10.9/another-book", "source": {"type": "ebook platform"}}
WITH_PDF = {"is_oa": True, "license": "cc-by", "pdf_url": "https://repository.example.edu/book.pdf",
            "landing_page_url": "https://repository.example.edu/book", "source": {"type": "repository"}}


def test_an_openalex_book_is_a_book_with_its_publisher():
    a = A._openalex_article(oa_work("book"))
    assert a["pub_types"] == ["Book"] and a["journal"] == "Example eBooks"
    assert a["book"] == {"kind": "book", "title": "Example Handbook", "publisher": "Example Publishing",
                         "place": "", "isbn": [], "editors": [], "bookshelf": None}


def test_an_openalex_chapter_does_not_know_its_book():
    a = A._openalex_article(oa_work("book-chapter"))
    assert (a["book"]["kind"], a["book"]["title"]) == ("chapter", "")


def test_a_book_is_free_only_with_a_link_to_a_pdf_of_it():
    # OpenAlex calls paid books open on the strength of a landing page.
    assert A._openalex_article(oa_work("book", [LANDING_ONLY]))["access_kind"] is None
    a = A._openalex_article(oa_work("book", [LANDING_ONLY, WITH_PDF]))
    assert (a["access_kind"], a["access_link"]) == ("open", "https://repository.example.edu/book.pdf")
    # A paper's openly licensed landing page still counts.
    paper = A._openalex_article(oa_work("article", [LANDING_ONLY]))
    assert paper["book"] is None and paper["pub_types"] == []
    assert (paper["access_kind"], paper["access_link"]) == ("open", "https://doi.org/10.9/another-book")


def test_unpaywall_and_the_openalex_fallback_ask_a_book_for_a_pdf_too(monkeypatch):
    A.CONFIG["unpaywall_email"] = "reader@example.org"
    unpaywall = {"is_oa": True, "oa_locations": [
        {"url": "https://doi.org/10.9/another-book", "url_for_pdf": None, "license": "cc-by",
         "url_for_landing_page": "https://doi.org/10.9/another-book", "host_type": "publisher"}]}
    monkeypatch.setattr(A, "fetch_json", lambda url, *a, **k: (unpaywall, 200))
    assert A.check_oa("10.9/book", book=True) is None
    assert A.check_oa("10.9/paper") == "https://doi.org/10.9/another-book"
    A.CONFIG["unpaywall_email"] = ""
    monkeypatch.setattr(A, "fetch_json", lambda url, *a, **k: ({"locations": [LANDING_ONLY]}, 200))
    assert A.check_oa("10.9/book", book=True) is None


def test_enrichment_tells_the_free_copy_check_which_is_a_book(monkeypatch):
    asked = []
    monkeypatch.setattr(A, "check_oa", lambda doi, book=False: asked.append((doi, book)))
    monkeypatch.setattr(A, "pmcids_for_dois", lambda dois: {})
    monkeypatch.setattr(A, "retraction_status", lambda doi: None)
    A.enrich_access([A._openalex_article(oa_work("book")),
                     A._article(doi="10.9/paper", source="Scopus")])
    assert sorted(asked) == [("10.9/book", True), ("10.9/paper", False)]


def test_a_free_copy_saved_under_the_rules_before_books_is_looked_up_again(monkeypatch):
    asked = []
    monkeypatch.setattr(A, "check_oa", lambda doi, book=False: asked.append(doi))
    monkeypatch.setattr(A, "pmcids_for_dois", lambda dois: {})
    monkeypatch.setattr(A, "retraction_status", lambda doi: None)
    A._DOI_CACHE["10.9/book"] = {"t": A.time.time(), "rules": 2, "kind": "open",
                                 "link": "https://doi.org/10.9/another-book", "retraction": None}
    a = A._openalex_article(oa_work("book"))
    A.enrich_access([a])
    assert asked == ["10.9/book"] and a["access_kind"] == "doi"


def cr_item(type_, **kw):
    return {"DOI": "10.9/cr", "type": type_, "title": ["Awake mapping"],
            "author": [{"family": "Doe", "given": "Jane"}], "issued": {"date-parts": [[2021]]},
            "publisher": "Example Publishing", "publisher-location": "Example City",
            "ISBN": ["0-306-40615-2", "9780804429573"],
            "editor": [{"family": "Moe", "given": "Mary"}, {"family": "Roe"}], **kw}


def test_a_crossref_chapter_names_its_book_not_its_series():
    a = A._crossref_article(cr_item("book-chapter",
                                    **{"container-title": ["Example Series", "Example Atlas"]}))
    assert a["journal"] == "Example Atlas" and a["pub_types"] == ["Book"]
    assert a["book"] == {"kind": "chapter", "title": "Example Atlas", "publisher": "Example Publishing",
                         "place": "Example City", "isbn": ["9780306406157", "9780804429573"],
                         "editors": ["Moe, Mary", "Roe"], "bookshelf": None}


def test_a_crossref_book_shows_its_publisher():
    a = A._crossref_article(cr_item("edited-book", **{"container-title": ["Example Online"]}))
    assert a["journal"] == "Example Publishing"
    assert (a["book"]["kind"], a["book"]["title"]) == ("book", "Awake mapping")


@pytest.mark.parametrize("type_, kind", [("book-part", "chapter"), ("book-section", "chapter"),
                                         ("reference-entry", "chapter"), ("monograph", "book"),
                                         ("reference-book", "book"), ("journal-article", None)])
def test_crossref_types_of_book(type_, kind):
    a = A._crossref_article(cr_item(type_, **{"container-title": ["Example"]}))
    assert (a["book"] or {}).get("kind") == kind
    assert ("Book" in a["pub_types"]) == bool(kind)


# ── Google Books ────────────────────────────────────────────────────────────

def volume(viewability="NO_PAGES", **access):
    """A Google Books volume, in the shape its API documents, placeholder values."""
    return {"volumeInfo": {"title": "Example Handbook", "subtitle": "Third edition",
                           "authors": ["Jane A. Doe", "Richard Roe"], "publisher": "Example Press",
                           "publishedDate": "2016-03-01", "description": "<p>A <b>handbook</b> &amp; more.</p>",
                           "industryIdentifiers": [{"type": "ISBN_10", "identifier": "0306406152"},
                                                   {"type": "ISBN_13", "identifier": "9780306406157"},
                                                   # a Library of Congress number: ten digits, no ISBN
                                                   {"type": "OTHER", "identifier": "LCCN:2001012345"}],
                           "previewLink": "https://books.google.example/preview",
                           "infoLink": "https://books.google.example/info"},
            "accessInfo": {"viewability": viewability, "publicDomain": False,
                           "webReaderLink": "https://play.google.example/reader", **access}}


@pytest.fixture
def google(monkeypatch):
    """A fake Google Books answering `reply[0]`; records the URLs asked."""
    asked, reply = Terms(), [({"totalItems": 0, "items": []}, 200)]

    def get(url, *a, **k):
        asked.append(url)
        return reply[0]
    monkeypatch.setattr(A, "fetch_json", get)
    A.CONFIG["google_books_api_key"] = "gb-key"
    asked.reply = reply
    return asked


def test_a_google_books_volume_is_read_as_one_edition_of_a_book():
    a = A._googlebooks_article(volume())
    assert a["title"] == "Example Handbook: Third edition"
    assert a["author_list"] == ["Doe, Jane A.", "Roe, Richard"] and a["authors"] == "Doe, J.; Roe, R."
    assert (a["year"], a["journal"], a["source"], a["pub_types"]) == (
        "2016", "Example Press", "Google Books", ["Book"])
    assert a["abstract"] == "A handbook & more."
    assert a["book"]["isbn"] == ["9780306406157"]           # its ISBN-10 and -13 are one book
    assert a["book"]["google"] == "https://books.google.example/info"
    assert (a["access_kind"], a["book"]["preview"]) == ("none", None)


def test_a_public_domain_volume_is_read_free_and_a_partial_one_previewed():
    free = A._googlebooks_article(volume("ALL_PAGES", publicDomain=True,
                                         accessViewStatus="FULL_PUBLIC_DOMAIN"))
    assert (free["access_kind"], free["access_link"]) == ("open", "https://play.google.example/reader")
    sample = A._googlebooks_article(volume("PARTIAL", accessViewStatus="SAMPLE"))
    assert sample["access_kind"] == "none"
    assert sample["book"]["preview"] == "https://books.google.example/preview"


def test_google_books_is_asked_with_its_key_page_order_and_author(google):
    google.reply[0] = ({"totalItems": 77, "items": [
        volume(), dict(volume(), volumeInfo=dict(volume()["volumeInfo"], authors=["John Roe"])),
        dict(volume(), volumeInfo=dict(volume()["volumeInfo"], publishedDate="1999"))]}, 200)
    arts, total = A.search_googlebooks("glioma", 100, 2000, None, sort="date", offset=40,
                                       people=A.people_filter("Jane Doe"))
    p = ol_params(google[0])
    assert google[0].startswith("https://www.googleapis.com/books/v1/volumes?")
    assert p == {"q": 'glioma inauthor:"Doe"', "maxResults": "40", "startIndex": "40",
                 "printType": "books", "orderBy": "newest", "key": "gb-key"}
    # Another author's book and one outside the years are left out here.
    assert [a["year"] for a in arts] == ["2016"] and total == 77


def test_an_author_alone_asks_google_books_by_the_name_only(google):
    A.search_googlebooks("", 10, None, None, people=A.people_filter("Jane Doe"))
    assert ol_params(google[0])["q"] == 'inauthor:"Doe"'


@pytest.mark.parametrize("status, body, says", [
    (429, {"error": {"message": "Quota exceeded"}}, "daily allowance for this key is used up (Quota exceeded)"),
    (400, {"error": {"message": "API key not valid."}}, "did not accept the API key (400: API key not valid.)"),
    (403, {"error": {"message": "Books API has not been used in project 1"}}, "Books API is turned on"),
    (0, None, "didn't respond"),
    (500, None, "returned HTTP 500."),
])
def test_google_books_says_why_it_refused(google, status, body, says):
    google.reply[0] = (body, status)
    with pytest.raises(RuntimeError, match=re.escape(says)):
        A.search_googlebooks("glioma", 10, None, None)


def test_google_books_needs_its_key_and_cannot_follow_an_institution_or_a_doi(google):
    A.CONFIG["google_books_api_key"] = ""
    with pytest.raises(RuntimeError, match="No Google Books API key"):
        A.search_googlebooks("glioma", 10, None, None)
    with pytest.raises(A.SourceCannotAnswer, match="institution"):
        A.search_googlebooks("glioma", 10, None, None, people=A.people_filter(None, "Example Hospital"))
    with pytest.raises(A.SourceCannotAnswer):
        A.doi_lookup("googlebooks", A.search_googlebooks, ["10.9/x"])
    assert google == []


def test_the_google_books_key_is_a_secret_kept_by_settings(client, auth):
    assert "google_books_api_key" in A.SECRET_KEYS
    assert A._KEY_REQUIRED["googlebooks"] == ("google_books_api_key", "Google Books")
    assert client.post("/settings", json={"google_books_api_key": "gb-key-1234"},
                       headers=auth, base_url=BASE).json["ok"]
    shown = client.get("/settings", headers=auth, base_url=BASE).json["google_books_api_key"]
    assert shown and "gb-key-1234" not in shown
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert 'id="badge_googlebooks">Available<' in page and "hasGooglebooks:     true" in page


def test_google_books_comes_after_open_library_and_asks_for_its_key_until_it_has_one(client, auth):
    keys = [k for k, *_ in A.SOURCES]
    assert keys.index("googlebooks") == keys.index("openlibrary") + 1
    client.post("/sources", json={"sources": ["pubmed", "googlebooks"]}, headers=auth, base_url=BASE)
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert 'id="badge_googlebooks">API required<' in page
    assert re.findall(r'class="db-item checked" data-db="([a-z]+)"', page) == ["pubmed"]


def test_a_google_books_book_is_exported_with_its_page(tmp_path, monkeypatch):
    a = A._googlebooks_article(volume())
    md = _export(tmp_path, monkeypatch, [a], "md")
    assert "**Google Books:** https://books.google.example/info" in md
    assert A.article_to_zotero_item(a)["url"] == "https://books.google.example/info"


def test_every_settings_field_the_page_reads_is_on_the_page():
    js = (Path(A.__file__).parent / "static" / "js" / "app.js").read_text(encoding="utf-8")
    html = (Path(A.__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r"getElementById\('(set_[a-z_]+)'\)", js))
    ids |= set(re.findall(r"^\s+\w+:\s+'(set_[a-z_]+)',", js, re.M))
    assert "set_googlebooks" in ids
    assert {i for i in ids if f'id="{i}"' not in html} == set()


# ── Library resources: platforms searched in their own window ───────────────

def test_the_ready_made_library_resources_and_their_search_addresses():
    assert {r["id"]: r["url"] for r in A.LIBRARY_RESOURCES} == {
        "clinicalkey": "https://www.clinicalkey.com/#!/search/{q}",
        # As Zotero's translator for McGraw Hill's Access sites knows it.
        "accessmedicine": "https://accessmedicine.mhmedical.com/SearchResults.aspx?q={q}",
        # As UpToDate's own search box sends it.
        "uptodate": "https://www.uptodate.com/contents/search?search={q}&source=USER_INPUT"}


def test_settings_keeps_the_ticked_resources_and_ones_own(client, auth):
    sent = {"on": ["uptodate", "clinicalkey", "unknown"],
            "own": [{"name": "  Example   Platform ", "url": "https://example.org/find?words={q}"}]}
    r = client.post("/settings", json={"library_resources": sent}, headers=auth, base_url=BASE)
    assert r.status_code == 200 and r.json["ok"]
    kept = {"on": ["clinicalkey", "uptodate"],
            "own": [{"name": "Example Platform", "url": "https://example.org/find?words={q}"}]}
    assert A.CONFIG["library_resources"] == kept
    assert client.get("/settings", headers=auth, base_url=BASE).json["library_resources"] == kept
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    assert f'libraryResources:   {json.dumps(kept)}' in page
    assert '"id": "accessmedicine"' in page and 'id="resourceButtons"' in page


@pytest.mark.parametrize("own, says", [
    ({"name": "Example", "url": "https://example.org/find?words=glioma"}, "needs {q} where the words go"),
    ({"name": "Example", "url": "example.org/find?q={q}"}, "must be a web address, beginning https://"),
    ({"name": "Example", "url": "https://example.org/find?q={q} more"}, "with no spaces"),
    ({"name": "  ", "url": "https://example.org/find?q={q}"}, "has no name"),
])
def test_a_resource_that_cannot_be_used_is_refused_and_nothing_is_saved(client, auth, own, says):
    r = client.post("/settings", json={"library_resources": {"on": [], "own": [own]},
                                       "pubmed_api_key": "pm-key-1234"}, headers=auth, base_url=BASE)
    assert r.status_code == 400 and not r.json["ok"] and says in r.json["message"]
    assert A.CONFIG["library_resources"] == {"on": [], "own": []} and A.CONFIG["pubmed_api_key"] == ""


def test_at_most_twenty_resources_of_ones_own(client, auth):
    own = [{"name": f"R{i}", "url": f"https://example.org/{i}?q={{q}}"} for i in range(21)]
    r = client.post("/settings", json={"library_resources": {"on": [], "own": own}},
                    headers=auth, base_url=BASE)
    assert r.status_code == 400 and "at most 20" in r.json["message"]


def test_resources_saved_badly_by_hand_are_read_without_failing():
    A.CONFIG["library_resources"] = {"on": ["uptodate", "nope", 3], "own": [{"name": "X"}, "junk", None]}
    assert A.library_resources() == {"on": ["uptodate"], "own": []}
    A.CONFIG["library_resources"] = "junk"
    assert A.library_resources() == {"on": [], "own": []}


def test_the_page_arrives_with_the_search_buttons_drawn_as_the_page_draws_them(client, auth):
    A.CONFIG["library_resources"] = {"on": ["uptodate", "clinicalkey"],
                                     "own": [{"name": "Example <Platform>", "url": "https://example.org/?q={q}"}]}
    page = client.get("/", base_url=BASE).get_data(as_text=True)
    drawn = re.search(r'<div id="resourceButtons">(.*?)</div>', page, re.S).group(1)
    assert re.findall(r'onclick="openLibraryResource\((\d)\)"><svg class="ico" aria-hidden="true">'
                      r'<use href="#i-external"/></svg> Search ([^<]+)</button>', drawn) == [
        ("0", "ClinicalKey"), ("1", "UpToDate"), ("2", "Example &lt;Platform&gt;")]
    js = (Path(A.__file__).parent / "static" / "js" / "app.js").read_text(encoding="utf-8")
    # The same button as the page draws after a save.
    assert ('`<button class="select-all-btn scholar-btn" type="button" onclick="openLibraryResource(${i})">` +\n'
            "    `${ico('external')} Search ${escHtml(r.name)}</button>`") in js

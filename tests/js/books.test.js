// A book on NCBI Bookshelf is read at its Bookshelf page, in a MedSearch
// window; a free PDF still opens in the viewer; and the results' type filter
// offers Book.
import { test } from "node:test";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { freeCopyButton } = load(["escAttr", "ico", "freeCopyButton"]);

const BOOKSHELF = "https://www.ncbi.nlm.nih.gov/books/NBK900001/";

test("a Bookshelf book opens at Bookshelf in a MedSearch window", () => {
  const html = freeCopyButton({title: "Low-Grade Gliomas", access_kind: "open", access_link: BOOKSHELF,
                               book: {kind: "chapter", bookshelf: "NBK900001"}});
  assert.match(html, /Read on Bookshelf<\/button>$/);
  assert.ok(html.includes(`onclick="openInAppBrowser('${BOOKSHELF}', 'Low-Grade Gliomas')"`));
  assert.ok(!html.includes("openPdf"));
});

test("a free paper still opens in the PDF viewer", () => {
  const html = freeCopyButton({title: "A paper", access_kind: "open", access_link: "https://x.org/a.pdf",
                               book: null});
  assert.match(html, /Read PDF<\/button>$/);
  assert.ok(html.includes(`onclick="openPdf('https://x.org/a.pdf', 'A paper')"`));
});

test("nothing free, no button", () => {
  assert.equal(freeCopyButton({access_kind: "doi", access_link: "https://doi.org/10.1/x"}), "");
  assert.equal(freeCopyButton({access_kind: "open", access_link: null}), "");
});

// The results' type filter offers Book when the list holds books.

test("Book is offered in the type filter, last, only when books are listed", () => {
  const src = readFileSync(new URL("../../static/js/app.js", import.meta.url), "utf8");
  globalThis._TYPE_ORDER = new Function(`return ${src.match(/const _TYPE_ORDER = (\[[^\]]*\]);/)[1]}`)();
  const { _refreshTypeOptions } = load(["escHtml", "_refreshTypeOptions"]);
  const sel = {value: "", innerHTML: "", options: [{}]};
  globalThis.document = {getElementById: () => sel};
  const offered = () => [...sel.innerHTML.matchAll(/<option value="([^"]+)">/g)].map(m => m[1]);
  globalThis.allArticles = [{pub_types: ["Review"]}];
  _refreshTypeOptions();
  assert.deepEqual(offered(), ["Review"]);
  sel.options = [{}, {value: "Review"}];
  globalThis.allArticles = [{pub_types: ["Book", "Review"]}, {pub_types: ["Registered trial"]}];
  _refreshTypeOptions();
  assert.deepEqual(offered(), ["Review", "Registered trial", "Book"]);
});

// ── Open Library ────────────────────────────────────────────────────────────

const { borrowButton, libraryButtons, worldcatUrl } =
  load(["escAttr", "ico", "borrowButton", "worldcatUrl", "libraryButtons"]);
const WORK = "https://openlibrary.org/works/OL1W";

test("a free Open Library book is read in a MedSearch window", () => {
  const html = freeCopyButton({title: "Example Handbook", access_kind: "open",
                               access_link: "https://archive.org/details/scan",
                               book: {kind: "book", openlibrary: WORK}});
  assert.match(html, /Read free<\/button>$/);
  assert.ok(html.includes(`onclick="openInAppBrowser('https://archive.org/details/scan', 'Example Handbook')"`));
});

test("a lent book has Borrow, at its edition's page in a MedSearch window", () => {
  const html = borrowButton({title: "Example Handbook",
                             book: {borrow: "https://openlibrary.org/books/OL2M"}});
  assert.match(html, /Borrow<\/button>$/);
  assert.ok(html.includes(`onclick="openInAppBrowser('https://openlibrary.org/books/OL2M', 'Example Handbook')"`));
  assert.equal(borrowButton({book: {borrow: null}}), "");
  assert.equal(borrowButton({book: null}), "");
});

test("WorldCat is asked by the ISBN, else by the title and the first author", () => {
  const byIsbn = new URL(worldcatUrl({title: "Example Handbook", author_list: ["Doe, Jane"],
                                      book: {isbn: ["9780306406157"]}}));
  assert.equal(byIsbn.origin + byIsbn.pathname, "https://search.worldcat.org/search");
  assert.equal(byIsbn.searchParams.get("q"), "bn:9780306406157");
  const byTitle = new URL(worldcatUrl({title: "Example Handbook", author_list: ["Doe, Jane", "Roe, R"],
                                       book: {isbn: []}}));
  assert.equal(byTitle.searchParams.get("q"), "Example Handbook Doe");
  assert.equal(new URL(worldcatUrl({title: "Example & Handbook", book: {}})).searchParams.get("q"),
               "Example & Handbook");
});

test("a book has Find in a library and its Open Library page; a Bookshelf book and a paper have neither", () => {
  const html = libraryButtons({title: "Example Handbook", author_list: [], book: {isbn: [], openlibrary: WORK}});
  assert.deepEqual([...html.matchAll(/<\/svg> ([^<]+)<\/button>/g)].map(m => m[1]),
                   ["Find in a library", "Open Library"]);
  assert.ok(html.includes("openInAppBrowser('https://search.worldcat.org/search?q=Example+Handbook'"));
  assert.ok(html.includes(`openInAppBrowser('${WORK}', 'Example Handbook')`));
  const elsewhere = libraryButtons({title: "A chapter", book: {isbn: [], openlibrary: null}});
  assert.match(elsewhere, /Find in a library<\/button>$/);
  assert.equal(libraryButtons({title: "A chapter", book: {bookshelf: "NBK1"}}), "");
  assert.equal(libraryButtons({title: "A paper", book: null}), "");
});

// ── A book's row, as the results list draws it ──────────────────────────────

const { makeCard } = load(["escHtml", "escAttr", "ico", "freeCopyButton", "borrowButton",
                           "worldcatUrl", "libraryButtons", "makeCard"]);

function rowButtons(a) {
  globalThis.document = {createElement: () => ({classList: {add() {}}, innerHTML: ""})};
  globalThis.currentProxyUrl = () => "";
  globalThis.proxify = (u) => u;
  const html = makeCard({_idx: 0, pub_types: ["Book"], scihub: [], ...a}).innerHTML;
  const links = html.slice(html.indexOf('<div class="article-links">'));
  return [...links.matchAll(/<(?:button|a) class="link-btn[^>]*>(?:<svg[^>]*>.*?<\/svg> )?([^<]+)<\/(?:button|a)>/g)]
    .map(m => m[1].trim());
}

test("an Open Library row: Borrow, then the library and its Open Library page", () => {
  assert.deepEqual(rowButtons({title: "Example Handbook", access_kind: "none", access_link: null,
                               book: {kind: "book", isbn: [], openlibrary: WORK,
                                      borrow: "https://openlibrary.org/books/OL2M"}}),
                   ["Borrow", "Find in a library", "Open Library", "Explain", "Zotero"]);
});

test("a Bookshelf row: Read on Bookshelf and PubMed, no library", () => {
  assert.deepEqual(rowButtons({title: "Low-Grade Gliomas", pmid: "900001", access_kind: "open",
                               access_link: BOOKSHELF, book: {kind: "chapter", isbn: [], bookshelf: "NBK900001"}}),
                   ["Read on Bookshelf", "PubMed", "Explain", "Zotero"]);
});

test("a paper's row is as it was", () => {
  assert.deepEqual(rowButtons({title: "A paper", doi: "10.1/x", pmid: "1", pub_types: [], book: null,
                               access_kind: "open", access_link: "https://x.org/a.pdf",
                               scihub: ["https://sci-hub.example/10.1/x"]}),
                   ["Read PDF", "Sci-Hub", "PubMed", "Citations", "Explain", "Zotero"]);
});

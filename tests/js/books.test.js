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
  const src = readFileSync(new URL("../../static/js/app.js", import.meta.url), "utf8")
    .replace(/\r\n/g, "\n");   // as checked out on Windows
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
  load(["escAttr", "escHtml", "ico", "borrowButton", "worldcatUrl", "libraryOpenUrl", "libraryButtons"]);
globalThis.activeLibrary = () => null;   // No library, unless a test picks one
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
                           "worldcatUrl", "libraryOpenUrl", "libraryButtons", "makeCard"]);

function rowButtons(a, library = null) {
  globalThis.document = {createElement: () => ({classList: {add() {}}, innerHTML: ""})};
  globalThis.activeLibrary = () => library;
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

// ── Books from OpenAlex and Crossref ────────────────────────────────────────

test("a chapter is looked up in WorldCat as its book, and not at all when its book is unknown", () => {
  const byBook = worldcatUrl({title: "Awake mapping", author_list: ["Doe, Jane"],
                              book: {kind: "chapter", title: "Example Atlas", isbn: []}});
  assert.equal(new URL(byBook).searchParams.get("q"), "Example Atlas");
  const byIsbn = worldcatUrl({title: "Awake mapping", book: {kind: "chapter", title: "Example Atlas",
                                                             isbn: ["9780306406157"]}});
  assert.equal(new URL(byIsbn).searchParams.get("q"), "bn:9780306406157");
  const unknown = {title: "Awake mapping", author_list: ["Doe, Jane"],
                   book: {kind: "chapter", title: "", isbn: [], openlibrary: null}};
  assert.equal(worldcatUrl(unknown), "");
  assert.equal(libraryButtons(unknown), "");
});

test("a Crossref chapter's row: DOI, Sci-Hub as now, then Find in a library", () => {
  assert.deepEqual(rowButtons({title: "Awake mapping", doi: "10.9/cr", access_kind: "doi",
                               access_link: "https://doi.org/10.9/cr",
                               scihub: ["https://sci-hub.example/10.9/cr"],
                               book: {kind: "chapter", title: "Example Atlas", isbn: ["9780306406157"]}}),
                   ["DOI", "Sci-Hub", "Find in a library", "Citations", "Explain", "Zotero"]);
});

// ── Google Books ────────────────────────────────────────────────────────────

test("a public-domain Google book is read free; one with sample pages is previewed", () => {
  const free = freeCopyButton({title: "Example Handbook", access_kind: "open",
                               access_link: "https://play.google.example/reader",
                               book: {kind: "book", google: "https://books.google.example/info"}});
  assert.match(free, /Read free<\/button>$/);
  assert.ok(free.includes("openInAppBrowser('https://play.google.example/reader'"));
  const sample = borrowButton({title: "Example Handbook",
                               book: {preview: "https://books.google.example/preview"}});
  assert.match(sample, /Preview<\/button>$/);
  assert.ok(sample.includes("openInAppBrowser('https://books.google.example/preview', 'Example Handbook')"));
});

test("a Google book's row: Preview, then Find in a library by its ISBN", () => {
  assert.deepEqual(rowButtons({title: "Example Handbook", access_kind: "none", access_link: null,
                               book: {kind: "book", isbn: ["9780306406157"],
                                      google: "https://books.google.example/info",
                                      preview: "https://books.google.example/preview"}}),
                   ["Preview", "Find in a library", "Explain", "Zotero"]);
});

// ── The user's own library: Get it at … ────────────────────────────────────

const { libraryOpenUrl, openUrlToSave, buildInstitutions } =
  load(["libraryOpenUrl", "openUrlToSave", "buildInstitutions"]);
const SRC = readFileSync(new URL("../../static/js/app.js", import.meta.url), "utf8").replace(/\r\n/g, "\n");
globalThis.PREDEFINED_INSTITUTIONS =
  new Function(`return ${SRC.match(/const PREDEFINED_INSTITUTIONS = (\[[\s\S]*?\n\]);/)[1]}`)();
const UNITN_CATALOGUE = "https://strutture-provincia.primo.exlibrisgroup.com/discovery/openurl" +
                        "?institution=39SBT_INST&vid=39SBT_INST:39SBT_UNI_TN";
const LIB = {label: "Example Uni", url: "https://ezp.example.edu", openurl: "https://find.example.edu/openurl?vid=X"};

/** The OpenURL's fields, in order, as the library's catalogue reads them. */
function asked(url) {
  const u = new URL(url);
  return {base: u.origin + u.pathname, fields: [...u.searchParams]};
}

test("a whole book is asked by its ISBN, title, first author, year and publisher", () => {
  const {base, fields} = asked(libraryOpenUrl(
    {title: "Example Handbook: Second Edition", author_list: ["Doe, Jane", "Roe, R"], year: "2016",
     doi: "10.1000/xyz123", book: {kind: "book", isbn: ["9780306406157", "0306406152"], publisher: "Example & Sons"}}, LIB));
  assert.equal(base, "https://find.example.edu/openurl");
  assert.deepEqual(fields, [
    ["vid", "X"], ["url_ver", "Z39.88-2004"], ["ctx_ver", "Z39.88-2004"],
    ["rft_val_fmt", "info:ofi/fmt:kev:mtx:book"], ["rft.genre", "book"],
    ["rft.btitle", "Example Handbook: Second Edition"], ["rft.isbn", "9780306406157"],
    ["rft.aulast", "Doe"], ["rft.date", "2016"], ["rft.pub", "Example & Sons"],
    ["rft_id", "info:doi/10.1000/xyz123"]]);
});

test("a chapter is asked as a chapter of its book; a year that isn't one is left out", () => {
  const {fields} = asked(libraryOpenUrl(
    {title: "Awake mapping", author_list: [], year: "n.d.",
     book: {kind: "chapter", title: "Example Atlas", isbn: []}}, LIB));
  assert.deepEqual(fields.slice(4), [["rft.genre", "bookitem"], ["rft.atitle", "Awake mapping"],
                                     ["rft.btitle", "Example Atlas"]]);
});

test("no address, or nothing to find the book by: no link", () => {
  const book = {title: "Example Handbook", book: {kind: "book", isbn: []}};
  assert.equal(libraryOpenUrl(book, {...LIB, openurl: ""}), "");
  assert.equal(libraryOpenUrl(book, {...LIB, openurl: undefined}), "");
  assert.equal(libraryOpenUrl(book, null), "");
  assert.equal(libraryOpenUrl({title: "Awake mapping", book: {kind: "chapter", title: "", isbn: []}}, LIB), "");
  assert.equal(libraryOpenUrl({title: " ", book: {kind: "book", isbn: []}}, LIB), "");
  assert.notEqual(libraryOpenUrl({title: "Awake mapping", book: {kind: "chapter", isbn: ["9780306406157"]}}, LIB), "");
});

test("the fields join the address however it ends", () => {
  const book = {title: "T", book: {kind: "book"}};
  assert.ok(libraryOpenUrl(book, {openurl: "https://r.example.edu/openurl"}).startsWith("https://r.example.edu/openurl?url_ver="));
  assert.ok(libraryOpenUrl(book, {openurl: "https://r.example.edu/sfx?"}).startsWith("https://r.example.edu/sfx?url_ver="));
  assert.ok(libraryOpenUrl(book, {openurl: "https://r.example.edu/o?a=1&"}).startsWith("https://r.example.edu/o?a=1&url_ver="));
  assert.ok(libraryOpenUrl(book, {openurl: " https://r.example.edu/o?a=1 "}).startsWith("https://r.example.edu/o?a=1&url_ver="));
});

test("Get it at the library comes first, opens in a MedSearch window, and shows its name safely", () => {
  globalThis.activeLibrary = () => ({...LIB, label: "Uni <Example>"});
  const html = libraryButtons({title: "Example Handbook", author_list: [], book: {kind: "book", isbn: []}});
  globalThis.activeLibrary = () => null;
  assert.deepEqual([...html.matchAll(/<\/svg> ([^<]+)<\/button>/g)].map(m => m[1]),
                   ["Get it at Uni &lt;Example&gt;", "Find in a library"]);
  // & is written &amp; inside the attribute; the browser decodes it back.
  assert.ok(html.includes("openInAppBrowser('https://find.example.edu/openurl?vid=X&amp;url_ver=Z39.88-2004&amp;ctx_ver="));
  assert.ok(html.includes("rft.btitle=Example%20Handbook', 'Example Handbook')"));
});

test("a book's row with the library picked: Get it at, then WorldCat; a paper's row has neither", () => {
  const unitn = {label: "UniTN", url: "https://ezp.biblio.unitn.it", openurl: UNITN_CATALOGUE};
  assert.deepEqual(rowButtons({title: "Example Handbook", access_kind: "none", access_link: null,
                               book: {kind: "book", isbn: ["9780306406157"]}}, unitn),
                   ["Get it at UniTN", "Find in a library", "Explain", "Zotero"]);
  assert.deepEqual(rowButtons({title: "Example Handbook", access_kind: "none", access_link: null,
                               book: {kind: "book", isbn: ["9780306406157"]}}, {...unitn, openurl: ""}),
                   ["Find in a library", "Explain", "Zotero"]);
  assert.deepEqual(rowButtons({title: "A paper", doi: "10.1/x", pmid: "1", pub_types: [], book: null,
                               access_kind: "none", access_link: null, scihub: []}, unitn),
                   ["PubMed", "Citations", "Explain", "Zotero"]);
});

test("UniTN's catalogue is built in; the others have none until set", () => {
  globalThis.savedProxies = [];
  const libs = buildInstitutions();
  assert.deepEqual(libs.map(l => [l.label, l.openurl]),
                   [["UniTN", UNITN_CATALOGUE], ["ASUIT", ""], ["FBK", ""]]);
});

test("a built-in catalogue is saved only when changed, so emptying it hides the button", () => {
  globalThis.savedProxies = [{id: "unitn", label: "UniTN", url: "https://ezp.biblio.unitn.it", openurl: ""},
                             {label: "Mine", url: "https://ezp.example.edu", openurl: LIB.openurl}];
  const [unitn, , , mine] = buildInstitutions();
  assert.equal(unitn.openurl, "");
  assert.equal(mine.openurl, LIB.openurl);
  assert.deepEqual(openUrlToSave({id: "unitn", openurl: UNITN_CATALOGUE}), {});
  assert.deepEqual(openUrlToSave({id: "unitn", openurl: ""}), {openurl: ""});
  assert.deepEqual(openUrlToSave({id: "unitn", openurl: " https://x.example.edu/o "}), {openurl: "https://x.example.edu/o"});
  assert.deepEqual(openUrlToSave({id: null, openurl: ""}), {});
  assert.deepEqual(openUrlToSave({id: null, openurl: LIB.openurl}), {openurl: LIB.openurl});
});

test("the library editor's Save keeps the catalogue address, for a library edited or added", () => {
  const { saveProxyEditor } = load(["saveProxyEditor"]);
  const fields = {proxyEditorUrl: {value: " https://ezp.example.edu "},
                  proxyEditorOpenUrl: {value: ` ${LIB.openurl} `}, proxyEditorLabel: {value: "Mine"}};
  globalThis.document = {getElementById: (id) => fields[id]};
  for (const f of ["closeProxyEditor", "renderProxyRows", "renderProxyPicker"]) globalThis[f] = () => {};
  globalThis.activeProxy = 0;
  globalThis.institutionProxies = [{id: "unitn", label: "UniTN", url: "", openurl: UNITN_CATALOGUE, predefined: true}];
  globalThis.editingProxyIndex = 0;
  saveProxyEditor();
  assert.equal(institutionProxies[0].openurl, LIB.openurl);
  globalThis.editingProxyIndex = null;
  fields.proxyEditorOpenUrl.value = "";
  saveProxyEditor();
  assert.deepEqual(institutionProxies[1], {id: null, label: "Mine", url: "https://ezp.example.edu",
                                           openurl: "", predefined: false});
});

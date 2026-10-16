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

// Google Scholar is opened, not asked: the address that opens it with the
// search box's text and the years from Options.
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { scholarUrl } = load(["scholarUrl"]);

test("the search goes in Scholar's q, every character of it encoded", () => {
  const url = new URL(scholarUrl('"awake craniotomy" & mapping'));
  assert.equal(url.origin + url.pathname, "https://scholar.google.com/scholar");
  assert.equal(url.searchParams.get("q"), '"awake craniotomy" & mapping');
  assert.equal(url.searchParams.has("as_ylo"), false);
  assert.equal(url.searchParams.has("as_yhi"), false);
});

test("the years go in Scholar's own year fields", () => {
  const url = new URL(scholarUrl("glioma", "2018", " 2024 "));
  assert.equal(url.searchParams.get("as_ylo"), "2018");
  assert.equal(url.searchParams.get("as_yhi"), "2024");
});

test("a half-typed year is left out rather than sent", () => {
  const url = new URL(scholarUrl("glioma", "201", "abcd"));
  assert.equal(url.searchParams.has("as_ylo"), false);
  assert.equal(url.searchParams.has("as_yhi"), false);
});

// ── An author, in Scholar's own form ────────────────────────────────────────

const { scholarAuthor, describeSearch } = load(["scholarAuthor", "describeSearch"]);
const { scholarUrl: withAuthor } = load(["scholarAuthor", "scholarUrl"]);

test("an author is written as Scholar writes names: first initial and family name", () => {
  assert.equal(scholarAuthor("Jane A. Doe"), "J Doe");
  assert.equal(scholarAuthor("Doe, Jane"), "J Doe");
  assert.equal(scholarAuthor("Ludwig van Gogh"), "L van Gogh");
  assert.equal(scholarAuthor("Élise Exemple"), "É Exemple");
  assert.equal(scholarAuthor("Doe"), "Doe");
  assert.equal(scholarAuthor("Doe JA"), "J Doe");
  assert.equal(scholarAuthor('Jane "the" Doe'), "J Doe");
});

test("the author goes in Scholar's author: operator, after the words", () => {
  const url = new URL(withAuthor("glioma", "", "", "Jane Doe"));
  assert.equal(url.searchParams.get("q"), 'glioma author:"J Doe"');
  assert.equal(new URL(withAuthor("", "", "", "Jane Doe")).searchParams.get("q"), 'author:"J Doe"');
});

test("a search is described with who and where it was narrowed to", () => {
  assert.equal(describeSearch({query: "glioma"}), "glioma");
  assert.equal(describeSearch({query: "glioma", author: {name: "Jane Doe"}}), "glioma (author: Jane Doe)");
  assert.equal(describeSearch({query: "", author: {name: "Jane Doe"}, institution: {name: "A Hospital"}}),
               "author: Jane Doe; institution: A Hospital");
});

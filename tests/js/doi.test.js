// The dialog at the end of a search: the sources that failed, and the DOIs
// nothing was found for.
//
//     node --test tests/js/*.test.js      (or just run the pytest suite)
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { searchProblems } = load(["searchProblems"]);

const missingOne = { count: 1, text: "Nothing was found for 10.1000/x …" };

test("a search with nothing to report opens no dialog", () => {
  assert.equal(searchProblems(new Map(), null, 5), null);
  assert.equal(searchProblems(new Map(), null, 0), null);
});

test("a DOI nothing was found for is said as such, not as a failed source", () => {
  const p = searchProblems(new Map(), missingOne, 0);
  assert.equal(p.title, "DOI not found");
  assert.equal(p.text, missingOne.text);
});

test("several are counted, and the papers that were found are said to be shown", () => {
  const p = searchProblems(new Map(), { count: 2, text: "…" }, 3);
  assert.equal(p.title, "2 DOIs not found");
  assert.equal(p.text, "…\n\nThe papers that were found are shown.");
});

test("a failed source keeps its title, and the missing DOI is added to the same dialog", () => {
  const errored = new Map([["Scopus", "Scopus rejected the request (401)."]]);
  const p = searchProblems(errored, missingOne, 1);
  assert.equal(p.title, "Scopus returned no results");
  assert.equal(p.text, `Scopus: Scopus rejected the request (401).\n\n${missingOne.text}` +
                       "\n\nThe other sources' results are shown.");
});

test("an ordinary search's failures read as they always have", () => {
  const errored = new Map([["Scopus", "a"], ["Web of Science", "b"]]);
  const p = searchProblems(errored, null, 0);
  assert.equal(p.title, "2 sources returned no results");
  assert.equal(p.text, "Scopus: a\n\nWeb of Science: b");
});

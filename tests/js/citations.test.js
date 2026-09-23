// The "Cited by" note in the citation window: where the list came from, and
// which source failed or could not be asked, so a short list is never taken
// for a complete one.
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { citeSourcesNote } = load(["escHtml", "citeSourcesNote"]);

test("each source says what it did, and a failure says why", () => {
  const note = citeSourcesNote([
    { label: "PubMed", status: "ok", count: 0 },
    { label: "Scopus", status: "failed", error: "Scopus quota exceeded (429)." },
    { label: "Web of Science", status: "no key" },
    { label: "OpenCitations", status: "ok", count: 3 },
  ]);
  assert.match(note, /PubMed 0/);
  assert.match(note, /Scopus failed: Scopus quota exceeded \(429\)\./);
  assert.match(note, /cite-note-failed/);
  assert.match(note, /Web of Science: no API key set/);
  assert.match(note, /OpenCitations 3 more/);
});

test("a reason from a server cannot inject markup", () => {
  const note = citeSourcesNote([{ label: "Scopus", status: "failed", error: "<img src=x>" }]);
  assert.doesNotMatch(note, /<img/);
});

test("no reports, no note", () => {
  assert.equal(citeSourcesNote(undefined), "");
});

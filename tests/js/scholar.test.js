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

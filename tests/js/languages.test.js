// Languages under Options: the first one added brings English, English comes
// first, a chip beside the search bar while any is set, and each search sends them.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { load } from "./load.mjs";

const NAMES = {en: "English", it: "Italian", de: "German", fr: "French"};
globalThis.LANGUAGE_NAMES = NAMES;
const fns = load(["escHtml", "escAttr", "ico", "languagesAfterAdding", "languageLabel", "setLanguages",
                  "addLanguage", "removeLanguage", "renderLanguages", "finalizeSourceGroup"]);

function fakePage() {
  const els = {};
  globalThis.document = {getElementById: (id) => (els[id] ||= {id, innerHTML: "", outerHTML: "",
    insertAdjacentHTML(where, html) { this.innerHTML = where === "afterbegin" ? html + this.innerHTML : this.innerHTML + html; }})};
  return els;
}

test("the first language added brings English, which always comes first", () => {
  assert.deepEqual(fns.languagesAfterAdding([], "it"), ["en", "it"]);
  assert.deepEqual(fns.languagesAfterAdding([], "en"), ["en"]);
  assert.deepEqual(fns.languagesAfterAdding(["en", "it"], "de"), ["en", "it", "de"]);
  assert.deepEqual(fns.languagesAfterAdding(["it"], "en"), ["en", "it"]);
  assert.deepEqual(fns.languagesAfterAdding(["en", "it"], "it"), ["en", "it"]);
  assert.deepEqual(fns.languagesAfterAdding(["en"], ""), ["en"]);
  assert.equal(fns.languageLabel(["en", "it"]), "English, Italian");
});

test("Options shows Any and the menu; with languages set, their chips and the chip by the search bar", () => {
  const els = fakePage();
  const posts = [];
  globalThis.fetch = (url, opts) => { posts.push([url, JSON.parse(opts.body)]); return Promise.resolve({}); };
  globalThis.languages = [];
  fns.renderLanguages();
  assert.match(els.languageList.innerHTML, /<span class="language-any">Any<\/span>/);
  assert.equal(els.languageChip.innerHTML, "");
  assert.deepEqual([...els.languageAdd.innerHTML.matchAll(/<option value="(\w*)">/g)].map(m => m[1]),
                   ["", "en", "it", "de", "fr"]);
  fns.addLanguage("it");
  assert.deepEqual(globalThis.languages, ["en", "it"]);
  assert.deepEqual(posts, [["/languages", {languages: ["en", "it"]}]]);
  assert.deepEqual([...els.languageList.innerHTML.matchAll(/<span>(\w+)<\/span>/g)].map(m => m[1]), ["English", "Italian"]);
  assert.ok(els.languageList.innerHTML.includes(`onclick="removeLanguage('it')"`));
  assert.deepEqual([...els.languageAdd.innerHTML.matchAll(/<option value="(\w*)">/g)].map(m => m[1]), ["", "de", "fr"]);
  assert.match(els.languageChip.innerHTML, /<span>English, Italian<\/span>/);
  assert.ok(els.languageChip.innerHTML.includes(`onclick="setLanguages([])"`));
  fns.removeLanguage("en");
  assert.deepEqual(globalThis.languages, ["it"]);
  fns.setLanguages([]);
  assert.equal(els.languageChip.innerHTML, "");
  assert.deepEqual(posts.at(-1), ["/languages", {languages: []}]);
});

test("a database's note shows above its results, and alone when it found nothing", () => {
  const els = fakePage();
  els.body_grp_Crossref = {...document.getElementById("body_grp_Crossref"), innerHTML: "<div>result</div>"};
  globalThis.document.getElementById("grp_Crossref");
  fns.finalizeSourceGroup("Crossref", 1, null, "Crossref can't be searched by language.");
  assert.equal(els.body_grp_Crossref.innerHTML.indexOf('<div class="source-empty source-note">Crossref can'), 0);
  assert.ok(els.body_grp_Crossref.innerHTML.endsWith("<div>result</div>"));
  els.body_grp_Crossref.innerHTML = "";
  fns.finalizeSourceGroup("Crossref", 0, null, "Nothing here.");
  assert.equal(els.body_grp_Crossref.innerHTML, '<div class="source-empty">Nothing here.</div>');
});

test("each search sends the languages, Find more the same ones, and the page draws them at start", () => {
  const src = readFileSync(new URL("../../static/js/app.js", import.meta.url), "utf8");
  const run = src.slice(src.indexOf("function runSearch("), src.indexOf("// Fresh search: rebuild the results area"));
  assert.ok(run.includes("    languages:   [...languages],\n"));
  assert.ok(run.includes("author: prev.author, institution: prev.institution,\n                                     languages: prev.languages});"));
  assert.match(src, /^renderLanguages\(\);$/m);
});

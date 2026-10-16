// Library resources: the platforms a library subscribes to that no other app
// can search, opened in a MedSearch window through the library, with the
// search filled in; and their list in Settings.
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const PRESETS = [
  {id: "clinicalkey", name: "ClinicalKey", url: "https://www.clinicalkey.com/#!/search/{q}"},
  {id: "uptodate", name: "UpToDate", url: "https://www.uptodate.com/contents/search?search={q}&source=USER_INPUT"},
];
const OWN = {name: "Example Platform", url: "https://example.org/find?words={q}&x=1"};

const fns = load(["escHtml", "escAttr", "ico", "activeResources", "resourceUrl", "resourceProblem",
                  "renderResourceButtons", "openLibraryResource", "renderResourceList",
                  "toggleResource", "addOwnResource", "removeOwnResource", "saveSettings"]);

function fakePage(values = {}) {
  const els = {};
  globalThis.document = {getElementById: (id) => (els[id] ||= {id, value: values[id] || "",
                                                                innerHTML: "", hidden: true, checked: false})};
  return els;
}

test("the words go where {q} is, encoded, as often as it appears", () => {
  assert.equal(fns.resourceUrl(PRESETS[0].url, "awake craniotomy & mapping"),
               "https://www.clinicalkey.com/#!/search/awake%20craniotomy%20%26%20mapping");
  assert.equal(fns.resourceUrl("https://e.org/s?a={q}&b={q}", "x/y"), "https://e.org/s?a=x%2Fy&b=x%2Fy");
});

test("the Search buttons: the ready-made ones ticked, in their order, then one's own", () => {
  assert.deepEqual(fns.activeResources({on: ["uptodate", "clinicalkey"], own: [OWN]}, PRESETS)
                     .map(r => r.name), ["ClinicalKey", "UpToDate", "Example Platform"]);
  const els = fakePage();
  globalThis.MS = {resourcePresets: PRESETS};
  globalThis.libraryResources = {on: ["uptodate"], own: [OWN]};
  fns.renderResourceButtons();
  assert.deepEqual([...els.resourceButtons.innerHTML.matchAll(/<\/svg> ([^<]+)<\/button>/g)].map(m => m[1]),
                   ["Search UpToDate", "Search Example Platform"]);
});

test("a Search button opens the search through the library, in a MedSearch window", () => {
  fakePage({searchInput: "  glioma  "});
  const opened = [], toasts = [];
  Object.assign(globalThis, {MS: {resourcePresets: PRESETS}, libraryResources: {on: ["clinicalkey"], own: [OWN]},
    people: {author: null, institution: null}, closePanels() {}, fail: (m) => opened.push(["fail", m]),
    showToast: (m) => toasts.push(m), proxify: (u) => "PROXY:" + u,
    openInAppBrowser: (u, t) => opened.push([u, t])});
  fns.openLibraryResource(1);
  assert.deepEqual(opened, [["PROXY:https://example.org/find?words=glioma&x=1", "Example Platform"]]);
  globalThis.people = {author: {name: "Jane Doe"}, institution: null};
  fns.openLibraryResource(0);
  assert.match(toasts[0], /ClinicalKey can't be narrowed to an author or an institution/);
});

test("with nothing typed it says so and opens nothing", () => {
  fakePage({searchInput: " "});
  const said = [];
  Object.assign(globalThis, {MS: {resourcePresets: PRESETS}, libraryResources: {on: ["clinicalkey"], own: []},
    fail: (m, t) => said.push([m, t]), openInAppBrowser: () => said.push("opened")});
  fns.openLibraryResource(0);
  assert.deepEqual(said, [["Type what to look for in the search box, then open ClinicalKey.", "Nothing to search for"]]);
});

test("Settings: ticking, adding one's own, and refusing an address it can't use", () => {
  const els = fakePage({resourceName: " Example  Platform ", resourceUrl: OWN.url});
  const fails = [];
  Object.assign(globalThis, {MS: {resourcePresets: PRESETS}, fail: (m) => fails.push(m),
                             resourceDraft: {on: [], own: []}});
  fns.toggleResource("uptodate", true);
  fns.toggleResource("clinicalkey", true);
  fns.toggleResource("uptodate", false);
  assert.equal(fns.addOwnResource(), true);
  assert.deepEqual(globalThis.resourceDraft, {on: ["clinicalkey"], own: [{...OWN}]});
  assert.equal(els.resourceName.value, "");
  assert.match(els.resourceList.innerHTML, /Example Platform[\s\S]*https:\/\/example\.org\/find\?words=\{q\}&amp;x=1/);
  els.resourceName.value = "Other"; els.resourceUrl.value = "https://example.org/no-words";
  assert.equal(fns.addOwnResource(), false);
  assert.match(fails[0], /^Other: the search address needs \{q\}/);
  assert.equal(globalThis.resourceDraft.own.length, 1);
  els.resourceName.value = els.resourceUrl.value = "";
  assert.equal(fns.addOwnResource(), true);       // nothing typed: nothing to add
  fns.removeOwnResource(0);
  assert.deepEqual(globalThis.resourceDraft.own, []);
});

// Save, with the page around it faked: what it sends and what it refuses.
async function save(draft, typed) {
  const els = fakePage({...typed});
  const sent = [], fails = [];
  Object.assign(globalThis, {MS: {resourcePresets: PRESETS}, resourceDraft: draft, libraryResources: {on: [], own: []},
    _keysToClear: new Set(), institutionProxies: [], activeProxy: 0, savedProxies: [],
    buildInstitutions: () => [], renderProxyPicker() {}, refreshDbKeyBadges() {}, closeSettings() {},
    showToast() {}, fail: (m) => fails.push(m),
    fetch: async (url, opts) => { if (opts) sent.push(JSON.parse(opts.body)); return {json: async () => ({ok: true})}; }});
  document.getElementById("loginField").hidden = true;
  await fns.saveSettings();
  return {sent, fails, els};
}

test("Save sends the resources, and adds one typed but not yet added", async () => {
  const {sent, els} = await save({on: ["uptodate"], own: []},
                                 {resourceName: "Example Platform", resourceUrl: OWN.url});
  assert.deepEqual(sent[0].library_resources, {on: ["uptodate"], own: [OWN]});
  assert.deepEqual(globalThis.libraryResources, {on: ["uptodate"], own: [OWN]});
  assert.match(els.resourceButtons.innerHTML, /Search UpToDate[\s\S]*Search Example Platform/);
});

test("Save with a typed address it can't use saves nothing and says why", async () => {
  const {sent, fails} = await save({on: [], own: []}, {resourceName: "Example", resourceUrl: "https://example.org/x"});
  assert.deepEqual(sent, []);
  assert.match(fails[0], /needs \{q\}/);
});

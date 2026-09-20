// The page's own logic: escaping, the Markdown the AI answers in, the citation
// links, and the advanced-query detection.
//
//     node --test tests/js/*.test.js      (or just run the pytest suite)
//
// The one that matters most is renderMd: it is the only place where text from
// the model becomes HTML in the page.
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { escHtml, escAttr, renderMd, linkifyCites, detectPowerQuery } =
  load(["escHtml", "escAttr", "renderMd", "linkifyCites", "detectPowerQuery"]);

// ── Escaping ────────────────────────────────────────────────────────────────

test("escHtml neutralises every character that could open a tag", () => {
  assert.equal(escHtml(`<b>&"'`), "&lt;b&gt;&amp;&quot;&#39;");
  assert.equal(escHtml("<script>alert(1)</script>"),
    "&lt;script&gt;alert(1)&lt;/script&gt;");
});

test("escAttr survives a title that would close the handler's string", () => {
  // Article titles go into onclick="…('TITLE')" — a raw quote would end it.
  assert.equal(escAttr("it's"), "it\\'s");
  assert.equal(escAttr('a "quoted" title'), 'a &quot;quoted&quot; title');
  assert.equal(escAttr("back\\slash"), "back\\\\slash");
  assert.equal(escAttr("two\nlines"), "two lines");
});

// ── The Markdown the AI answers in ──────────────────────────────────────────

// Any `<` that does not open one of the tags the renderer itself writes.
const FOREIGN_TAG = /<(?!\/?(p|div|ul|ol|li|strong|em|code|pre|hr|span)\b)/;

test("no input produces a tag the renderer did not write itself", () => {
  const nasty = [
    '<img src=x onerror="alert(1)">',
    "<script>alert(1)</script>",
    "[link](javascript:alert(1))",
    "<div onclick=alert(1)>hi</div>",
    "**<b>bold</b>**",
    "`<i>code</i>`",
    "# <svg onload=alert(1)>",
    "- <iframe src=evil>",
  ];
  for (const s of nasty) {
    const out = renderMd(s);
    assert.ok(!FOREIGN_TAG.test(out), `escaped output expected for ${s}: ${out}`);
    // What was dangerous arrives as text: the angle brackets are entities.
    if (s.includes("<")) assert.match(out, /&lt;/);
  }
});

test("headings, lists, emphasis and code come through", () => {
  assert.equal(renderMd("# Title"), '<div class="md-h md-h1">Title</div>');
  assert.equal(renderMd("## 1. Methods"), '<div class="md-h md-h2">1. Methods</div>');
  assert.equal(renderMd("- a\n- b"), "<ul><li>a</li><li>b</li></ul>");
  assert.equal(renderMd("1. a\n2. b"), "<ol><li>a</li><li>b</li></ol>");
  assert.equal(renderMd("**bold** and *italic*"),
    "<p><strong>bold</strong> and <em>italic</em></p>");
  assert.equal(renderMd("use `term[tiab]`"), "<p>use <code>term[tiab]</code></p>");
  assert.equal(renderMd("---"), "<hr>");
});

test("a fenced block keeps its lines, for a query you copy", () => {
  assert.equal(renderMd("```\nglioma AND awake[tiab]\n```"),
    "<pre><code>glioma AND awake[tiab]</code></pre>");
  // An answer cut off mid-fence still closes.
  assert.equal(renderMd("```\nunfinished"), "<pre><code>unfinished</code></pre>");
});

test("multiplication is not read as emphasis", () => {
  assert.equal(renderMd("5 * 3 = 15 and 2 * 2"), "<p>5 * 3 = 15 and 2 * 2</p>");
  assert.equal(renderMd("**unclosed"), "<p>**unclosed</p>");
});

test("wrapped lines join into one paragraph, blank lines split them", () => {
  assert.equal(renderMd("one\ntwo\n\nthree"), "<p>one two</p><p>three</p>");
});

test("nothing in, nothing out", () => {
  for (const empty of ["", null, undefined, "   \n  "]) assert.equal(renderMd(empty), "");
});

// ── Citations in the assistant's answers ────────────────────────────────────

test("[n] becomes a link to that card, and only that", () => {
  const out = linkifyCites("Paper [2] says so.");
  assert.match(out, /<span class="cite-ref" onclick="jumpToCard\(1\)">\[2\]<\/span>/);
  assert.ok(!/jumpToCard/.test(linkifyCites("no citations here")));
});

test("a citation written by the model cannot smuggle markup", () => {
  const out = linkifyCites('[1] <img src=x onerror="alert(1)">');
  assert.ok(!FOREIGN_TAG.test(out), out);      // only our own <span> is added
  assert.match(out, /&lt;img/);
});

// ── Advanced query detection (mirrors the server's rule) ────────────────────

test("operators, field tags and phrases mean an advanced query", () => {
  for (const q of ["glioma AND awake", "a OR b", "a NOT b",
                   "awake[tiab]", 'an "exact phrase"']) {
    assert.equal(detectPowerQuery(q), true, q);
  }
});

test("ordinary words are not an advanced query", () => {
  for (const q of ["awake craniotomy glioma", "and or not", "brain mapping"]) {
    assert.equal(detectPowerQuery(q), false, q);
  }
});

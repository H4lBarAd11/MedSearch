// The AI provider: Anthropic directly, or OpenRouter in front of it. The page
// shows the key field of the provider in use and names it where the AI panel
// says whose key is needed.
//
//     node --test tests/js/*.test.js      (or just run the pytest suite)
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const fns = load(["renderAiProvider", "setAiProvider", "closeSettings"]);

// The page around it, faked: the provider toggle, the two key fields, the
// models, and the AI panel's words.
function fakePage() {
  const els = {};
  const buttons = [
    {dataset: {provider: "anthropic"}, classList: {toggle() {}}, setAttribute() {}},
    {dataset: {provider: "openrouter"}, classList: {toggle() {}}, setAttribute() {}},
  ];
  const doc = {
    getElementById: (id) => (els[id] ||= {id, hidden: false, textContent: ""}),
    querySelector: () => ({textContent: ""}),
    querySelectorAll: () => buttons,
  };
  globalThis.document = doc;
  return {els, buttons};
}

function setup(provider) {
  const page = fakePage();
  globalThis.MS = {aiProvider: provider};
  globalThis.AI_PROVIDERS = {anthropic: {label: "Anthropic"}, openrouter: {label: "OpenRouter"}};
  globalThis.aiProvider = provider;
  return page;
}

test("the provider in use is the one that came from the server", () => {
  setup("openrouter");
  fns.renderAiProvider();
  assert.equal(globalThis.aiProvider, "openrouter");
});

test("only the key field of the provider in use is shown", () => {
  const {els} = setup("anthropic");
  fns.renderAiProvider();
  assert.equal(els.anthropicKeyField.hidden, false);
  assert.equal(els.openrouterKeyField.hidden, true);
  assert.equal(els.openrouterModelField.hidden, true);
});

test("picking OpenRouter shows its key and its models", () => {
  const {els} = setup("anthropic");
  fns.setAiProvider("openrouter");
  assert.equal(globalThis.aiProvider, "openrouter");
  assert.equal(els.anthropicKeyField.hidden, true);
  assert.equal(els.openrouterKeyField.hidden, false);
  assert.equal(els.openrouterModelField.hidden, false);
});

test("a provider nobody knows is ignored", () => {
  setup("anthropic");
  fns.setAiProvider("not-a-provider");
  assert.equal(globalThis.aiProvider, "anthropic");
});

test("the AI panel says whose key it needs", () => {
  const {els} = setup("anthropic");
  fns.renderAiProvider();
  assert.match(els.aiKeyHint.textContent, /Anthropic/);
  fns.setAiProvider("openrouter");
  assert.match(els.aiKeyHint.textContent, /OpenRouter/);
});

test("leaving Settings without saving puts the old provider back", () => {
  setup("anthropic");
  globalThis._settingsSaved = false;
  globalThis._librariesBefore = null;
  globalThis._providerBefore = "anthropic";
  globalThis.renderProxyPicker = () => {};
  globalThis.closeOverlay = () => {};
  fns.setAiProvider("openrouter");
  fns.closeSettings();
  assert.equal(globalThis.aiProvider, "anthropic");
});

test("a saved provider stays the one that was saved", () => {
  setup("anthropic");
  globalThis._settingsSaved = true;
  globalThis._librariesBefore = null;
  globalThis._providerBefore = "anthropic";
  globalThis.renderProxyPicker = () => {};
  globalThis.closeOverlay = () => {};
  fns.setAiProvider("openrouter");
  fns.closeSettings();
  assert.equal(globalThis.aiProvider, "openrouter");
});

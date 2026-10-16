// Settings ▸ Uninstall MedSearch: asks first, in the danger colour, then asks
// MedSearch to go; a refusal is a popup saying why.
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { uninstallMedSearch } = load(["uninstallMedSearch"]);

function page(answer, reply) {
  const seen = {asked: null, posted: [], fails: [], toasts: []};
  Object.assign(globalThis, {
    MS: {onWindows: false},
    ask: async (o) => { seen.asked = o; return answer; },
    fetch: async (url, opts) => { seen.posted.push([url, opts.method]); return reply; },
    fail: (m, t) => seen.fails.push([m, t]),
    showToast: (m) => seen.toasts.push(m)});
  return seen;
}

test("it asks first, with the danger colour, and does nothing when cancelled", async () => {
  const seen = page(null, null);
  await uninstallMedSearch();
  assert.equal(seen.asked.danger, true);
  assert.equal(seen.asked.okLabel, "Move to Trash and quit");
  assert.match(seen.asked.text, /API keys and library sign-ins stay in the Keychain/);
  assert.deepEqual(seen.posted, []);
});

test("confirmed, it asks MedSearch to uninstall itself", async () => {
  const seen = page(true, {ok: true, status: 200, json: async () => ({ok: true})});
  await uninstallMedSearch();
  assert.deepEqual(seen.posted, [["/uninstall", "POST"]]);
  assert.deepEqual(seen.fails, []);
  assert.match(seen.toasts[0], /quitting; its files go to the Trash/);
});

test("a refusal says why, in a popup", async () => {
  const seen = page(true, {ok: false, status: 400, json: async () => ({ok: false, message: "Not here."})});
  await uninstallMedSearch();
  assert.deepEqual(seen.fails, [["Not here.", "Couldn't uninstall MedSearch"]]);
});

test("on Windows it names the Recycle Bin and Credential Manager", async () => {
  const seen = page(null, null);
  globalThis.MS.onWindows = true;
  await uninstallMedSearch();
  assert.equal(seen.asked.okLabel, "Move to the Recycle Bin and quit");
  assert.match(seen.asked.text, /stay in Credential Manager/);
});

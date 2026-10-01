// When the update check speaks. By itself (at launch, and each time the window
// comes back) it only ever offers an update, and not one put off today with
// "Later". Asked from Settings, it always answers.
//
//     node --test tests/js/*.test.js      (or just run the pytest suite)
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { updateVerdict } = load(["updateVerdict"]);

const newer = { ok: true, update_available: true, deferred: false };
const putOff = { ok: true, update_available: true, deferred: true };
const latest = { ok: true, update_available: false, deferred: false };
const offline = { ok: false, reason: "offline" };

test("a newer version is offered, by itself and from Settings", () => {
  assert.equal(updateVerdict(newer, false), "offer");
  assert.equal(updateVerdict(newer, true), "offer");
});

test("a version put off today is offered only from Settings", () => {
  assert.equal(updateVerdict(putOff, false), null);
  assert.equal(updateVerdict(putOff, true), "offer");
});

test("by itself the check says nothing when there is nothing to offer", () => {
  assert.equal(updateVerdict(latest, false), null);
  assert.equal(updateVerdict(offline, false), null);
  assert.equal(updateVerdict(null, false), null);
});

test("from Settings it says it is the latest, or that GitHub was out of reach", () => {
  assert.equal(updateVerdict(latest, true), "latest");
  assert.equal(updateVerdict(offline, true), "unreachable");
  assert.equal(updateVerdict(null, true), "unreachable");
});

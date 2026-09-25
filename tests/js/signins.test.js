// The sign-in domain Settings shows under "Remember sign-in". It must be the
// one signins.domain_of fills on, so both are checked against the same table
// (tests/signin_domains.json, also read by tests/test_signins.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { load } from "./load.mjs";

const { signinDomain } = load(["signinDomain"]);
const CASES = JSON.parse(readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "..", "signin_domains.json"), "utf8"));

test("Settings names the domain the sign-in is filled on", () => {
  for (const [url, domain] of CASES) assert.equal(signinDomain(url), domain, url);
});

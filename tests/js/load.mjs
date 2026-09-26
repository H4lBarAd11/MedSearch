// Loads the page's pure functions out of static/js/app.js so they can be
// tested in Node.
//
// app.js is a browser script: it runs on load, reads window.MS, and touches the
// document. Rather than faking a browser, this pulls the named functions out of
// the real file and evaluates those — so the tests run against the code that
// ships, not a copy of it.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const APP_JS = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "static", "js", "app.js");

/** The source of a top-level `[async] function name(...) { ... }`, braces balanced. */
function extract(src, name) {
  const start = src.search(new RegExp(`^(?:async\\s+)?function ${name}\\s*\\(`, "m"));
  if (start < 0) throw new Error(`function ${name} not found in app.js`);
  let i = src.indexOf("{", start), depth = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === "{") depth++;
    else if (src[j] === "}" && --depth === 0) return src.slice(start, j + 1);
  }
  throw new Error(`function ${name} is not balanced`);
}

export function load(names) {
  const src = readFileSync(APP_JS, "utf8");
  const body = names.map((n) => extract(src, n)).join("\n");
  // eslint-disable-next-line no-new-func
  return new Function(`${body}\nreturn {${names.join(",")}};`)();
}

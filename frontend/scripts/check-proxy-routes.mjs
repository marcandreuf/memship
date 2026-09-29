#!/usr/bin/env node
/**
 * Every client-side call must have a Next.js route handler in front of it.
 *
 * `apiClient` prefixes `/api`, so a call to `/receipts/1/credit-note` is served
 * by `app/api/receipts/[id]/credit-note/route.ts`. When that file is missing the
 * request never leaves the frontend: Next answers its own 404, the backend logs
 * nothing, and the feature is unreachable while every backend test still passes
 * because they call the API directly and never cross this layer.
 *
 * That is not hypothetical — it shipped three times. Credit notes were dead from
 * v2.8.0 through v2.14.0 (#326), and the remedy for a member locked out by
 * unconfigured email was dead from v2.12.0. Both were found by hand.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname.replace(/\/$/, "");
const API_DIR = join(ROOT, "app", "api");
const SEARCH_DIRS = ["features", "lib", "hooks", "components", "app"];
const CALL_RE = /apiClient(?:<[^>]*>)?\(\s*(["'`])/g;
const HOLE = "<expr>";

/**
 * Read the string literal starting at `open` and return it with every `${...}`
 * replaced by a placeholder.
 *
 * Hand-scanned rather than matched with a regex because the paths nest: an
 * expression may itself contain a template literal, as in
 * `/activities/${id}/registrations${qs ? `?${qs}` : ""}`. A regex stops at the
 * inner backtick and yields a truncated path, which then reads as an
 * uncovered call — noise that would have buried the two real findings.
 */
function readLiteral(text, open) {
  const quote = text[open];
  let out = "";
  for (let i = open + 1; i < text.length; i++) {
    const ch = text[i];
    if (ch === "\\") {
      out += text[i + 1] ?? "";
      i++;
    } else if (ch === quote) {
      return out;
    } else if (quote === "`" && ch === "$" && text[i + 1] === "{") {
      let depth = 1;
      i += 2;
      for (; i < text.length && depth > 0; i++) {
        if (text[i] === "{") depth++;
        else if (text[i] === "}") depth--;
        else if (text[i] === "`") {
          // Skip a nested template literal wholesale.
          for (i++; i < text.length && text[i] !== "`"; i++) {
            if (text[i] === "\\") i++;
          }
        }
      }
      i--;
      out += HOLE;
    } else {
      out += ch;
    }
  }
  return null;
}

/** `/reports/annual-summary${qs}` is the annual-summary route, not a wildcard. */
function toSegments(raw) {
  return raw
    .split("?")[0]
    .split("/")
    .filter(Boolean)
    .map((s) => {
      const literal = s.split(HOLE).join("");
      return literal === "" ? "*" : literal;
    });
}

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    if (name === "node_modules" || name === ".next") continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

/** Existing route handlers, as segment lists. */
const routes = walk(API_DIR)
  .filter((f) => f.endsWith("route.ts"))
  .map((f) =>
    relative(API_DIR, f)
      .split("/")
      .slice(0, -1)
      .filter(Boolean)
  );

/**
 * A `[param]` route segment matches any call segment. A literal route segment
 * matches only the identical literal.
 *
 * An interpolated call segment (`*`) must NOT match a literal route segment:
 * `${id}` resolves to an id at runtime and will never equal `by-stripe-session`.
 * Allowing it let that route falsely cover `/receipts/${id}/credit-note`, which
 * hid the very defect this check exists to catch.
 */
function isCovered(callSegs) {
  return routes.some(
    (routeSegs) =>
      routeSegs.length === callSegs.length &&
      routeSegs.every((r, i) =>
        r.startsWith("[") && r.endsWith("]") ? true : callSegs[i] === r
      )
  );
}

const calls = new Map();
for (const dir of SEARCH_DIRS) {
  for (const file of walk(join(ROOT, dir))) {
    if (!/\.tsx?$/.test(file)) continue;
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(CALL_RE)) {
      const raw = readLiteral(text, m.index + m[0].length - 1);
      if (raw === null) continue;
      const segs = toSegments(raw);
      if (!segs.length) continue;
      const key = segs.join("/");
      if (!calls.has(key)) calls.set(key, { segs, files: new Set() });
      calls.get(key).files.add(relative(ROOT, file));
    }
  }
}

const missing = [...calls.values()].filter((c) => !isCovered(c.segs));

if (missing.length) {
  console.error(
    `\ncheck-proxy-routes: ${missing.length} client call(s) have no route handler.\n`
  );
  for (const { segs, files } of missing) {
    console.error(`  /${segs.join("/")}`);
    console.error(`      expected: app/api/${segs.map((s) => (s === "*" ? "[id]" : s)).join("/")}/route.ts`);
    for (const f of [...files].sort()) console.error(`      called by: ${f}`);
  }
  console.error(
    "\nAdd the route handler, or remove the call if it is no longer used.\n"
  );
  process.exit(1);
}

console.log(`check-proxy-routes: ${calls.size} client call paths, all covered.`);

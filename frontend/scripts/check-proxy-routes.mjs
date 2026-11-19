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
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not `.pathname`: on Windows the latter is `/C:/...`, which
// readdirSync cannot open, and the check passed having read nothing at all.
const ROOT = fileURLToPath(new URL("..", import.meta.url)).replace(/[\\/]$/, "");
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

const METHOD_RE = /export async function (GET|POST|PUT|PATCH|DELETE)\b/g;

/** Existing route handlers, as segment lists plus the methods each exports. */
const routes = walk(API_DIR)
  .filter((f) => f.endsWith("route.ts"))
  .map((f) => ({
    segs: relative(API_DIR, f).split(sep).slice(0, -1).filter(Boolean),
    methods: new Set([...readFileSync(f, "utf8").matchAll(METHOD_RE)].map((m) => m[1])),
  }));

const isParam = (seg) => seg.startsWith("[") && seg.endsWith("]");

/**
 * The route handler Next.js will serve a call from, or undefined.
 *
 * A `[param]` route segment matches any call segment. A literal route segment
 * matches only the identical literal.
 *
 * An interpolated call segment (`*`) must NOT match a literal route segment:
 * `${id}` resolves to an id at runtime and will never equal `by-stripe-session`.
 * Allowing it let that route falsely cover `/receipts/${id}/credit-note`, which
 * hid the very defect this check exists to catch.
 *
 * Among several matches Next prefers a literal segment over a `[param]` one,
 * leftmost first, and that choice is final: it does not fall back to another
 * route when the one it picked lacks the method. So `/registrations/refunds`
 * with no `refunds/route.ts` lands on `registrations/[id]/route.ts`, which
 * exports only DELETE, and answers 405 (#591). Matching on the path alone
 * called that covered.
 */
function resolveRoute(callSegs) {
  const matches = routes.filter(
    ({ segs }) =>
      segs.length === callSegs.length &&
      segs.every((r, i) => isParam(r) || callSegs[i] === r)
  );
  const rank = ({ segs }) => segs.map((r) => (isParam(r) ? "1" : "0")).join("");
  return matches.sort((a, b) => rank(a).localeCompare(rank(b)))[0];
}

/** Skip past the string literal opening at `i`; returns the index of its close. */
function skipString(text, i) {
  const quote = text[i];
  for (i++; i < text.length && text[i] !== quote; i++) {
    if (text[i] === "\\") i++;
  }
  return i;
}

/**
 * The HTTP method of the `apiClient(` call whose `(` is at `open`: the
 * `method:` of its options, or GET when it passes none.
 */
function callMethod(text, open) {
  let depth = 0;
  for (let i = open; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"' || ch === "'" || ch === "`") i = skipString(text, i);
    else if (ch === "(") depth++;
    else if (ch === ")" && --depth === 0) {
      const m = text.slice(open, i).match(/method:\s*["'`](\w+)["'`]/);
      return m ? m[1].toUpperCase() : "GET";
    }
  }
  return "GET";
}

const calls = new Map();
for (const dir of SEARCH_DIRS) {
  for (const file of walk(join(ROOT, dir))) {
    if (!/\.tsx?$/.test(file)) continue;
    const text = readFileSync(file, "utf8");
    for (const m of text.matchAll(CALL_RE)) {
      const literalStart = m.index + m[0].length - 1;
      const raw = readLiteral(text, literalStart);
      if (raw === null) continue;
      const segs = toSegments(raw);
      if (!segs.length) continue;
      const method = callMethod(text, text.lastIndexOf("(", literalStart));
      const key = `${method} ${segs.join("/")}`;
      if (!calls.has(key)) calls.set(key, { segs, method, files: new Set() });
      calls.get(key).files.add(relative(ROOT, file).split(sep).join("/"));
    }
  }
}

const missing = [];
for (const call of calls.values()) {
  const route = resolveRoute(call.segs);
  if (!route) missing.push({ ...call, problem: "no route handler" });
  else if (!route.methods.has(call.method))
    missing.push({
      ...call,
      problem: `served by app/api/${route.segs.join("/")}/route.ts, which does not export ${call.method}`,
    });
}

if (missing.length) {
  console.error(
    `\ncheck-proxy-routes: ${missing.length} client call(s) cannot reach the API.\n`
  );
  for (const { segs, method, files, problem } of missing) {
    console.error(`  ${method} /${segs.join("/")} — ${problem}`);
    console.error(`      expected: app/api/${segs.map((s) => (s === "*" ? "[id]" : s)).join("/")}/route.ts exporting ${method}`);
    for (const f of [...files].sort()) console.error(`      called by: ${f}`);
  }
  console.error(
    "\nAdd the route handler or the method, or remove the call if it is no longer used.\n"
  );
  process.exit(1);
}

console.log(`check-proxy-routes: ${calls.size} client call paths, all covered.`);

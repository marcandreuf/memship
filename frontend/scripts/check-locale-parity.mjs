#!/usr/bin/env node
/**
 * Every locale must say the same things: es, ca and en hold the same files, the
 * same keys, and each message takes the same ICU arguments.
 *
 * Keys were kept at parity by hand and checked by eye. A key missing from one
 * locale renders as its raw path to exactly the members reading that language,
 * and nothing else fails: the build, the types and every test pass, because
 * next-intl resolves keys at runtime. An argument present in one translation
 * and not another is the same defect one level down — `{count}` in es and
 * `{total}` in ca throws on the Catalan screen alone.
 *
 * `es` is the reference only for the report's wording; a key present in ca or
 * en and missing from es is reported just the same.
 */

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not `.pathname`: on Windows the latter is `/C:/...`.
const ROOT = fileURLToPath(new URL("..", import.meta.url)).replace(/[\\/]$/, "");
// Overridable so the check's own tests can point it at fixtures.
const LOCALES_DIR = process.env.LOCALE_PARITY_DIR ?? join(ROOT, "locales");
const LOCALES = ["es", "ca", "en"];
const PLURAL_TYPES = new Set(["plural", "select", "selectordinal"]);

/** Leaf paths of a locale file, each with its message. */
function flatten(node, prefix = "", out = new Map()) {
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      flatten(value, path, out);
    } else {
      out.set(path, value);
    }
  }
  return out;
}

/**
 * The arguments an ICU message uses, name to type (`simple`, `plural`,
 * `select`…), nested plural and select branches included. Hand-parsed rather than matched with a regex, because a branch's
 * text sits in braces too (`one {# minuto}`) and must not read as an argument.
 *
 * Apostrophes follow ICU: one quotes only when it is followed by a brace or
 * another apostrophe, so Catalan prose ("l'import") is literal text.
 */
function icuArguments(message) {
  const args = new Map();
  let i = 0;

  function skipQuoted() {
    // At an apostrophe that starts quoting: skip to the closing one.
    i += 1;
    while (i < message.length && message[i] !== "'") i += 1;
    i += 1;
  }

  function text(stopAtClose) {
    while (i < message.length) {
      const c = message[i];
      if (c === "'" && /['{}]/.test(message[i + 1] ?? "")) {
        if (message[i + 1] === "'") i += 2;
        else skipQuoted();
      } else if (c === "{") {
        argument();
      } else if (c === "}") {
        if (stopAtClose) return;
        i += 1;
      } else {
        i += 1;
      }
    }
  }

  function readUntil(chars) {
    const start = i;
    while (i < message.length && !chars.includes(message[i])) i += 1;
    return message.slice(start, i).trim();
  }

  function argument() {
    i += 1; // past "{"
    const name = readUntil([",", "}"]);
    if (message[i] === "}") {
      if (name && !args.has(name)) args.set(name, "simple");
      i += 1;
      return;
    }
    i += 1; // past ","
    const type = readUntil([",", "}"]);
    if (name) args.set(name, type);
    if (message[i] === "}") {
      i += 1;
      return;
    }
    i += 1; // past ","
    if (!PLURAL_TYPES.has(type)) {
      // A number or date style: nothing in it names an argument.
      let depth = 1;
      while (i < message.length && depth > 0) {
        if (message[i] === "{") depth += 1;
        else if (message[i] === "}") depth -= 1;
        i += 1;
      }
      return;
    }
    // Branches: `selector {message}`, until the argument closes.
    while (i < message.length) {
      while (/\s/.test(message[i] ?? "")) i += 1;
      if (message[i] === "}") {
        i += 1;
        return;
      }
      readUntil(["{", "}"]);
      if (message[i] !== "{") continue;
      i += 1; // past the branch's "{"
      text(true);
      i += 1; // past the branch's "}"
    }
  }

  text(false);
  return args;
}

function load(locale, file) {
  return flatten(JSON.parse(readFileSync(join(LOCALES_DIR, locale, file), "utf8")));
}

const problems = [];
const filesByLocale = Object.fromEntries(
  LOCALES.map((l) => [l, new Set(readdirSync(join(LOCALES_DIR, l)).filter((f) => f.endsWith(".json")))])
);
const allFiles = new Set(LOCALES.flatMap((l) => [...filesByLocale[l]]));

let keyCount = 0;
for (const file of [...allFiles].sort()) {
  const missingIn = LOCALES.filter((l) => !filesByLocale[l].has(file));
  if (missingIn.length) {
    problems.push(`${file}: missing in ${missingIn.join(", ")}`);
    continue;
  }
  const messages = Object.fromEntries(LOCALES.map((l) => [l, load(l, file)]));
  const keys = new Set(LOCALES.flatMap((l) => [...messages[l].keys()]));
  keyCount += keys.size;
  for (const key of [...keys].sort()) {
    const absent = LOCALES.filter((l) => !messages[l].has(key));
    if (absent.length) {
      problems.push(`${file}: ${key} missing in ${absent.join(", ")}`);
      continue;
    }
    const kinds = new Set(LOCALES.map((l) => typeof messages[l].get(key)));
    if (kinds.size > 1) {
      problems.push(`${file}: ${key} is not the same kind of value in every locale`);
      continue;
    }
    if (!kinds.has("string")) continue;
    const args = Object.fromEntries(
      LOCALES.map((l) => [l, icuArguments(messages[l].get(key))])
    );
    // A translation may leave out a `select` its language has no use for:
    // English needs no grammatical gender to say "Welcome". Any other argument
    // one locale uses and another lacks is drift, or a quoting mistake that
    // turned it into literal text.
    const used = new Map();
    for (const l of LOCALES) for (const [name, type] of args[l]) used.set(name, type);
    const drift = LOCALES.some((l) =>
      [...used].some(([name, type]) => !args[l].has(name) && type !== "select")
    );
    if (drift) {
      const detail = LOCALES.map((l) => `${l} {${[...args[l].keys()].sort().join(", ")}}`).join(" · ");
      problems.push(`${file}: ${key} takes different arguments: ${detail}`);
    }
  }
}

if (problems.length) {
  console.error(`check-locale-parity: ${problems.length} problem(s)\n`);
  for (const p of problems) console.error(`  ${p}`);
  console.error(
    "\nEvery key goes into es, ca and en together, with the same {arguments} in each."
  );
  process.exit(1);
}
console.log(
  `check-locale-parity: ${allFiles.size} files, ${keyCount} keys, at parity in ${LOCALES.join(", ")}.`
);

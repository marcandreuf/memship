// The parity check's own tests: a check that passes on the real locales proves
// only that they are at parity today, not that it would notice when they stop
// being. Each case builds a small set of locales and runs the script on it.
//
//   node --test scripts/

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT = fileURLToPath(new URL("./check-locale-parity.mjs", import.meta.url));

/** Run the check on `{ es: {file: json}, ca: {...}, en: {...} }`. */
function check(locales) {
  const dir = mkdtempSync(join(tmpdir(), "locale-parity-"));
  try {
    for (const [locale, files] of Object.entries(locales)) {
      mkdirSync(join(dir, locale));
      for (const [file, json] of Object.entries(files)) {
        writeFileSync(join(dir, locale, file), JSON.stringify(json));
      }
    }
    const run = spawnSync(process.execPath, [SCRIPT], {
      env: { ...process.env, LOCALE_PARITY_DIR: dir },
      encoding: "utf8",
    });
    return { ok: run.status === 0, output: run.stdout + run.stderr };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const same = (json) => ({ es: { "a.json": json }, ca: { "a.json": json }, en: { "a.json": json } });

test("passes locales that say the same things", () => {
  assert.equal(check(same({ a: { b: "Hola {name}" } })).ok, true);
});

test("fails a key missing from one locale", () => {
  const result = check({
    es: { "a.json": { a: { b: "x", c: "y" } } },
    ca: { "a.json": { a: { b: "x" } } },
    en: { "a.json": { a: { b: "x", c: "y" } } },
  });
  assert.equal(result.ok, false);
  assert.match(result.output, /a\.c missing in ca/);
});

test("fails a key only a translation has", () => {
  const result = check({
    es: { "a.json": { a: "x" } },
    ca: { "a.json": { a: "x" } },
    en: { "a.json": { a: "x", extra: "y" } },
  });
  assert.equal(result.ok, false);
  assert.match(result.output, /extra missing in es, ca/);
});

test("fails a file missing from one locale", () => {
  const result = check({
    es: { "a.json": { a: "x" }, "b.json": { b: "y" } },
    ca: { "a.json": { a: "x" }, "b.json": { b: "y" } },
    en: { "a.json": { a: "x" } },
  });
  assert.equal(result.ok, false);
  assert.match(result.output, /b\.json: missing in en/);
});

test("fails a renamed argument", () => {
  const result = check({
    es: { "a.json": { a: "{count} reservas" } },
    ca: { "a.json": { a: "{count} reserves" } },
    en: { "a.json": { a: "{total} bookings" } },
  });
  assert.equal(result.ok, false);
  assert.match(result.output, /a takes different arguments/);
});

test("fails an argument an apostrophe has quoted into literal text", () => {
  // ICU reads '{status}' as the text "{status}": the argument is gone.
  const result = check({
    es: { "a.json": { a: "Estado «{status}»" } },
    ca: { "a.json": { a: "Estat «{status}»" } },
    en: { "a.json": { a: "Status '{status}'" } },
  });
  assert.equal(result.ok, false);
});

test("reads a Catalan apostrophe in prose as text", () => {
  const result = check({
    es: { "a.json": { a: "El importe {amount}" } },
    ca: { "a.json": { a: "L'import {amount}" } },
    en: { "a.json": { a: "The amount {amount}" } },
  });
  assert.equal(result.ok, true, result.output);
});

test("does not read a plural branch's text as an argument", () => {
  const result = check({
    es: { "a.json": { a: "{n, plural, =0 {Nada} one {Una} other {# cosas}}" } },
    ca: { "a.json": { a: "{n, plural, =0 {Res} one {Una} other {# coses}}" } },
    en: { "a.json": { a: "{n, plural, =0 {Nothing} one {One} other {# things}}" } },
  });
  assert.equal(result.ok, true, result.output);
});

test("finds an argument inside a plural branch", () => {
  const result = check({
    es: { "a.json": { a: "{n, plural, other {# de {total}}}" } },
    ca: { "a.json": { a: "{n, plural, other {# de {total}}}" } },
    en: { "a.json": { a: "{n, plural, other {# of all}}" } },
  });
  assert.equal(result.ok, false);
});

test("lets a language leave out a select it has no use for", () => {
  // English says "Welcome" whatever the gender.
  const result = check({
    es: { "a.json": { a: "{gender, select, female {Bienvenida} other {Bienvenido}}, {name}" } },
    ca: { "a.json": { a: "{gender, select, female {Benvinguda} other {Benvingut}}, {name}" } },
    en: { "a.json": { a: "Welcome, {name}" } },
  });
  assert.equal(result.ok, true, result.output);
});

test("fails a value that is text in one locale and a group in another", () => {
  const result = check({
    es: { "a.json": { a: "x" } },
    ca: { "a.json": { a: "x" } },
    en: { "a.json": { a: { b: "x" } } },
  });
  assert.equal(result.ok, false);
});

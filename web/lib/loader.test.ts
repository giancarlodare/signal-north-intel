// A test that the other tests actually RUN.
//
// WHY THIS EXISTS. `node --test` loads these files as ESM, where an
// extensionless relative import does not resolve. A test file that imports
// "./thing" instead of "./thing.ts" therefore fails to LOAD -- and a file that
// never loads reports no failures, so the suite looks green while the module
// it covers is untested.
//
// That is exactly the defect class the operator named: a monitor reporting
// success it has not verified is the same as a swallowed error. It bit us for
// real on 2026-08-02, when portal-routes.test.ts and subscription-state.test.ts
// (the paywall's own tests) had never executed once.
//
// So this file walks the suite and asserts every relative import carries its
// extension. It is a cheap, permanent answer to a failure mode that is
// otherwise invisible.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const LIB = dirname(fileURLToPath(import.meta.url));

function testFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...testFiles(full));
    else if (entry.endsWith(".test.ts")) out.push(full);
  }
  return out;
}

// Any relative specifier ("./x", "../y/z") in an import or export-from.
const RELATIVE = /\bfrom\s+["'](\.[^"']*)["']/g;

test("every relative import in the suite carries its .ts extension", () => {
  const offenders: string[] = [];
  for (const file of testFiles(LIB)) {
    const src = readFileSync(file, "utf8");
    for (const m of src.matchAll(RELATIVE)) {
      const spec = m[1];
      // `import type` is erased before Node sees it, so it is exempt. Match
      // the whole statement to tell the two apart.
      const stmt = src.slice(0, m.index).lastIndexOf("import");
      const isTypeOnly = /import\s+type\b/.test(src.slice(stmt, m.index));
      if (!isTypeOnly && !spec.endsWith(".ts")) {
        offenders.push(`${file.slice(LIB.length + 1)} -> ${spec}`);
      }
    }
  }
  assert.deepEqual(
    offenders,
    [],
    "these imports will not resolve, so the file silently never runs:\n" +
      offenders.join("\n"),
  );
});

test("the suite finds the files it is supposed to find", () => {
  // A floor, not an exact count: it catches a glob or path change that
  // quietly stops collecting tests, without breaking every time one is added.
  const found = testFiles(LIB).length;
  assert.ok(found >= 12, `only ${found} test files discovered under lib/`);
});

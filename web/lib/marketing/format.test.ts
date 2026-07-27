import { test } from "node:test";
import assert from "node:assert/strict";

import { formatCadCompact, formatCountFloor } from "./format.ts";

test("formatCadCompact: billions get one decimal", () => {
  assert.equal(formatCadCompact(4_120_000_000), "$4.1B");
});

test("formatCadCompact: millions round whole", () => {
  assert.equal(formatCadCompact(630_400_000), "$630M");
});

test("formatCadCompact: below a million renders exact-ish", () => {
  assert.equal(formatCadCompact(85_000), "$85,000");
});

test("formatCountFloor always undercounts, never overstates", () => {
  assert.equal(formatCountFloor(2961), "2,900+");
  assert.equal(formatCountFloor(1000), "1,000+");
  assert.equal(formatCountFloor(247), "240+");
  assert.equal(formatCountFloor(99), "99");
  assert.equal(formatCountFloor(0), "0");
});

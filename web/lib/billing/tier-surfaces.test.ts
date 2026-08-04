// The surface->tier matrix behind the ship-gate (operator 2026-08-04): the
// pricing table must never claim a distinction the product does not enforce.
// This pins the mapping the nav AND the RequireTier guard both read, so the
// two cannot disagree, and a drift from the pricing table fails here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { requiredTierFor, tierAllows, navShows } from "./tier-surfaces.ts";

test("the pricing table's Pro rows are Pro surfaces; the rest are Weekly", () => {
  assert.equal(requiredTierFor("/portal/closing-soon"), "pro");
  assert.equal(requiredTierFor("/portal/watching"), "pro");
  // subroutes inherit their parent's tier
  assert.equal(requiredTierFor("/portal/watching/edit"), "pro");
  // Weekly's product: the brief and saved items
  assert.equal(requiredTierFor("/portal/brief"), "weekly");
  assert.equal(requiredTierFor("/portal/saved"), "weekly");
  assert.equal(requiredTierFor("/portal"), "weekly");
  assert.equal(requiredTierFor("/portal/account"), "weekly");
});

test("a lookalike path does not inherit Pro", () => {
  assert.equal(requiredTierFor("/portal/watchingx"), "weekly");
  assert.equal(requiredTierFor("/portal/closing-soonest"), "weekly");
});

test("weekly opens Weekly surfaces and NOT Pro surfaces", () => {
  assert.equal(tierAllows("weekly", "/portal/brief"), true);
  assert.equal(tierAllows("weekly", "/portal/saved"), true);
  assert.equal(tierAllows("weekly", "/portal/closing-soon"), false);
  assert.equal(tierAllows("weekly", "/portal/watching"), false);
});

test("pro and founding open everything", () => {
  for (const tier of ["pro", "founding"] as const) {
    for (const p of ["/portal/brief", "/portal/saved", "/portal/closing-soon", "/portal/watching"]) {
      assert.equal(tierAllows(tier, p), true, `${tier} ${p}`);
    }
  }
});

test("nav: no tier shows Weekly-level items only; tiers match the guard", () => {
  assert.equal(navShows(null, "/portal/brief"), true);
  assert.equal(navShows(null, "/portal/closing-soon"), false);
  assert.equal(navShows("weekly", "/portal/watching"), false);
  assert.equal(navShows("pro", "/portal/watching"), true);
  assert.equal(navShows("founding", "/portal/closing-soon"), true);
});

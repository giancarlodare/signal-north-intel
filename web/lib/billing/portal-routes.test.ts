// The paywall's route split. Pinned by test because getting it wrong either
// locks a member out of checkout or gives away the product.
import { test } from "node:test";
import assert from "node:assert/strict";
import { isRelationshipPath, requiresSubscription } from "./portal-routes.ts";

test("the account page NEVER requires a subscription: it is where you buy one", () => {
  assert.equal(requiresSubscription("/portal/account"), false);
  assert.equal(isRelationshipPath("/portal/account"), true);
  // and any sub-route of it, so a future /portal/account/billing stays open
  assert.equal(requiresSubscription("/portal/account/billing"), false);
});

test("every product route requires a subscription", () => {
  for (const p of [
    "/portal",
    "/portal/brief",
    "/portal/closing-soon",
    "/portal/saved",
    "/portal/watching",
  ]) {
    assert.equal(requiresSubscription(p), true, p);
  }
});

test("a lookalike path does not sneak past the paywall", () => {
  // /portal/accounts is NOT /portal/account
  assert.equal(requiresSubscription("/portal/accounts"), true);
  assert.equal(requiresSubscription("/portal/account-x"), true);
});

test("non-portal paths are not this function's business", () => {
  for (const p of ["/", "/login", "/pricing", "/api/stripe/webhook", "/corpus"]) {
    assert.equal(requiresSubscription(p), false, p);
  }
});

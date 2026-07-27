import { test } from "node:test";
import assert from "node:assert/strict";

import { keyRefusalReason, tierForPrice } from "./config.ts";

test("test keys are always allowed", () => {
  assert.equal(keyRefusalReason("sk_test_abc", false), null);
  assert.equal(keyRefusalReason("rk_test_abc", false), null);
});

test("live key refused without the explicit approval flag", () => {
  const reason = keyRefusalReason("sk_live_abc", false);
  assert.ok(reason && reason.includes("live key refused"));
});

test("live key allowed only with the deliberate go-live flag", () => {
  assert.equal(keyRefusalReason("sk_live_abc", true), null);
});

test("missing key is refused", () => {
  assert.ok(keyRefusalReason(undefined, true));
});

const PRICES = { weekly: "price_w", pro: "price_p", founding: "price_f" };

test("tierForPrice maps ids back to tiers", () => {
  assert.equal(tierForPrice("price_f", PRICES), "founding");
  assert.equal(tierForPrice("price_w", PRICES), "weekly");
});

test("tierForPrice returns null for unknown or missing ids", () => {
  assert.equal(tierForPrice("price_x", PRICES), null);
  assert.equal(tierForPrice(null, PRICES), null);
  // An unset env price ("") must never match an empty price id.
  assert.equal(
    tierForPrice("", { weekly: "", pro: "price_p", founding: "" }),
    null,
  );
});

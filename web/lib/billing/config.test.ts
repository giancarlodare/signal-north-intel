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

const PRICES = {
  weekly: { annual: "price_wa", monthly: "price_wm" },
  pro: { annual: "price_pa", monthly: "price_pm" },
  founding: { annual: "price_fa", monthly: "" },
};

test("tierForPrice maps ids back to tier AND interval", () => {
  assert.deepEqual(tierForPrice("price_fa", PRICES), {
    tier: "founding",
    interval: "annual",
  });
  assert.deepEqual(tierForPrice("price_wa", PRICES), {
    tier: "weekly",
    interval: "annual",
  });
  assert.deepEqual(tierForPrice("price_wm", PRICES), {
    tier: "weekly",
    interval: "monthly",
  });
});

test("tierForPrice returns null for unknown or missing ids", () => {
  // An ad hoc Enterprise price, or a dashboard price nobody wired, must never
  // resolve to a tier the member did not buy.
  assert.equal(tierForPrice("price_adhoc_enterprise", PRICES), null);
  assert.equal(tierForPrice("price_x", PRICES), null);
  assert.equal(tierForPrice(null, PRICES), null);
});

test("an unset env price never matches an empty price id", () => {
  assert.equal(
    tierForPrice("", {
      weekly: { annual: "", monthly: "" },
      pro: { annual: "price_pa", monthly: "" },
      founding: { annual: "", monthly: "" },
    }),
    null,
  );
});

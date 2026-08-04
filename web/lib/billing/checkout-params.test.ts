// Locks the one invariant of our checkout ENTRY POINT that the webhook E2E can
// never see (it builds a session by hand): the anonymous checkout is created in
// SUBSCRIPTION mode. Payment mode would charge a Weekly buyer $3,900 once with
// no recurring billing, no subscription and no invoice -- a revenue bug. This
// runs on every push.
import { test } from "node:test";
import assert from "node:assert/strict";
import { anonymousCheckoutParams } from "./checkout-params.ts";

test("anonymous checkout is SUBSCRIPTION mode (recurring), never a one-time charge", () => {
  const p = anonymousCheckoutParams("price_weekly_annual", "https://x.test");
  assert.equal(p.mode, "subscription");
  assert.deepEqual(p.line_items, [{ price: "price_weekly_annual", quantity: 1 }]);
});

test("anonymous checkout returns to the thank-you page and cancels to pricing", () => {
  const p = anonymousCheckoutParams("price_x", "https://signalnorthintel.com");
  assert.equal(p.success_url, "https://signalnorthintel.com/join/thank-you?checkout=success");
  assert.equal(p.cancel_url, "https://signalnorthintel.com/pricing?checkout=cancelled");
  // No customer/customer_email prefilled: Checkout collects the anchor email.
  assert.equal("customer" in p, false);
  assert.equal("customer_email" in p, false);
});

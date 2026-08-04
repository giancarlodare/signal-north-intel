// The Checkout Session params for the anonymous (checkout-first) purchase,
// extracted as a PURE function (operator 2026-08-04).
//
// WHY THIS IS SEPARATE AND TESTED. The E2E validates the WEBHOOK by constructing
// a session + subscription by hand, so it could never catch a regression HERE --
// in how our own entry point creates the session. The one invariant that matters
// most is `mode: "subscription"`: in payment mode a Weekly buyer is charged
// $3,900 ONCE, with no recurring billing, no subscription object and no invoice,
// and nothing downstream can fire. That is a revenue bug a hand-built test would
// never see. checkout-params.test.ts asserts this on every push.
//
// No Stripe SDK VALUE import here (only the type, which is erased), so the unit
// test loads under `node --test` without pulling the SDK -- the same discipline
// as config.ts.
import type Stripe from "stripe";

export function anonymousCheckoutParams(
  price: string,
  origin: string,
): Stripe.Checkout.SessionCreateParams {
  return {
    mode: "subscription",
    line_items: [{ price, quantity: 1 }],
    // Checkout collects the payer's address; it becomes the provisioning anchor.
    billing_address_collection: "auto",
    success_url: `${origin}/join/thank-you?checkout=success`,
    cancel_url: `${origin}/pricing?checkout=cancelled`,
  };
}

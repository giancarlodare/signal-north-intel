#!/usr/bin/env node
// Archive the throwaway test product + its prices after the validation run.
// Runs with if: always() so create-side residue is cleaned even when the
// validation failed early. Stripe prices cannot be deleted, only archived
// (active:false); the product is archived too. Idempotent.
import Stripe from "stripe";

const key = process.env.STRIPE_SECRET_KEY || "";
if (!/^(sk|rk)_test_/.test(key)) process.exit(0); // nothing to do without a test key
const productId = process.env.CI_TEST_PRODUCT;
if (!productId) { console.log("no CI_TEST_PRODUCT; nothing to clean"); process.exit(0); }
const stripe = new Stripe(key);

let archived = 0;
for await (const price of stripe.prices.list({ product: productId, limit: 100 })) {
  if (price.active) { await stripe.prices.update(price.id, { active: false }); archived++; }
}
await stripe.products.update(productId, { active: false }).catch(() => {});
console.log(`archived product ${productId} and ${archived} prices`);

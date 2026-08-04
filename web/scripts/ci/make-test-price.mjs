#!/usr/bin/env node
// Create the throwaway TEST-MODE Stripe product + prices the checkout-flow
// validation runs against, and export their ids to $GITHUB_ENV so the server
// (started in a later step) maps them exactly as production would.
//
// Two mapped prices (weekly annual + monthly) go into STRIPE_PRICE_WEEKLY_*,
// which billingConfig reads, so the webhook resolves them to the weekly tier.
// One UNMAPPED price is created too and deliberately NOT put in the price env,
// so the validation can exercise the "price maps to no tier" failure branch.
//
// TEST MODE ONLY by construction: it refuses a non-test secret key, so this can
// never touch live money or live catalog.
import { appendFileSync } from "node:fs";
import Stripe from "stripe";

const key = process.env.STRIPE_SECRET_KEY || "";
if (!/^(sk|rk)_test_/.test(key)) {
  console.error("FATAL: STRIPE_SECRET_KEY is not a test key; refusing to run.");
  process.exit(2);
}
const tag = process.env.CI_RUN_TAG || "notag";
const stripe = new Stripe(key);

const product = await stripe.products.create({ name: `CI checkout-validate ${tag}` });
const mk = (amount, interval) =>
  stripe.prices.create({
    product: product.id,
    unit_amount: amount,
    currency: "cad",
    recurring: { interval },
  });
const annual = await mk(390000, "year");
const monthly = await mk(39000, "month");
const unmapped = await mk(100, "month");

const out =
  `STRIPE_PRICE_WEEKLY_ANNUAL=${annual.id}\n` +
  `STRIPE_PRICE_WEEKLY_MONTHLY=${monthly.id}\n` +
  `CI_UNMAPPED_PRICE=${unmapped.id}\n` +
  `CI_TEST_PRODUCT=${product.id}\n`;
if (process.env.GITHUB_ENV) appendFileSync(process.env.GITHUB_ENV, out);
console.log("created test product", product.id);
console.log(out.trim());

#!/usr/bin/env node
// Read the actual Stripe objects for a customer / payment intent and report
// them (operator 2026-08-04: read it, don't infer it), then clean up the
// test-mode residue (refund the charge, cancel any subscription, delete the
// customer). TEST MODE ONLY: refuses a non-test key.
//
// Usage: node inspect-stripe.mjs <cus_... | pi_... | sub_...>
import Stripe from "stripe";

const KEY = process.env.STRIPE_SECRET_KEY || "";
if (!/^(sk|rk)_test_/.test(KEY)) {
  console.error("FATAL: STRIPE_SECRET_KEY is not a test key; refusing to run.");
  process.exit(2);
}
const stripe = new Stripe(KEY);
const arg = (process.env.INSPECT_ARG || process.argv[2] || "").trim();
if (!arg) { console.error("usage: inspect-stripe.mjs <cus_/pi_/sub_ id>"); process.exit(2); }

let customerId = null;
let pinnedPi = null;
if (arg.startsWith("cus_")) customerId = arg;
else if (arg.startsWith("pi_")) {
  pinnedPi = await stripe.paymentIntents.retrieve(arg);
  customerId = typeof pinnedPi.customer === "string" ? pinnedPi.customer : pinnedPi.customer?.id ?? null;
} else if (arg.startsWith("sub_")) {
  const s = await stripe.subscriptions.retrieve(arg);
  customerId = typeof s.customer === "string" ? s.customer : s.customer?.id ?? null;
}
console.log(`ARG ${arg}  ->  customer ${customerId}`);
console.log("=".repeat(72));

// --- Checkout sessions for this customer (the question: what MODE?) ---------
const sessions = customerId
  ? (await stripe.checkout.sessions.list({ customer: customerId, limit: 10 })).data
  : [];
console.log(`CHECKOUT SESSIONS: ${sessions.length}`);
for (const s of sessions) {
  const full = await stripe.checkout.sessions.retrieve(s.id, { expand: ["line_items"] });
  console.log(`  ${full.id}`);
  console.log(`    mode=${full.mode}  status=${full.status}  payment_status=${full.payment_status}`);
  console.log(`    amount_total=${full.amount_total} ${full.currency}  subscription=${full.subscription}  payment_intent=${full.payment_intent}`);
  for (const li of full.line_items?.data ?? []) {
    console.log(`    line_item: price=${li.price?.id} type=${li.price?.type} recurring=${JSON.stringify(li.price?.recurring)} qty=${li.quantity}`);
  }
}
if (!sessions.length) {
  console.log("  (NO checkout session on this customer -- the payment did not go through Checkout)");
}

// --- Subscriptions / invoices / payment intents -----------------------------
const subs = customerId ? (await stripe.subscriptions.list({ customer: customerId, limit: 10 })).data : [];
console.log(`SUBSCRIPTIONS: ${subs.length}  ${subs.map((x) => `${x.id}(${x.status})`).join(", ")}`);

const invoices = customerId ? (await stripe.invoices.list({ customer: customerId, limit: 10 })).data : [];
console.log(`INVOICES: ${invoices.length}  ${invoices.map((i) => i.id).join(", ")}`);

const pis = pinnedPi
  ? [pinnedPi]
  : customerId ? (await stripe.paymentIntents.list({ customer: customerId, limit: 10 })).data : [];
console.log(`PAYMENT INTENTS: ${pis.length}`);
for (const pi of pis) {
  console.log(`  ${pi.id}: amount=${pi.amount} ${pi.currency} status=${pi.status} invoice=${pi.invoice} (invoice present => subscription/one-off distinction)`);
}

console.log("\nREAD:");
const sub = subs[0];
const sess = sessions[0];
if (sess?.mode === "subscription" || sub) {
  console.log("  A subscription-mode session and/or a subscription object exists: recurring billing is set up.");
} else if (sess?.mode === "payment") {
  console.log("  PAYMENT MODE: a one-time charge with NO subscription. Nothing downstream can fire. Revenue bug.");
} else if (!sess && pis.length) {
  console.log("  A charge exists but NO checkout session and NO subscription: the payment bypassed Checkout entirely.");
}

// --- Cleanup (refund, cancel, delete) ---------------------------------------
console.log("\n=== CLEANUP ===");
for (const pi of pis) {
  if (pi.status === "succeeded" && (pi.amount_received ?? pi.amount) > 0) {
    try {
      const r = await stripe.refunds.create({ payment_intent: pi.id });
      console.log(`  refunded ${pi.id} -> ${r.id} (${r.status})`);
    } catch (e) {
      console.log(`  refund ${pi.id} failed: ${e.message}`);
    }
  }
}
for (const s of subs) {
  try { await stripe.subscriptions.cancel(s.id); console.log(`  cancelled subscription ${s.id}`); }
  catch (e) { console.log(`  cancel ${s.id} failed: ${e.message}`); }
}
if (customerId) {
  try { await stripe.customers.del(customerId); console.log(`  deleted customer ${customerId}`); }
  catch (e) { console.log(`  delete customer failed: ${e.message}`); }
}
console.log("done");

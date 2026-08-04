#!/usr/bin/env node
// Remove ALL test residue for one email address, across Stripe test mode and
// Supabase, with VERIFIED removal (re-query + counts) -- the operator's
// standing rule: a test that leaves residue in the production auth table is
// worse than no test.
//
// Per email: Stripe customers matching the address (refund succeeded charges,
// cancel subscriptions, delete the customer), the Supabase auth user (cascade
// removes member_subscriptions), provisioning_failures rows (by email AND by
// each Stripe subscription id found), and any brief_signups row.
//
// TEST MODE ONLY: refuses a non-test Stripe key, so live objects are untouchable.
// PUBLIC LOGS: prints emails/ids/counts only, never tokens.
//
// Usage: cleanup-test-member.mjs <email> [email ...]
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const KEY = process.env.STRIPE_SECRET_KEY || "";
if (!/^(sk|rk)_test_/.test(KEY)) {
  console.error("FATAL: STRIPE_SECRET_KEY is not a test key; refusing to run.");
  process.exit(2);
}
const stripe = new Stripe(KEY);
const db = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY,
  { auth: { persistSession: false } },
);

const emails = process.argv.slice(2).map((e) => e.trim().toLowerCase()).filter(Boolean);
if (!emails.length) { console.error("usage: cleanup-test-member.mjs <email> [...]"); process.exit(2); }

async function findUser(email) {
  let page = 1;
  for (;;) {
    const { data, error } = await db.auth.admin.listUsers({ page, perPage: 200 });
    if (error) throw new Error(error.message);
    const users = data?.users ?? [];
    const hit = users.find((u) => (u.email || "").toLowerCase() === email);
    if (hit) return hit;
    if (users.length < 200 || page >= 25) return null;
    page++;
  }
}

let totalResidual = 0;
for (const email of emails) {
  console.log(`\n==== ${email} ====`);
  const report = {};

  // --- Stripe -----------------------------------------------------------
  const custs = (await stripe.customers.list({ email, limit: 100 })).data;
  const subIds = [];
  let refunds = 0, cancels = 0, custDeletes = 0;
  for (const c of custs) {
    for (const s of (await stripe.subscriptions.list({ customer: c.id, status: "all", limit: 100 })).data) {
      subIds.push(s.id);
      if (!["canceled", "incomplete_expired"].includes(s.status)) {
        try { await stripe.subscriptions.cancel(s.id); cancels++; } catch (e) { console.log(`  cancel ${s.id}: ${e.message}`); }
      }
    }
    for (const pi of (await stripe.paymentIntents.list({ customer: c.id, limit: 100 })).data) {
      if (pi.status === "succeeded" && (pi.amount_received ?? pi.amount) > 0) {
        try { const r = await stripe.refunds.create({ payment_intent: pi.id }); refunds++; console.log(`  refunded ${pi.id} -> ${r.id}`); }
        catch (e) { console.log(`  refund ${pi.id}: ${e.message}`); }
      }
    }
    try { await stripe.customers.del(c.id); custDeletes++; } catch (e) { console.log(`  delete ${c.id}: ${e.message}`); }
  }
  const custResidual = (await stripe.customers.list({ email, limit: 100 })).data.length;
  report.stripe = { customers: custs.length, subsCancelled: cancels, refunds, custDeletes, custResidual };

  // --- Supabase user (cascade removes member_subscriptions) ---------------
  const user = await findUser(email);
  let userRemoved = 0, userResidual = 0, hadSub = 0;
  if (user) {
    const { count } = await db.from("member_subscriptions")
      .select("member_id", { count: "exact", head: true }).eq("member_id", user.id);
    hadSub = count || 0;
    await db.auth.admin.deleteUser(user.id).catch((e) => console.log(`  deleteUser: ${e.message}`));
    const { data: still } = await db.auth.admin.getUserById(user.id);
    if (still?.user) userResidual = 1; else userRemoved = 1;
  }
  // member_subscriptions residue by any Stripe sub id (belt and suspenders)
  let subRowResidual = 0;
  for (const id of subIds) {
    const { count } = await db.from("member_subscriptions")
      .select("member_id", { count: "exact", head: true }).eq("stripe_subscription_id", id);
    subRowResidual += count || 0;
  }
  report.user = { found: user ? 1 : 0, hadSubscriptionRow: hadSub, removed: userRemoved, residual: userResidual, subRowResidual };

  // --- provisioning_failures (by email and by each sub id) ----------------
  const { count: pfBefore } = await db.from("provisioning_failures")
    .select("id", { count: "exact", head: true }).eq("email", email);
  await db.from("provisioning_failures").delete().eq("email", email);
  for (const id of subIds) await db.from("provisioning_failures").delete().eq("stripe_subscription_id", id);
  const { count: pfAfter } = await db.from("provisioning_failures")
    .select("id", { count: "exact", head: true }).eq("email", email);
  report.failures = { found: pfBefore || 0, residual: pfAfter || 0 };

  // --- brief_signups ------------------------------------------------------
  const { count: bsBefore } = await db.from("brief_signups")
    .select("id", { count: "exact", head: true }).eq("email", email);
  await db.from("brief_signups").delete().eq("email", email);
  const { count: bsAfter } = await db.from("brief_signups")
    .select("id", { count: "exact", head: true }).eq("email", email);
  report.freeList = { found: bsBefore || 0, residual: bsAfter || 0 };

  const residual = report.stripe.custResidual + report.user.residual +
    report.user.subRowResidual + report.failures.residual + report.freeList.residual;
  totalResidual += residual;

  console.log(`  stripe: ${report.stripe.customers} customer(s), ${cancels} sub(s) cancelled, ${refunds} refund(s), ${custDeletes} deleted, residual ${report.stripe.custResidual}`);
  console.log(`  auth user: found ${report.user.found}, had sub row ${hadSub}, removed ${userRemoved}, RESIDUAL ${userResidual}; sub-row residual ${subRowResidual}`);
  console.log(`  provisioning_failures: found ${report.failures.found}, residual ${report.failures.residual}`);
  console.log(`  brief_signups: found ${report.freeList.found}, residual ${report.freeList.residual}`);
  console.log(`  RESIDUAL for ${email}: ${residual}`);
}

console.log(`\nTOTAL RESIDUAL ACROSS ALL ADDRESSES: ${totalResidual}`);
process.exit(totalResidual === 0 ? 0 : 1);

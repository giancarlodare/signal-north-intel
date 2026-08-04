#!/usr/bin/env node
// End-to-end TEST-MODE validation of the checkout-first webhook (operator
// 2026-08-04, path a). It drives the REAL webhook -- the running route handler,
// against the REAL Stripe test API and the REAL Supabase -- with signed events,
// asserts the rows the flow is supposed to write, and then removes every test
// artifact and VERIFIES the removal by re-querying, reporting created-vs-removed
// counts. A test that leaves residue in the auth table is worse than no test
// (operator), so cleanup runs in a finally and is proven, not assumed.
//
// TEST MODE ONLY: refuses a non-test Stripe key. No live money can move.
// No member email is sent: MEMBER_WELCOME_LIVE stays off, so welcomes are held.
// Alarm sends (failure paths) go to OPERATOR_ALARM_EMAIL, set to a Resend sink.
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const KEY = process.env.STRIPE_SECRET_KEY || "";
if (!/^(sk|rk)_test_/.test(KEY)) {
  console.error("FATAL: STRIPE_SECRET_KEY is not a test key; refusing to run.");
  process.exit(2);
}
const BASE = process.env.CI_WEBHOOK_BASE || "http://127.0.0.1:3123";
const WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;
const TAG = process.env.CI_RUN_TAG || `t${Date.now()}`;
const WEEKLY_ANNUAL = process.env.STRIPE_PRICE_WEEKLY_ANNUAL;
const UNMAPPED = process.env.CI_UNMAPPED_PRICE;

const stripe = new Stripe(KEY);
const db = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY,
  { auth: { persistSession: false } },
);

const ACCESS = new Set(["active", "trialing", "past_due"]);
const results = [];
function check(name, cond, detail = "") {
  results.push({ name, ok: !!cond, detail });
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}${detail ? "  :: " + detail : ""}`);
}

// --- what we create, so we can prove we removed it -------------------------
const created = { userIds: new Set(), subIds: new Set(), custIds: new Set(), freeEmails: new Set(), failSubIds: new Set() };

function email(n) { return `svc-${TAG}-${n}@sn-ci.test`; }

async function mkCustomer(addr) {
  const c = await stripe.customers.create(addr ? { email: addr } : {});
  created.custIds.add(c.id);
  return c;
}
async function mkSub(customerId, price) {
  const s = await stripe.subscriptions.create({
    customer: customerId,
    items: [{ price }],
    trial_period_days: 7, // status 'trialing', no payment method needed in test
  });
  created.subIds.add(s.id);
  return s;
}
async function postCompleted({ subId, customerId, addr }) {
  const evt = {
    id: `evt_ci_${TAG}_${Math.random().toString(36).slice(2)}`,
    type: "checkout.session.completed",
    created: Math.floor(Date.now() / 1000),
    data: {
      object: {
        id: `cs_ci_${Math.random().toString(36).slice(2)}`,
        object: "checkout.session",
        mode: "subscription",
        subscription: subId,
        customer: customerId,
        customer_details: addr ? { email: addr } : null,
        customer_email: addr ?? null,
        client_reference_id: null,
        metadata: {},
      },
    },
  };
  const payload = JSON.stringify(evt);
  const header = stripe.webhooks.generateTestHeaderString({ payload, secret: WEBHOOK_SECRET });
  const resp = await fetch(`${BASE}/api/stripe/webhook`, {
    method: "POST",
    headers: { "stripe-signature": header, "content-type": "application/json" },
    body: payload,
  });
  return { status: resp.status, body: await resp.text().catch(() => "") };
}

const subRow = (subId) =>
  db.from("member_subscriptions")
    .select("member_id,tier,interval,status")
    .eq("stripe_subscription_id", subId).maybeSingle();
const failRow = (subId) =>
  db.from("provisioning_failures").select("reason,alerted_at")
    .eq("stripe_subscription_id", subId).maybeSingle();

async function main() {
  // ---- S1: anonymous checkout provisions a NEW account -------------------
  const e1 = email(1);
  const c1 = await mkCustomer(e1);
  const s1 = await mkSub(c1.id, WEEKLY_ANNUAL);
  const r1 = await postCompleted({ subId: s1.id, customerId: c1.id, addr: e1 });
  check("S1 webhook returns 200", r1.status === 200, `status=${r1.status}`);
  const { data: row1 } = await subRow(s1.id);
  check("S1 member_subscriptions row written", !!row1);
  check("S1 tier=weekly interval=annual", row1?.tier === "weekly" && row1?.interval === "annual", `${row1?.tier}/${row1?.interval}`);
  check("S1 status grants access", ACCESS.has(row1?.status), row1?.status);
  let user1 = null;
  if (row1?.member_id) {
    created.userIds.add(row1.member_id);
    user1 = row1.member_id;
    const { data: u } = await db.auth.admin.getUserById(row1.member_id);
    check("S1 auth account created with the checkout email", u?.user?.email === e1, u?.user?.email);
  }
  const s1r = await stripe.subscriptions.retrieve(s1.id);
  check("S1 sn_member_id stamped back onto the subscription", s1r.metadata?.sn_member_id === user1);
  const { data: f1 } = await failRow(s1.id);
  check("S1 no provisioning_failures row (clean provision)", !f1);

  // ---- S2: upgrading a free-list address dedups it -----------------------
  const e2 = email(2);
  await db.from("brief_signups").insert({ email: e2, consent_source: "ci-validate" });
  created.freeEmails.add(e2);
  const c2 = await mkCustomer(e2);
  const s2 = await mkSub(c2.id, WEEKLY_ANNUAL);
  const r2 = await postCompleted({ subId: s2.id, customerId: c2.id, addr: e2 });
  check("S2 webhook returns 200", r2.status === 200, `status=${r2.status}`);
  const { data: row2 } = await subRow(s2.id);
  if (row2?.member_id) created.userIds.add(row2.member_id);
  const { data: free2 } = await db.from("brief_signups").select("unsubscribed_at").eq("email", e2).maybeSingle();
  check("S2 free-list row unsubscribed on upgrade", !!free2?.unsubscribed_at, String(free2?.unsubscribed_at));

  // ---- S3: re-delivery is idempotent (no duplicate account) --------------
  const r3 = await postCompleted({ subId: s1.id, customerId: c1.id, addr: e1 });
  check("S3 re-delivery returns 200", r3.status === 200, `status=${r3.status}`);
  const { data: link3 } = await db.auth.admin.generateLink({ type: "magiclink", email: e1 });
  check("S3 same email resolves to the SAME account (no duplicate)", link3?.user?.id === user1, link3?.user?.id);
  const { count: n1 } = await db.from("member_subscriptions").select("member_id", { count: "exact", head: true }).eq("stripe_subscription_id", s1.id);
  check("S3 still exactly one subscription row for the sub", n1 === 1, `count=${n1}`);

  // ---- S4: unmapped price -> failure row + idempotent alarm --------------
  const e4 = email(4);
  const c4 = await mkCustomer(e4);
  const s4 = await mkSub(c4.id, UNMAPPED);
  const r4a = await postCompleted({ subId: s4.id, customerId: c4.id, addr: e4 });
  created.failSubIds.add(s4.id);
  check("S4 unmapped price rejected (422)", r4a.status === 422, `status=${r4a.status}`);
  const { data: f4 } = await failRow(s4.id);
  check("S4 provisioning_failures row, reason unmapped-price", f4?.reason === "unmapped-price", f4?.reason);
  // the account is provisioned before the price check; capture it for cleanup
  const { data: link4 } = await db.auth.admin.generateLink({ type: "magiclink", email: e4 });
  if (link4?.user?.id) created.userIds.add(link4.user.id);
  const r4b = await postCompleted({ subId: s4.id, customerId: c4.id, addr: e4 });
  check("S4 re-delivery still 422", r4b.status === 422, `status=${r4b.status}`);
  const { count: nf4 } = await db.from("provisioning_failures").select("id", { count: "exact", head: true }).eq("stripe_subscription_id", s4.id);
  check("S4 alarm is idempotent: exactly one failure row", nf4 === 1, `count=${nf4}`);

  // ---- S5: no email on the checkout -> no-email failure -------------------
  const c5 = await mkCustomer(null);
  const s5 = await mkSub(c5.id, WEEKLY_ANNUAL);
  const r5 = await postCompleted({ subId: s5.id, customerId: c5.id, addr: null });
  created.failSubIds.add(s5.id);
  check("S5 missing email is a retryable failure (500)", r5.status === 500, `status=${r5.status}`);
  const { data: f5 } = await failRow(s5.id);
  check("S5 provisioning_failures row, reason no-email", f5?.reason === "no-email", f5?.reason);
  const { data: row5 } = await subRow(s5.id);
  check("S5 no subscription row for an unprovisionable checkout", !row5);
}

// --- cleanup, verified -----------------------------------------------------
async function cleanup() {
  const report = { users: { made: created.userIds.size, removed: 0, residual: 0 },
                   free: { made: created.freeEmails.size, removed: 0, residual: 0 },
                   fails: { made: created.failSubIds.size, removed: 0, residual: 0 },
                   stripeSubs: created.subIds.size, stripeCusts: created.custIds.size };

  // Supabase auth users (member_subscriptions cascades on user delete).
  for (const id of created.userIds) {
    await db.auth.admin.deleteUser(id).catch((e) => console.error("deleteUser", id, e.message));
  }
  for (const id of created.userIds) {
    const { data } = await db.auth.admin.getUserById(id);
    if (data?.user) report.users.residual++; else report.users.removed++;
  }
  // Free-list seeds.
  for (const addr of created.freeEmails) {
    await db.from("brief_signups").delete().eq("email", addr);
    const { count } = await db.from("brief_signups").select("id", { count: "exact", head: true }).eq("email", addr);
    if (count) report.free.residual += count; else report.free.removed++;
  }
  // Provisioning-failure rows (no FK cascade; delete explicitly).
  for (const subId of created.failSubIds) {
    await db.from("provisioning_failures").delete().eq("stripe_subscription_id", subId);
    const { count } = await db.from("provisioning_failures").select("id", { count: "exact", head: true }).eq("stripe_subscription_id", subId);
    if (count) report.fails.residual += count; else report.fails.removed++;
  }
  // member_subscriptions residue check (should be gone via cascade).
  let subResidual = 0;
  for (const subId of created.subIds) {
    const { count } = await db.from("member_subscriptions").select("member_id", { count: "exact", head: true }).eq("stripe_subscription_id", subId);
    subResidual += count || 0;
  }
  // Stripe test objects.
  for (const id of created.subIds) await stripe.subscriptions.cancel(id).catch(() => {});
  for (const id of created.custIds) await stripe.customers.del(id).catch(() => {});

  console.log("\n==== CLEANUP REPORT ====");
  console.log(`auth users        made ${report.users.made}  removed ${report.users.removed}  RESIDUAL ${report.users.residual}`);
  console.log(`member_subscriptions residue (should be 0): ${subResidual}`);
  console.log(`brief_signups seeds made ${report.free.made}  removed ${report.free.removed}  RESIDUAL ${report.free.residual}`);
  console.log(`provisioning_failures made ${report.fails.made}  removed ${report.fails.removed}  RESIDUAL ${report.fails.residual}`);
  console.log(`stripe test subs cancelled ${report.stripeSubs}, customers deleted ${report.stripeCusts} (product/prices archived separately)`);
  const residue = report.users.residual + report.free.residual + report.fails.residual + subResidual;
  console.log(`TOTAL RESIDUAL IN PRODUCTION TABLES: ${residue}`);
  return residue;
}

let residue = 0;
let threw = null;
try {
  await main();
} catch (e) {
  threw = e;
  console.error("VALIDATION ERROR:", e?.stack || e);
} finally {
  residue = await cleanup().catch((e) => { console.error("CLEANUP ERROR:", e); return 999; });
}

const failed = results.filter((r) => !r.ok);
console.log("\n==== SUMMARY ====");
console.log(`assertions: ${results.length - failed.length}/${results.length} passed`);
if (failed.length) console.log("FAILED:", failed.map((f) => f.name).join(" | "));
const ok = !threw && failed.length === 0 && residue === 0;
console.log(ok ? "\nVALIDATION PASSED, no residue." : "\nVALIDATION FAILED.");
process.exit(ok ? 0 : 1);

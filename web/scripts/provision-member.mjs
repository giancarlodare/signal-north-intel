#!/usr/bin/env node
// Manual provision command (operator 2026-08-03, change A). The reconciliation
// alarm points here: it turns a PAID Stripe subscription into a working account
// by hand, for the case where the webhook could not (and Stripe's retries did
// not) do it automatically.
//
// It does exactly what the webhook's provision path does, so it is idempotent
// and safe to run even if Stripe has since succeeded: it finds-or-creates the
// account, grants the subscription, dedups the free list, sends the welcome,
// and resolves the provisioning_failures row.
//
// USAGE:
//   node web/scripts/provision-member.mjs <sub_id | email>
//
// ENV (the same secrets the webhook uses; run where they are available):
//   STRIPE_SECRET_KEY, NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
//   NEXT_PUBLIC_SITE_URL, RESEND_API_KEY (optional; welcome is skipped without
//   it), MEMBER_EMAIL_SENDER (optional).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";

const HERE = dirname(fileURLToPath(import.meta.url));
const EMAILS = join(HERE, "..", "emails");

function need(name) {
  const v = process.env[name];
  if (!v) {
    console.error(`FATAL: ${name} is not set.`);
    process.exit(2);
  }
  return v;
}

function tierForPrice(priceId) {
  const map = {
    [process.env.STRIPE_PRICE_WEEKLY_ANNUAL || "\0"]: ["weekly", "annual"],
    [process.env.STRIPE_PRICE_WEEKLY_MONTHLY || "\0"]: ["weekly", "monthly"],
    [process.env.STRIPE_PRICE_PRO_ANNUAL || "\0"]: ["pro", "annual"],
    [process.env.STRIPE_PRICE_PRO_MONTHLY || "\0"]: ["pro", "monthly"],
    [process.env.STRIPE_PRICE_FOUNDING_ANNUAL || "\0"]: ["founding", "annual"],
  };
  return map[priceId] || null;
}

function firstBriefDateLabel(purchasedAt) {
  const day = purchasedAt.getUTCDay();
  let delta = (1 - day + 7) % 7;
  if (delta === 0) delta = 7;
  const monday = new Date(Date.UTC(
    purchasedAt.getUTCFullYear(), purchasedAt.getUTCMonth(), purchasedAt.getUTCDate() + delta));
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Toronto", month: "long", day: "numeric",
  }).format(monday);
}

async function sendWelcome({ email, signInLink, firstBriefDate, sender }) {
  const key = process.env.RESEND_API_KEY;
  if (!key) {
    console.warn("  RESEND_API_KEY absent; welcome NOT sent. Sign-in link:");
    console.warn("  " + signInLink);
    return false;
  }
  const fill = (s) => s
    .split("{{signin_url}}").join(signInLink)
    .split("{{first_brief_date}}").join(firstBriefDate);
  const html = fill(readFileSync(join(EMAILS, "03-member-welcome.html"), "utf8"));
  const text = fill(readFileSync(join(EMAILS, "03-member-welcome.txt"), "utf8"));
  const resp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({
      from: sender, to: [email],
      subject: "Your Signal North membership is active", html, text,
    }),
  });
  if (!resp.ok) {
    console.error("  welcome send FAILED:", resp.status, (await resp.text()).slice(0, 200));
    return false;
  }
  console.log("  welcome sent to", email);
  return true;
}

async function main() {
  const arg = process.argv[2];
  if (!arg) {
    console.error("usage: node web/scripts/provision-member.mjs <sub_id | email>");
    process.exit(2);
  }
  const stripe = new Stripe(need("STRIPE_SECRET_KEY"));
  const db = createClient(need("NEXT_PUBLIC_SUPABASE_URL"), need("SUPABASE_SERVICE_ROLE_KEY"), {
    auth: { persistSession: false },
  });
  const origin = (process.env.NEXT_PUBLIC_SITE_URL || "").trim().replace(/\/+$/, "");
  if (!origin) { console.error("FATAL: NEXT_PUBLIC_SITE_URL is not set."); process.exit(2); }
  const sender = process.env.MEMBER_EMAIL_SENDER || "Signal North <signal@signalnorthintel.com>";

  // Resolve the subscription from a sub_ id, or from an email via its customer.
  let sub;
  if (arg.startsWith("sub_")) {
    sub = await stripe.subscriptions.retrieve(arg);
  } else if (arg.includes("@")) {
    const custs = await stripe.customers.list({ email: arg.trim().toLowerCase(), limit: 1 });
    const cust = custs.data[0];
    if (!cust) { console.error("No Stripe customer for", arg); process.exit(1); }
    const subs = await stripe.subscriptions.list({ customer: cust.id, limit: 1 });
    sub = subs.data[0];
    if (!sub) { console.error("Customer", cust.id, "has no subscription"); process.exit(1); }
  } else {
    console.error("Argument must be a sub_ id or an email."); process.exit(2);
  }

  console.log("Provisioning subscription", sub.id, "status", sub.status);
  const priceId = sub.items.data[0]?.price?.id ?? null;
  const mapped = tierForPrice(priceId);
  if (!mapped) { console.error("Price", priceId, "maps to no configured tier."); process.exit(1); }
  const [tier, interval] = mapped;

  const custId = typeof sub.customer === "string" ? sub.customer : sub.customer?.id;
  const cust = custId ? await stripe.customers.retrieve(custId) : null;
  const email = (cust && !cust.deleted ? cust.email : null)?.trim().toLowerCase();
  if (!email) { console.error("No email on the customer; cannot provision."); process.exit(1); }

  const { data, error } = await db.auth.admin.generateLink({
    type: "magiclink", email,
    options: { redirectTo: `${origin}/auth/confirm?next=${encodeURIComponent("/portal/brief")}` },
  });
  if (error || !data?.user?.id) { console.error("generateLink failed:", error?.message); process.exit(1); }
  const memberId = data.user.id;
  const hashed = data.properties?.hashed_token ?? "";
  const signInLink = hashed
    ? `${origin}/auth/confirm?token_hash=${hashed}&type=magiclink&next=${encodeURIComponent("/portal/brief")}`
    : `${origin}/login`;
  console.log("  member", memberId, email);

  await stripe.subscriptions.update(sub.id, { metadata: { sn_member_id: memberId } });
  if (custId) await stripe.customers.update(custId, { metadata: { sn_member_id: memberId } });

  const periodEnd = sub.items.data[0]?.current_period_end;
  const { error: upErr } = await db.from("member_subscriptions").upsert({
    member_id: memberId,
    stripe_customer_id: custId ?? null,
    stripe_subscription_id: sub.id,
    tier, interval, status: sub.status,
    current_period_end: periodEnd ? new Date(periodEnd * 1000).toISOString() : null,
    event_created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }, { onConflict: "member_id" });
  if (upErr) { console.error("member_subscriptions upsert failed:", upErr.message); process.exit(1); }
  console.log("  entitlement written:", tier, interval, sub.status);

  await db.from("brief_signups").update({ unsubscribed_at: new Date().toISOString() })
    .eq("email", email).is("unsubscribed_at", null);

  await sendWelcome({
    email, signInLink,
    firstBriefDate: firstBriefDateLabel(new Date((sub.created ?? Date.now() / 1000) * 1000)),
    sender,
  });

  await db.from("provisioning_failures")
    .update({ resolved_at: new Date().toISOString(), resolved_by: "manual" })
    .eq("stripe_subscription_id", sub.id).is("resolved_at", null);

  console.log("Done. Subscription", sub.id, "provisioned to", email);
}

main().catch((e) => { console.error("FATAL:", e); process.exit(1); });

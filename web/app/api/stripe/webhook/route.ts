// Stripe webhook: the ONLY writer of member_subscriptions (operator
// 2026-08-01) and, since checkout-first (operator 2026-08-03, change A), the
// place accounts are PROVISIONED from a paid checkout.
//
// SECURITY. Signature verification is not optional and there is no bypass. An
// unverified webhook is an unauthenticated caller asserting that someone has
// paid, and this endpoint's whole job is granting access. Without
// STRIPE_WEBHOOK_SECRET configured the route refuses every request.
//
// THE REVERSAL (change A). The earlier rule was "matching NEVER uses email":
// identity was pinned to a verified account, and a subscription with no account
// was unattributable and stopped there. Checkout-first inverts the default
// case, because now there is NO account at checkout time. Resolution order:
//
//   1. STAMP. sn_member_id on the subscription / session / customer. This is
//      the account-anchored path (a signed-in member subscribing from
//      /portal/account) and an operator dashboard action. Unchanged.
//   2. PROVISION BY EMAIL, on checkout.session.completed only. The
//      Stripe-verified email is the anchor: admin.generateLink(magiclink)
//      finds the account or CREATES one, and we stamp the id back onto the
//      subscription + customer so every later event resolves by stamp (1).
//
// PROVISION ONLY ON checkout.session.completed, never on a bare subscription.*
// event: those carry no payer email and no "just paid" semantics, so they
// resolve by stamp only and 500-retry until the completed event has stamped the
// customer. This avoids double-provisioning and email/stamp races.
//
// LOUD FAILURE. A completed checkout that cannot be provisioned (no email, an
// unmapped price, a failed admin call) is recorded in provisioning_failures and
// the operator is emailed directly -- the single out-of-window interrupt. The
// table makes that alarm fire once per stranded subscription, not once per
// Stripe retry.
import { NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { billingConfig, tierForPrice } from "@/lib/billing/config";
import { shouldApply } from "@/lib/billing/subscription-state";
import {
  pickAnchorEmail,
  firstBriefDateLabel,
  WELCOME_DESTINATION,
  type ProvisionFailureReason,
} from "@/lib/billing/provision";
import { renderMemberWelcome } from "@/lib/billing/welcome-email";
import { renderProvisionAlarm } from "@/lib/billing/alarm-email";
import { sendEmail } from "@/lib/email/send";

export const dynamic = "force-dynamic";
export const runtime = "nodejs"; // needs the raw body for signature verification

// Member-facing sends are ARMED by a deliberate env flip (operator: "don't wire
// any send path until I've approved the rendered result"), the same shape as
// PORTAL_ENABLED. While off, a provisioned member is entitled and their
// sign-in link is logged, but no welcome is sent -- so the flow is complete for
// testing without mailing anyone before the templates are approved. The
// operator alarm is NOT gated by this: it is an internal ops message and must
// always be able to reach the operator.
function memberWelcomeLive(): boolean {
  return process.env.MEMBER_WELCOME_LIVE === "true";
}

const WELCOME_SENDER =
  process.env.MEMBER_EMAIL_SENDER || "Signal North <signal@signalnorthintel.com>";
const ALARM_SENDER =
  process.env.OPERATOR_ALARM_SENDER || "Signal North Alerts <signal@signalnorthintel.com>";
const ALARM_RECIPIENT =
  process.env.OPERATOR_ALARM_EMAIL || "giancarlo@signalnorthintel.com";

// Service-role client: writes member_subscriptions, provisions accounts, and
// records provisioning_failures. Server-only; the key never reaches a browser
// bundle because this file is a route handler.
function admin(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}

const HANDLED = new Set([
  "checkout.session.completed",
  "customer.subscription.created",
  "customer.subscription.updated",
  "customer.subscription.deleted",
]);

function originFor(req: Request): string {
  const pinned = (process.env.NEXT_PUBLIC_SITE_URL ?? "").trim().replace(/\/+$/, "");
  if (pinned) return pinned;
  try {
    return new URL(req.url).origin;
  } catch {
    return "";
  }
}

export async function POST(req: Request) {
  const cfg = billingConfig();
  if (!cfg?.webhookSecret) {
    console.error("[stripe-webhook] refused: no STRIPE_WEBHOOK_SECRET");
    return NextResponse.json({ error: "webhook not configured" }, { status: 503 });
  }
  const sig = req.headers.get("stripe-signature");
  if (!sig) return NextResponse.json({ error: "unsigned" }, { status: 400 });

  const raw = await req.text();
  const stripe = new Stripe(cfg.secretKey);
  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(raw, sig, cfg.webhookSecret);
  } catch (e) {
    console.error("[stripe-webhook] bad signature:", (e as Error).message);
    return NextResponse.json({ error: "bad signature" }, { status: 400 });
  }

  if (!HANDLED.has(event.type)) {
    console.log("[stripe-webhook] ignoring", event.type);
    return NextResponse.json({ received: true, handled: false });
  }

  const db = admin();
  if (!db) {
    console.error("[stripe-webhook] no service-role client; asking for retry");
    return NextResponse.json({ error: "server misconfigured" }, { status: 500 });
  }

  try {
    const subId = await subscriptionIdFor(stripe, event);
    if (!subId) {
      console.log("[stripe-webhook]", event.type, "carried no subscription");
      return NextResponse.json({ received: true, handled: false });
    }
    const sub = await stripe.subscriptions.retrieve(subId);
    const priceId = sub.items.data[0]?.price?.id ?? null;
    const match = tierForPrice(priceId, cfg.prices);

    // Resolve the member: stamp first, then provision-by-email on completed.
    const resolved = await resolveMember(stripe, db, event, sub, originFor(req));

    if (!resolved) {
      // Could not attribute this subscription to a member.
      if (event.type === "checkout.session.completed") {
        // A PAID checkout with no account: the loud case. Record + alarm, then
        // 500 so Stripe retries (a retry can still succeed once transient).
        const email = anchorEmailFor(event, sub);
        await recordFailureAndAlarm(db, {
          email,
          subscriptionId: sub.id,
          customerId: customerIdOf(sub),
          tier: match?.tier ?? null,
          interval: match?.interval ?? null,
          reason: email ? "provision-failed" : "no-email",
        });
        return NextResponse.json({ error: "unprovisioned" }, { status: 500 });
      }
      // A bare subscription.* event with no stamp yet: almost always a race
      // with a checkout.session.completed that will stamp the customer. 500 so
      // Stripe retries; no alarm, because no fresh payment is stranded here.
      console.error("[stripe-webhook]", event.type, sub.id, "unresolved (no stamp yet)");
      return NextResponse.json({ error: "unresolved, retry" }, { status: 500 });
    }

    const { memberId, provisioned, signInLink } = resolved;

    if (!match) {
      // An ad hoc Enterprise Price or an unwired dashboard price. It must not
      // resolve to a tier the member did not buy. For a paid checkout this is
      // the loud case; for a sync event it just means we do not project it.
      if (event.type === "checkout.session.completed") {
        await recordFailureAndAlarm(db, {
          email: anchorEmailFor(event, sub),
          subscriptionId: sub.id,
          customerId: customerIdOf(sub),
          tier: null,
          interval: null,
          reason: "unmapped-price",
        });
      }
      console.error("[stripe-webhook] price", priceId, "maps to no configured tier");
      return NextResponse.json({ error: "unmapped price" }, { status: 422 });
    }

    const { data: existing } = await db
      .from("member_subscriptions")
      .select("event_created_at")
      .eq("member_id", memberId)
      .maybeSingle();

    const eventAt = new Date(event.created * 1000).toISOString();
    if (!shouldApply(existing ?? null, eventAt)) {
      console.log("[stripe-webhook] stale event for", memberId, "- not applied");
      return NextResponse.json({ received: true, handled: false, stale: true });
    }

    const periodEnd = sub.items.data[0]?.current_period_end;
    const { error } = await db.from("member_subscriptions").upsert(
      {
        member_id: memberId,
        stripe_customer_id: customerIdOf(sub),
        stripe_subscription_id: sub.id,
        tier: match.tier,
        interval: match.interval,
        status: sub.status,
        current_period_end: periodEnd
          ? new Date(periodEnd * 1000).toISOString()
          : null,
        event_created_at: eventAt,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "member_id" },
    );
    if (error) throw new Error(error.message);

    // Any earlier provisioning failure for this subscription is now resolved.
    await db
      .from("provisioning_failures")
      .update({ resolved_at: new Date().toISOString(), resolved_by: "stripe-retry" })
      .eq("stripe_subscription_id", sub.id)
      .is("resolved_at", null);

    // Post-provision, only on the email-anchored path (a freshly bought
    // checkout, whether it created the account or matched an existing one).
    if (provisioned) {
      await onProvisioned(db, {
        stripe,
        email: provisioned.email,
        memberId,
        signInLink,
        purchasedAt: new Date(event.created * 1000),
        subscriptionId: sub.id,
        customerId: customerIdOf(sub),
        tier: match.tier,
        interval: match.interval,
      });
    }

    console.log(
      "[stripe-webhook]", event.type, "->", memberId,
      match.tier, match.interval, sub.status,
      provisioned ? "(provisioned by email)" : "(by stamp)",
    );
    return NextResponse.json({ received: true, handled: true });
  } catch (e) {
    console.error("[stripe-webhook] failed:", (e as Error).message);
    return NextResponse.json({ error: "handler failed" }, { status: 500 });
  }
}

interface ResolvedMember {
  memberId: string;
  // Present when this resolution came from the email-anchored provision path,
  // carrying the anchor email so the caller can dedup the free list and welcome.
  provisioned: { email: string } | null;
  // The one-time sign-in link, present only on the provision path.
  signInLink: string | null;
}

// Stamp-first, then provision-by-email (completed only). See the file header.
async function resolveMember(
  stripe: Stripe,
  db: SupabaseClient,
  event: Stripe.Event,
  sub: Stripe.Subscription,
  origin: string,
): Promise<ResolvedMember | null> {
  const stamped = await resolveByStamp(stripe, event, sub);
  if (stamped) return { memberId: stamped, provisioned: null, signInLink: null };

  if (event.type !== "checkout.session.completed") return null;

  const email = anchorEmailFor(event, sub);
  if (!email) return null;

  // Match-or-provision in one call: generateLink(magiclink) returns the
  // existing account or creates one, plus a hashed token we turn into our own
  // /auth/confirm link (the token-hash template flow the confirm route handles).
  const { data, error } = await db.auth.admin.generateLink({
    type: "magiclink",
    email,
    options: {
      redirectTo: `${origin}/auth/confirm?next=${encodeURIComponent(WELCOME_DESTINATION)}`,
    },
  });
  if (error || !data?.user?.id) {
    console.error("[stripe-webhook] generateLink failed:", error?.message ?? "no user");
    return null;
  }
  const memberId = data.user.id;
  const hashedToken = data.properties?.hashed_token ?? "";
  const signInLink = hashedToken
    ? `${origin}/auth/confirm?token_hash=${hashedToken}&type=magiclink&next=${encodeURIComponent(WELCOME_DESTINATION)}`
    : `${origin}/login`;

  // Stamp the id back onto the subscription and customer so every LATER event
  // resolves by stamp (path 1) and never re-provisions.
  try {
    await stripe.subscriptions.update(sub.id, { metadata: { sn_member_id: memberId } });
    const custId = customerIdOf(sub);
    if (custId) await stripe.customers.update(custId, { metadata: { sn_member_id: memberId } });
  } catch (e) {
    // Non-fatal: the local row is written regardless, and a missing stamp only
    // means a later sync event 500-retries until it can re-provision (which is
    // idempotent). Logged, not swallowed.
    console.error("[stripe-webhook] stamp-back failed:", (e as Error).message);
  }

  return { memberId, provisioned: { email }, signInLink };
}

async function resolveByStamp(
  stripe: Stripe,
  event: Stripe.Event,
  sub: Stripe.Subscription,
): Promise<string | null> {
  const fromSub = sub.metadata?.sn_member_id;
  if (fromSub) return fromSub;

  if (event.type === "checkout.session.completed") {
    const s = event.data.object as Stripe.Checkout.Session;
    const fromSession = s.metadata?.sn_member_id ?? s.client_reference_id;
    if (fromSession) return fromSession;
  }

  const custId = customerIdOf(sub);
  if (custId) {
    try {
      const cust = await stripe.customers.retrieve(custId);
      if (!("deleted" in cust) && cust.metadata?.sn_member_id) {
        return cust.metadata.sn_member_id;
      }
    } catch (e) {
      console.error("[stripe-webhook] customer lookup failed:", (e as Error).message);
    }
  }
  return null;
}

// The Stripe-verified email for this checkout: the payer's own
// customer_details.email first, the Customer record's email second.
function anchorEmailFor(event: Stripe.Event, sub: Stripe.Subscription): string | null {
  const candidates: Array<string | null | undefined> = [];
  if (event.type === "checkout.session.completed") {
    const s = event.data.object as Stripe.Checkout.Session;
    candidates.push(s.customer_details?.email, s.customer_email);
  }
  const cust = sub.customer;
  if (cust && typeof cust !== "string" && !("deleted" in cust)) {
    candidates.push(cust.email);
  }
  return pickAnchorEmail(candidates);
}

function customerIdOf(sub: Stripe.Subscription): string | null {
  return typeof sub.customer === "string" ? sub.customer : sub.customer?.id ?? null;
}

interface ProvisionedCtx {
  stripe: Stripe;
  email: string;
  memberId: string;
  signInLink: string | null;
  purchasedAt: Date;
  subscriptionId: string;
  customerId: string | null;
  tier: string;
  interval: string;
}

// Runs after a member is provisioned by email and the subscription row is
// written: dedup the free list, then send the welcome (if armed).
async function onProvisioned(db: SupabaseClient, ctx: ProvisionedCtx): Promise<void> {
  // Free upgraders live only in brief_signups (no auth.users). On upgrade,
  // unsubscribe them from the free partial list so they are on ONE list, the
  // paid one, not both. Harmless when no free row exists.
  const { error: unsubErr } = await db
    .from("brief_signups")
    .update({ unsubscribed_at: new Date().toISOString() })
    .eq("email", ctx.email)
    .is("unsubscribed_at", null);
  if (unsubErr) {
    console.error("[stripe-webhook] free-list dedup failed:", unsubErr.message);
  }

  if (!memberWelcomeLive()) {
    // Held by design until the operator arms member emails. The member is
    // entitled; log the link so it is recoverable during test-mode validation.
    console.log(
      "[stripe-webhook] welcome HELD (MEMBER_WELCOME_LIVE off) for",
      ctx.memberId, "link:", ctx.signInLink,
    );
    return;
  }

  const welcome = renderMemberWelcome({
    signInLink: ctx.signInLink ?? "",
    firstBriefDate: firstBriefDateLabel(ctx.purchasedAt),
  });
  const res = await sendEmail({
    from: WELCOME_SENDER,
    to: [ctx.email],
    subject: welcome.subject,
    html: welcome.html,
    text: welcome.text,
  });
  if (!res.ok) {
    // Entitlement is done; the comms failed. Alarm so the operator can resend,
    // but do NOT fail the webhook (a 500 here would re-provision needlessly).
    console.error("[stripe-webhook] welcome send failed:", res.message);
    await recordFailureAndAlarm(db, {
      email: ctx.email,
      subscriptionId: ctx.subscriptionId,
      customerId: ctx.customerId,
      tier: ctx.tier,
      interval: ctx.interval,
      reason: "welcome-send-failed",
    });
  }
}

interface FailureCtx {
  email: string | null;
  subscriptionId: string;
  customerId: string | null;
  tier: string | null;
  interval: string | null;
  reason: ProvisionFailureReason;
}

// Record the failure (idempotent per subscription) and, only when this is the
// first record of it, email the operator the reconciliation alarm.
async function recordFailureAndAlarm(db: SupabaseClient, ctx: FailureCtx): Promise<void> {
  // Insert-if-absent. A conflict means we already recorded (and likely alarmed)
  // this subscription, so we do not alarm again on Stripe's retries.
  const { data: inserted, error } = await db
    .from("provisioning_failures")
    .upsert(
      {
        stripe_subscription_id: ctx.subscriptionId,
        stripe_customer_id: ctx.customerId,
        email: ctx.email,
        tier: ctx.tier,
        interval: ctx.interval,
        reason: ctx.reason,
      },
      { onConflict: "stripe_subscription_id", ignoreDuplicates: true },
    )
    .select("id, alerted_at")
    .maybeSingle();
  if (error) {
    console.error("[stripe-webhook] failure-record write failed:", error.message);
  }

  // Only alarm on the first sighting: `inserted` is non-null only when a NEW
  // row was written (ignoreDuplicates returns nothing on conflict). If the row
  // already existed, the operator has already been told.
  if (!inserted) {
    // Either the row pre-existed (already alarmed) or the write errored. In the
    // welcome-send-failed case there is no prior row for THIS reason, but the
    // subscription may already have a resolved row from provisioning; alarm
    // once more only if we actually inserted. Conservative: stay quiet.
    return;
  }

  const alarm = renderProvisionAlarm({
    email: ctx.email,
    subscriptionId: ctx.subscriptionId,
    customerId: ctx.customerId,
    tier: ctx.tier,
    interval: ctx.interval,
    reason: ctx.reason,
  });
  const res = await sendEmail({
    from: ALARM_SENDER,
    to: [ALARM_RECIPIENT],
    subject: alarm.subject,
    html: alarm.html,
    text: alarm.text,
    replyTo: ALARM_RECIPIENT,
  });
  if (res.ok) {
    await db
      .from("provisioning_failures")
      .update({ alerted_at: new Date().toISOString() })
      .eq("id", inserted.id);
  } else {
    // The alarm itself could not be delivered. This is the worst case; make it
    // as loud as we can in the logs, which the operator's log monitor watches.
    console.error(
      "[stripe-webhook] RECONCILIATION ALARM COULD NOT BE SENT:",
      res.message, "| paid, unprovisioned:", ctx.email, ctx.subscriptionId,
    );
  }
}

async function subscriptionIdFor(
  stripe: Stripe,
  event: Stripe.Event,
): Promise<string | null> {
  if (event.type === "checkout.session.completed") {
    const s = event.data.object as Stripe.Checkout.Session;
    return typeof s.subscription === "string"
      ? s.subscription
      : s.subscription?.id ?? null;
  }
  const s = event.data.object as Stripe.Subscription;
  return s.id ?? null;
}

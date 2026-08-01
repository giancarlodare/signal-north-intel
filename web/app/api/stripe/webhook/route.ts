// Stripe webhook: the ONLY writer of member_subscriptions (operator
// 2026-08-01). Stripe is the source of truth; this route projects it locally
// so the portal guard answers from one indexed row rather than a network call
// on every render.
//
// SECURITY. Signature verification is not optional and there is no bypass.
// An unverified webhook is an unauthenticated caller asserting that someone
// has paid, and this endpoint's whole job is granting access. Without
// STRIPE_WEBHOOK_SECRET configured the route refuses every request rather
// than trusting the body.
//
// SCOPE. Happy path only. checkout.session.completed opens access;
// subscription.updated and .deleted keep it honest when the operator acts by
// hand in the Stripe dashboard. Nothing here implements self-serve
// cancellation, plan changes, dunning, or failed-payment recovery.
import { NextResponse } from "next/server";
import Stripe from "stripe";
import { createClient } from "@supabase/supabase-js";
import { billingConfig, tierForPrice } from "@/lib/billing/config";
import { shouldApply } from "@/lib/billing/subscription-state";

export const dynamic = "force-dynamic";
export const runtime = "nodejs"; // needs the raw body for signature verification

// Service-role client: this table is service-role-write by policy, and the
// webhook has no member session to borrow. Server-only; the key never reaches
// a browser bundle because this file is a route handler.
function admin() {
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
    // 400, not 500: a bad signature is a rejected caller, not our outage, and
    // Stripe should not retry it.
    console.error("[stripe-webhook] bad signature:", (e as Error).message);
    return NextResponse.json({ error: "bad signature" }, { status: 400 });
  }

  if (!HANDLED.has(event.type)) {
    // Logged, not swallowed, and 200 so Stripe stops retrying something we
    // have deliberately chosen not to act on.
    console.log("[stripe-webhook] ignoring", event.type);
    return NextResponse.json({ received: true, handled: false });
  }

  const db = admin();
  if (!db) {
    // 500 so Stripe RETRIES: this is our misconfiguration, and dropping the
    // event would leave a paying member without access and no trace.
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
    // MATCHING NEVER USES EMAIL (operator 2026-08-01). Checkout's own customer
    // email can diverge from the verified account address, so every fallback
    // below is an explicit member id we stamped ourselves. If all four are
    // absent the subscription is unattributable and we say so loudly rather
    // than guessing from an address.
    const memberId = await resolveMemberId(stripe, event, sub);
    if (!memberId) {
      console.error("[stripe-webhook] subscription", subId, "has no sn_member_id");
      return NextResponse.json({ error: "unattributable subscription" }, { status: 422 });
    }

    const priceId = sub.items.data[0]?.price?.id ?? null;
    const match = tierForPrice(priceId, cfg.prices);
    if (!match) {
      // An ad hoc Enterprise Price, or a dashboard price nobody wired. It must
      // NOT resolve to a tier the member did not buy, so we refuse rather than
      // guess, and the operator provisions that member by hand.
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
        stripe_customer_id:
          typeof sub.customer === "string" ? sub.customer : sub.customer?.id ?? null,
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

    console.log(
      "[stripe-webhook]", event.type, "->", memberId,
      match.tier, match.interval, sub.status,
    );
    return NextResponse.json({ received: true, handled: true });
  } catch (e) {
    // 500 so Stripe retries. A dropped event means a member paid and cannot
    // read what they paid for, which must never be resolved by silence.
    console.error("[stripe-webhook] failed:", (e as Error).message);
    return NextResponse.json({ error: "handler failed" }, { status: 500 });
  }
}

// The four places sn_member_id is stamped at checkout, read in descending
// order of directness. Any ONE of them is sufficient; email is not among them.
async function resolveMemberId(
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

  // Last resort: the Customer we created carries it too, which survives even
  // a subscription created by hand in the dashboard against that customer.
  const custId =
    typeof sub.customer === "string" ? sub.customer : sub.customer?.id ?? null;
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

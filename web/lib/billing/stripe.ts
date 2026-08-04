// Stage-4 Stripe plumbing (server-only). Stripe IS the source of truth: no
// billing tables, no webhook persistence, no service key. Checkout sessions
// are tagged with the member's id (metadata.sn_member_id), and subscription
// state is read back live from Stripe's API. Test mode by construction: the
// key guard in ./config refuses live keys without the explicit go-live flag.
import Stripe from "stripe";
import {
  billingConfig,
  tierForPrice,
  type Interval,
  type Tier,
} from "./config";
import { anonymousCheckoutParams } from "./checkout-params";

export interface MemberSubscription {
  tier: Tier;
  status: string;               // 'active' | 'trialing' | 'past_due' | ...
  currentPeriodEnd: string | null; // ISO date of the next renewal
  testMode: boolean;
}

function client(secretKey: string): Stripe {
  return new Stripe(secretKey);
}

export function billingEnabled(): boolean {
  return billingConfig() !== null;
}

// The member's current subscription, straight from Stripe, or null when
// billing is unconfigured / nothing found. Errors degrade to null: the
// account page then shows the manual-provision state, never a crash.
export async function getMemberSubscription(
  memberId: string,
): Promise<MemberSubscription | null> {
  const cfg = billingConfig();
  if (!cfg) return null;
  try {
    const stripe = client(cfg.secretKey);
    const found = await stripe.subscriptions.search({
      query: `metadata['sn_member_id']:'${memberId}' AND status:'active'`,
      limit: 1,
    });
    const sub = found.data[0];
    if (!sub) return null;
    const priceId = sub.items.data[0]?.price?.id ?? null;
    const match = tierForPrice(priceId, cfg.prices);
    if (!match) return null;
    const tier = match.tier;
    const end = sub.items.data[0]?.current_period_end;
    return {
      tier,
      status: sub.status,
      currentPeriodEnd: end ? new Date(end * 1000).toISOString() : null,
      testMode: cfg.secretKey.includes("_test_"),
    };
  } catch {
    return null;
  }
}

// CHECKOUT-FIRST (operator 2026-08-03, change A). The primary purchase path is
// now anonymous: someone with no account presses "Join Weekly" and lands in
// hosted Checkout, which collects the email itself. That address is the
// provisioning anchor -- the webhook creates the account from it. There is no
// member id to pin here because there is no member yet, so nothing is stamped;
// the webhook resolves this subscription by its Stripe-verified email instead.
//
// This does NOT collect email/name ourselves and redirect: hosted Checkout
// already collects them with the card, and adding a form in front only adds a
// step someone can abandon. The interval is chosen on OUR page before this call
// (hosted Checkout has no in-session interval toggle), which is why it is a
// parameter rather than something Checkout offers.
export async function createAnonymousCheckoutUrl(
  tier: Tier,
  origin: string,
  interval: Interval = "annual",
): Promise<string | null> {
  const cfg = billingConfig();
  const price = cfg?.prices[tier]?.[interval];
  if (!cfg || !price) {
    console.error("[billing] no configured price for", tier, interval);
    return null;
  }
  try {
    const stripe = client(cfg.secretKey);
    // Params come from the pure anonymousCheckoutParams (checkout-params.ts),
    // whose mode:"subscription" invariant is asserted by a unit test that runs
    // on every push -- so a payment-mode regression fails CI, not a live sale.
    const session = await stripe.checkout.sessions.create(
      anonymousCheckoutParams(price, origin),
    );
    return session.url ?? null;
  } catch (e) {
    console.error("[billing] anon checkout session failed:", (e as Error).message);
    return null;
  }
}

// A Checkout session for one tier, ANCHORED TO AN EXISTING ACCOUNT. This is the
// secondary path: a member who is already signed in (on /portal/account)
// choosing to subscribe. Here we DO have a verified account id, so identity is
// pinned to it (sn_member_id in four places) exactly as before -- the webhook
// resolves this subscription by that stamp, never needing the email fallback.
// Returns the redirect URL or null when billing is dark / the tier has no price.
export async function createCheckoutUrl(
  memberId: string,
  email: string | null,
  tier: Tier,
  origin: string,
  interval: Interval = "annual",
): Promise<string | null> {
  const cfg = billingConfig();
  const price = cfg?.prices[tier]?.[interval];
  if (!cfg || !price) {
    console.error("[billing] no configured price for", tier, interval);
    return null;
  }
  try {
    const stripe = client(cfg.secretKey);
    // IDENTITY IS PINNED TO THE ACCOUNT, NEVER TO AN EMAIL (operator
    // 2026-08-01). Stripe Checkout collects its own customer email, which can
    // diverge from the verified account address; a subscription that cannot be
    // matched back to an account is the failure mode being designed out here.
    //
    // Two halves. First: we create or reuse a Customer carrying sn_member_id
    // and pass `customer`, rather than passing customer_email and letting
    // Checkout mint one. That fixes the address to the VERIFIED account email
    // and makes it non-editable at checkout, so nobody pays under an address
    // the brief will never reach.
    const customerId = await customerForMember(stripe, memberId, email);
    // Second: sn_member_id is stamped in FOUR independent places, so matching
    // never falls back to comparing email strings. The webhook reads them in
    // order and any one of them is sufficient.
    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      line_items: [{ price, quantity: 1 }],
      ...(customerId
        ? { customer: customerId }
        : { customer_email: email ?? undefined }),
      client_reference_id: memberId,
      subscription_data: { metadata: { sn_member_id: memberId } },
      metadata: { sn_member_id: memberId },
      success_url: `${origin}/portal/account?checkout=success`,
      cancel_url: `${origin}/portal/account?checkout=cancelled`,
    });
    return session.url ?? null;
  } catch (e) {
    // Logged rather than swallowed: a checkout that silently fails to open is
    // a member who wanted to pay us and could not, with no trace of it.
    console.error("[billing] checkout session failed:", (e as Error).message);
    return null;
  }
}


// Create or reuse the Stripe Customer for one member, keyed on sn_member_id
// in metadata rather than on email, so a member who later changes their
// address is still the same customer. Returns null on failure, which the
// caller degrades to customer_email: a checkout that works with a weaker
// identity guarantee beats no checkout, and the other three id stamps still
// carry the match.
async function customerForMember(
  stripe: Stripe,
  memberId: string,
  email: string | null,
): Promise<string | null> {
  try {
    const found = await stripe.customers.search({
      query: `metadata['sn_member_id']:'${memberId}'`,
      limit: 1,
    });
    const existing = found.data[0];
    if (existing) return existing.id;
    const created = await stripe.customers.create({
      email: email ?? undefined,
      metadata: { sn_member_id: memberId },
    });
    return created.id;
  } catch (e) {
    console.error("[billing] customer resolve failed:", (e as Error).message);
    return null;
  }
}

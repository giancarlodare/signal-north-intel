// Stage-4 Stripe plumbing (server-only). Stripe IS the source of truth: no
// billing tables, no webhook persistence, no service key. Checkout sessions
// are tagged with the member's id (metadata.sn_member_id), and subscription
// state is read back live from Stripe's API. Test mode by construction: the
// key guard in ./config refuses live keys without the explicit go-live flag.
import Stripe from "stripe";
import { billingConfig, tierForPrice, type Tier } from "./config";

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
    const tier = tierForPrice(priceId, cfg.prices);
    if (!tier) return null;
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

// A Checkout session for one tier. Returns the redirect URL or null when
// billing is dark / the tier has no configured price.
export async function createCheckoutUrl(
  memberId: string,
  email: string | null,
  tier: Tier,
  origin: string,
): Promise<string | null> {
  const cfg = billingConfig();
  if (!cfg || !cfg.prices[tier]) return null;
  try {
    const stripe = client(cfg.secretKey);
    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      line_items: [{ price: cfg.prices[tier], quantity: 1 }],
      customer_email: email ?? undefined,
      client_reference_id: memberId,
      subscription_data: { metadata: { sn_member_id: memberId } },
      metadata: { sn_member_id: memberId },
      success_url: `${origin}/portal/account?checkout=success`,
      cancel_url: `${origin}/portal/account?checkout=cancelled`,
    });
    return session.url ?? null;
  } catch {
    return null;
  }
}

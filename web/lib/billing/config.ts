// Stage-4 billing seam: pure configuration + the live-charge guard.
// (No Stripe SDK import here so node --test can load it.)
//
// THE SEAM (design: "going live is a key swap plus an operator decision,
// reviewable on its own"): a LIVE secret key is REFUSED unless the operator
// has also set STRIPE_LIVE_APPROVED=true. While dark, only sk_test_ keys
// function, so no code path can create a real charge. Tier prices come from
// operator-created Stripe Prices, referenced by env id, never hardcoded.

export type Tier = "weekly" | "pro" | "founding";

export const TIER_LABELS: Record<Tier, string> = {
  weekly: "Signal North Weekly",
  pro: "Signal North Pro",
  founding: "Founding Member",
};

// ANNUAL IS THE HEADLINE PRICE, monthly is available at a premium: a year
// costs the same as ten months, so annual is two months free. That is a
// commercial decision (operator 2026-07-29), so both intervals are first
// class here rather than annual being "the price" and monthly a variant.
export type Interval = "annual" | "monthly";
export type TierPrices = Record<Interval, string>;

export interface BillingConfig {
  secretKey: string;
  prices: Record<Tier, TierPrices>;
  // Required to trust an inbound webhook. Absent means we refuse to act on
  // webhook payloads at all -- an unverified webhook is an unauthenticated
  // caller asserting someone has paid.
  webhookSecret: string | null;
}

// The guard, pure so it is unit-tested: returns the reason a key must be
// refused, or null when it may be used.
export function keyRefusalReason(
  secretKey: string | undefined,
  liveApproved: boolean,
): string | null {
  if (!secretKey) return "no key configured";
  if (secretKey.startsWith("sk_test_") || secretKey.startsWith("rk_test_"))
    return null;
  if (!liveApproved)
    return "live key refused: set STRIPE_LIVE_APPROVED=true only as a " +
      "deliberate go-live decision";
  return null;
}

// price id -> (tier, interval), for reading a subscription back. Pure.
// Returns null for an UNRECOGNISED price, which is the important case: an ad
// hoc Price scoped to one Enterprise customer, or a price created in the
// dashboard and not wired here, must not silently resolve to a tier a member
// did not buy.
export function tierForPrice(
  priceId: string | null | undefined,
  prices: Record<Tier, TierPrices>,
): { tier: Tier; interval: Interval } | null {
  if (!priceId) return null;
  for (const t of Object.keys(prices) as Tier[]) {
    for (const i of ["annual", "monthly"] as Interval[]) {
      if (prices[t][i] && prices[t][i] === priceId) return { tier: t, interval: i };
    }
  }
  return null;
}

// Reads env; null when billing is not (fully) configured, which callers
// treat as "billing dark" and render the manual-provision state.
export function billingConfig(): BillingConfig | null {
  const secretKey = process.env.STRIPE_SECRET_KEY;
  const refusal = keyRefusalReason(
    secretKey,
    process.env.STRIPE_LIVE_APPROVED === "true",
  );
  if (refusal || !secretKey) return null;
  const prices: Record<Tier, TierPrices> = {
    weekly: {
      annual: process.env.STRIPE_PRICE_WEEKLY_ANNUAL ?? "",
      monthly: process.env.STRIPE_PRICE_WEEKLY_MONTHLY ?? "",
    },
    pro: {
      annual: process.env.STRIPE_PRICE_PRO_ANNUAL ?? "",
      monthly: process.env.STRIPE_PRICE_PRO_MONTHLY ?? "",
    },
    // Founding is annual only and is never self-serve: it exists here so an
    // operator-provisioned subscription resolves to a tier, not so anyone can
    // buy it. No member-facing path selects it.
    founding: {
      annual: process.env.STRIPE_PRICE_FOUNDING_ANNUAL ?? "",
      monthly: "",
    },
  };
  const anyPrice = (Object.keys(prices) as Tier[]).some(
    (t) => prices[t].annual || prices[t].monthly,
  );
  if (!anyPrice) return null;
  return {
    secretKey,
    prices,
    webhookSecret: process.env.STRIPE_WEBHOOK_SECRET || null,
  };
}

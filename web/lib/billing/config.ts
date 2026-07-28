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

export interface BillingConfig {
  secretKey: string;
  prices: Record<Tier, string>;
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

// price id -> tier, for reading a subscription back. Pure.
export function tierForPrice(
  priceId: string | null | undefined,
  prices: Record<Tier, string>,
): Tier | null {
  if (!priceId) return null;
  for (const t of Object.keys(prices) as Tier[]) {
    if (prices[t] && prices[t] === priceId) return t;
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
  const prices: Record<Tier, string> = {
    weekly: process.env.STRIPE_PRICE_WEEKLY ?? "",
    pro: process.env.STRIPE_PRICE_PRO ?? "",
    founding: process.env.STRIPE_PRICE_FOUNDING ?? "",
  };
  if (!prices.weekly && !prices.pro && !prices.founding) return null;
  return { secretKey, prices };
}

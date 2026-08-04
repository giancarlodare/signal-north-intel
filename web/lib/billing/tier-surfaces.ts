// WHICH portal surfaces each TIER opens (operator ship-gate, 2026-08-04).
//
// The paywall (portal-routes.ts + RequirePaid) answers paid-vs-unpaid. This
// module answers the question the pricing table already answers publicly:
// which PAID tier a surface belongs to. Before this existed, grantsPortal()
// treated weekly/pro/founding identically, so a Weekly member could reach
// Closing-soon and Watching -- surfaces the tier table sells as Pro. The
// operator's ruling: the table must never claim a distinction the product
// does not enforce.
//
// Pure and dependency-light on purpose: imported by the client-side nav (to
// hide what the tier cannot reach) and by the server-side RequireTier guard
// (to enforce it), so the two can never disagree. The source of truth for the
// mapping is the pricing table's rows; change them together.
import type { Tier } from "./config";

// Higher rank opens everything below it. Founding is a private, operator-
// provisioned tier that gets everything Pro gets.
const TIER_RANK: Record<Tier, number> = { weekly: 1, pro: 2, founding: 3 };

// Surfaces the pricing table marks Pro-and-above. Everything else under
// /portal that RequirePaid guards is Weekly-and-above (the brief, saved).
// Prefix-matched so a future /portal/watching/edit inherits its parent's tier.
const PRO_PREFIXES = ["/portal/closing-soon", "/portal/watching"] as const;

export function requiredTierFor(path: string): Tier {
  return PRO_PREFIXES.some((p) => path === p || path.startsWith(p + "/"))
    ? "pro"
    : "weekly";
}

export function tierAllows(tier: Tier, path: string): boolean {
  return TIER_RANK[tier] >= TIER_RANK[requiredTierFor(path)];
}

// The nav's question, tolerant of "no tier yet" (unpaid member, or an
// operator viewing the surface without a subscription row): only surfaces the
// tier provably opens are shown. No tier -> only Weekly-level items render,
// and the paywall handles the rest honestly on click.
export function navShows(tier: Tier | null, href: string): boolean {
  if (!tier) return requiredTierFor(href) === "weekly";
  return tierAllows(tier, href);
}

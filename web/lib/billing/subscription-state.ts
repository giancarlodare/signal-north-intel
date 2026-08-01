// The rules that turn a Stripe subscription into portal access. Pure, so the
// thing standing between a member and paid content is unit-tested without a
// network call or a database.
import type { Interval, Tier } from "./config";

export interface SubscriptionRow {
  member_id: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  tier: Tier;
  interval: Interval;
  status: string;
  current_period_end: string | null;
  event_created_at: string;
}

// Stripe statuses that mean "this member is paid up right now". Deliberately
// an ALLOW-LIST: a status Stripe adds in future defaults to no access, which
// is the safe direction. 'past_due' is excluded on purpose -- recovering a
// failed payment is a Stripe dashboard task (operator 2026-08-01), and while
// it is unrecovered the member is not paid up.
export const ACCESS_STATUSES = new Set(["active", "trialing"]);

export function grantsAccess(row: SubscriptionRow | null): boolean {
  if (!row) return false;
  return ACCESS_STATUSES.has(row.status);
}

// The portal is Weekly and above. Free is email-only with no login at all
// (operator 2026-08-01), so any member session that reaches the portal should
// be carrying one of these.
const PORTAL_TIERS = new Set<Tier>(["weekly", "pro", "founding"]);

export function grantsPortal(row: SubscriptionRow | null): boolean {
  return grantsAccess(row) && PORTAL_TIERS.has(row!.tier);
}

// Stripe delivers webhooks out of order and retries them. An event older than
// what we already stored must NOT be applied, or a late 'created' can
// resurrect a subscription the operator cancelled minutes ago.
export function shouldApply(
  existing: { event_created_at: string } | null,
  incomingCreatedAt: string,
): boolean {
  if (!existing) return true;
  return new Date(incomingCreatedAt) >= new Date(existing.event_created_at);
}

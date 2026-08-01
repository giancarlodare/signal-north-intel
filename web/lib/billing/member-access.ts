// Reading the webhook-fed subscription row for the CURRENT session, and
// deciding whether it opens the portal.
//
// The row is read under the member's own session, so RLS scopes it to their
// own row and this file adds no security of its own. What it does add is the
// FAIL-CLOSED decision: an absent table, an unreadable row, or an error all
// mean no access, because the alternative is a paid surface opening on a
// database hiccup.
import type { SupabaseClient } from "@supabase/supabase-js";
import { grantsPortal, type SubscriptionRow } from "./subscription-state";

export interface AccessDecision {
  allowed: boolean;
  // Why, so the surface can say something true rather than a bare 404.
  reason: "granted" | "no-subscription" | "not-paid-up" | "unreadable";
  row: SubscriptionRow | null;
}

export async function portalAccess(
  supabase: SupabaseClient,
): Promise<AccessDecision> {
  const { data, error } = await supabase
    .from("member_subscriptions")
    .select(
      "member_id, stripe_customer_id, stripe_subscription_id, tier, " +
      "interval, status, current_period_end, event_created_at",
    )
    .maybeSingle();

  if (error) {
    // FAIL CLOSED, and LOUD. Pre-migration this is the expected state and the
    // portal stays shut, which is correct: the guard's job is to open the
    // portal only on positive evidence of payment, never on the absence of
    // evidence to the contrary.
    console.error("[member-access] subscription read failed:", error.message);
    return { allowed: false, reason: "unreadable", row: null };
  }

  const row = (data as SubscriptionRow | null) ?? null;
  if (!row) return { allowed: false, reason: "no-subscription", row: null };
  if (!grantsPortal(row)) return { allowed: false, reason: "not-paid-up", row };
  return { allowed: true, reason: "granted", row };
}

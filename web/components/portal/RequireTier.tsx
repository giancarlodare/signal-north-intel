// The TIER guard for Pro surfaces (operator ship-gate, 2026-08-04). Sits where
// RequirePaid sits on Weekly pages, and answers both questions in order: is
// this member paid up at all (RequirePaid's question), and does their tier
// open THIS surface (the new one).
//
// A Weekly member hitting a Pro surface is redirected to
// /portal/account?access=tier -- which renders the Pro early-access CAPTURE,
// not a wall. The operator's ruling: a Weekly member reaching for a Pro
// surface is the strongest upgrade signal we have; treat it as one.
//
// FAIL CLOSED, same as RequirePaid: unreadable state means no access.
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { portalAccess } from "@/lib/billing/member-access";
import { tierAllows } from "@/lib/billing/tier-surfaces";

export default async function RequireTier(path: string) {
  const supabase = createClient();
  const decision = await portalAccess(supabase);
  if (!decision.allowed) {
    // Not paid up at all: the same honest routing RequirePaid gives.
    redirect(`/portal/account?access=${decision.reason}`);
  }
  if (!tierAllows(decision.row!.tier, path)) {
    // Paid, but this surface belongs to a higher tier.
    redirect("/portal/account?access=tier");
  }
  return null;
}

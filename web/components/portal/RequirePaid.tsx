// The paywall, applied per PRODUCT page rather than in the member layout.
//
// WHY NOT THE LAYOUT: the layout wraps /portal/account too, and that is where
// checkout lives. Guarding there locks an unsubscribed member out of the page
// where they subscribe. So this is a component each product page awaits, and
// the account page simply does not use it.
//
// FAIL CLOSED: portalAccess() treats an absent table, an unreadable row, or
// any error as no access. A paid surface opens on positive evidence of
// payment, never on the absence of evidence against it.
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { portalAccess } from "@/lib/billing/member-access";

export default async function RequirePaid() {
  const supabase = createClient();
  const decision = await portalAccess(supabase);
  if (decision.allowed) return null;
  // Redirected to the RELATIONSHIP surface with an honest reason, never a
  // 404. They are a real member who has not paid; saying so is both truthful
  // and the only way they can act on it.
  redirect(`/portal/account?access=${decision.reason}`);
}

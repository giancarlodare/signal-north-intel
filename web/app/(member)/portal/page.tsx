// /portal is a ROUTER, not a page (operator 2026-08-03, change A). It must
// never 404 and never dead-end: it sends a paid member to the product
// (/portal/brief) and an unpaid one to the relationship surface where checkout
// lives (/portal/account). This is the landing the magic-link / welcome sign-in
// link points at, so getting it wrong stranded a just-signed-in member on a
// 404 -- the bug this replaces.
//
// The paid/unpaid decision is portalAccess(): read under the member's own
// session, RLS-scoped to their row, fail-closed (an unreadable row sends them
// to /portal/account, never into the product).
//
// NOTE (supersedes the stage-2 dashboard index): the earlier /portal rendered
// a member dashboard. The operator's checkout-first ruling makes /portal a pure
// redirect instead; the member edition of the brief is the paid home.
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { portalAccess } from "@/lib/billing/member-access";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

export default async function PortalIndex() {
  const supabase = createClient();
  const decision = await portalAccess(supabase);
  redirect(decision.allowed ? "/portal/brief" : "/portal/account");
}

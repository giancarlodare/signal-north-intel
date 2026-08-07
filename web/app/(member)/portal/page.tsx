// /portal is a ROUTER, not a page (operator 2026-08-03, change A).
// Paid members land on /portal/brief; unpaid see /portal/account.
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

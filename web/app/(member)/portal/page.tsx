// Wave 3 member surface: STAGE-1 SCAFFOLD ONLY.
//
// Functional placeholder proving the route exists and is gated. The real
// member dashboard (data layer + components) is stage 2; ALL visual design
// is AWAITING GIANCARLO'S CLAUDE DESIGN FILES. Deliberately unstyled: no
// layout, no CSS, no copy beyond a functional marker. Do not add styling
// here; drop design files in at stage 2.
import { createClient } from "@/lib/supabase/server";
import { currentRole } from "@/lib/auth/roles";

export const metadata = {
  robots: { index: false, follow: false, nocache: true },
};

export default async function PortalHome() {
  const supabase = createClient();
  const role = await currentRole(supabase);
  // Stage 2 replaces this with the member-filtered dashboard data layer.
  return (
    <main>
      <p data-testid="portal-scaffold">member portal (stage-1 scaffold)</p>
      <p data-testid="portal-role">role: {role}</p>
    </main>
  );
}

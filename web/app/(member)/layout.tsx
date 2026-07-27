// Member dashboard layout (Wave 3, Claude Design incorporation). Loads the
// design system + dashboard styles, wraps the portal in the .sn-site scope,
// and renders the shared member header with the session's honest identity.
// Route access is enforced by middleware gate() + RLS; this is presentation.
import "../design-system/tokens.css";
import "./dashboard.css";
import DashHeader from "@/components/portal/DashHeader";
import { memberIdentity } from "@/lib/portal/identity";
import { createClient } from "@/lib/supabase/server";

export default async function MemberLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const identity = memberIdentity(
    user?.email,
    (user?.user_metadata as Record<string, unknown> | undefined)?.[
      "full_name"
    ] as string | undefined,
  );

  return (
    <div className="sn-site">
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        rel="preconnect"
        href="https://fonts.gstatic.com"
        crossOrigin="anonymous"
      />
      <link
        href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
        rel="stylesheet"
      />
      <DashHeader initials={identity.initials} shortname={identity.shortname} />
      {children}
    </div>
  );
}

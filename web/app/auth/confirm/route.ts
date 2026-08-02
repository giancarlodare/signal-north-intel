// Magic-link landing (dual-mode auth, operator 2026-07-27). Handles both
// shapes Supabase can send depending on template/flow configuration:
//   ?code=...                  PKCE code exchange (default template)
//   ?token_hash=...&type=...   token-hash template (verifyOtp)
// On success the session cookie is set and the user lands on their role's
// home surface; a used or expired link returns to /login with a clear error.
//
// ?next=/some/path OVERRIDES the role home, and is how a "Join Weekly" signup
// arrives at checkout (/portal/account) rather than the portal index. It is
// passed through safeNext(), which rejects anything that is not a same-origin
// absolute path: a magic link is a URL an attacker can hand to someone else,
// so an unvalidated `next` would make this route a credible open redirector.
//
// If a mail template or a redirect allow-list strips the parameter, the flow
// still lands correctly: a brand-new account has no subscription, so /portal
// bounces it to /portal/account anyway (components/portal/RequirePaid.tsx).
// `next` makes that destination explicit rather than incidental.
import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { roleFromUser } from "@/lib/auth/roles";
import { safeNext } from "@/lib/site/signup";
import type { EmailOtpType } from "@supabase/supabase-js";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const url = request.nextUrl;
  const code = url.searchParams.get("code");
  const tokenHash = url.searchParams.get("token_hash");
  const type = url.searchParams.get("type") as EmailOtpType | null;
  const supabase = createClient();

  let ok = false;
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    ok = !error;
  } else if (tokenHash && type) {
    const { error } = await supabase.auth.verifyOtp({
      token_hash: tokenHash,
      type,
    });
    ok = !error;
  }

  if (!ok) {
    return NextResponse.redirect(
      new URL(
        "/login?error=" +
          encodeURIComponent(
            "That sign-in link is expired or already used. Request a fresh one."
          ),
        url
      )
    );
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();
  const home = roleFromUser(user) === "member" ? "/portal" : "/corpus";
  // An operator is never sent to a member destination: `next` is a member
  // signup's destination, and the operator's home surface wins over it.
  const requested = roleFromUser(user) === "member"
    ? safeNext(url.searchParams.get("next"))
    : null;
  return NextResponse.redirect(new URL(requested ?? home, url));
}

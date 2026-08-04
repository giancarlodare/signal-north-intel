"use server";

import { createClient } from "@/lib/supabase/server";
import { roleFromUser } from "@/lib/auth/roles";
import { redirect } from "next/navigation";
import { siteOrigin } from "@/lib/site/origin";

// Dual-mode auth (operator decision 2026-07-27): magic link is the designed
// default for members; password stays fully working underneath because
// vendor/gov mail filters can eat the link and the operator signs in daily.

// Where the emailed link lands (app/auth/confirm/route.ts). Origin pinned by
// NEXT_PUBLIC_SITE_URL in production, header-derived on previews
// (lib/site/origin.ts): the localhost-fallback bug would have broken
// production magic-link login at launch, not just signup.
function confirmUrl(): string {
  return `${siteOrigin()}/auth/confirm`;
}

export async function sendMagicLink(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim();
  if (email) {
    const supabase = createClient();
    // shouldCreateUser: false — founding members are provisioned manually;
    // a link request must never create an account. The VISITOR-FACING result
    // is ignored on purpose (no user enumeration): unknown addresses get the
    // same "if that address belongs to a member" message as real ones.
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: confirmUrl(), shouldCreateUser: false },
    });
    if (error) {
      // Logged SERVER-SIDE only (operator 2026-08-04): no-enumeration holds
      // for the visitor, but a swallowed send failure -- the auth-email rate
      // limit choking, SMTP down -- must be visible to us in the logs, or a
      // member locked out of their own account looks exactly like nothing.
      console.error("[login] magic-link send failed:", error.message);
    }
  }
  redirect("/login?sent=1");
}

export async function signIn(formData: FormData) {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  const supabase = createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) {
    redirect("/login?error=" + encodeURIComponent(error.message));
  }
  // Land each role on its home surface (middleware would bounce a member off
  // /corpus anyway; this just skips the extra hop).
  const {
    data: { user },
  } = await supabase.auth.getUser();
  redirect(roleFromUser(user) === "member" ? "/portal" : "/corpus");
}

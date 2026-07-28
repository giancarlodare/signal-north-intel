"use server";
// Stage-4 checkout action. Test mode by construction (key guard); billing
// dark (no config) is a silent no-op back to the account page.
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { createCheckoutUrl } from "@/lib/billing/stripe";
import type { Tier } from "@/lib/billing/config";

export async function startCheckout(formData: FormData) {
  const tier = String(formData.get("tier") ?? "") as Tier;
  if (!["weekly", "pro", "founding"].includes(tier)) return;
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return;
  const h = headers();
  const origin =
    h.get("origin") ??
    `https://${h.get("x-forwarded-host") ?? h.get("host") ?? ""}`;
  const url = await createCheckoutUrl(user.id, user.email ?? null, tier, origin);
  if (url) redirect(url);
  redirect("/portal/account?checkout=unavailable");
}

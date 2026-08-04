"use server";
// Checkout-first (operator 2026-08-03, change A). The PUBLIC action behind
// "Join Weekly": it opens Stripe Checkout for someone with NO account and no
// session. The account does not exist yet; the webhook provisions it from the
// email Checkout collects. Nothing here creates a session, and the only thing
// chosen before Stripe is the term, because hosted Checkout has no in-session
// interval toggle.
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { createAnonymousCheckoutUrl } from "@/lib/billing/stripe";
import type { Interval } from "@/lib/billing/config";

export async function startAnonymousCheckout(formData: FormData) {
  const raw = String(formData.get("interval") ?? "annual");
  // Annual is the headline term and the default: an unrecognised value falls
  // back to it rather than erroring.
  const interval: Interval = raw === "monthly" ? "monthly" : "annual";
  const h = headers();
  const origin =
    h.get("origin") ??
    `https://${h.get("x-forwarded-host") ?? h.get("host") ?? ""}`;
  const url = await createAnonymousCheckoutUrl("weekly", origin, interval);
  // A real URL opens Checkout. Billing dark (test key refused, no price wired)
  // returns null, and the visitor is sent back to pricing with an honest note
  // rather than a dead button.
  if (url) redirect(url);
  redirect("/pricing?checkout=unavailable");
}

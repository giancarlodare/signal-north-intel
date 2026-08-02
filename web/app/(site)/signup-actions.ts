"use server";
// The two PUBLIC actions on the marketing site (operator 2026-08-02). Kept in
// one file because the thing worth seeing at a glance is that they stay
// SEPARATE:
//
//   captureFreeSignup   an address on the partial-send list. Touches
//                       brief_signups and nothing else. Creates no account,
//                       no session, and no entitlement.
//   startWeeklySignup   a real account. Calls Supabase with
//                       shouldCreateUser: true and emails a confirm link that
//                       lands on /portal/account, where checkout lives.
//
// WHY OPENING SIGNUP IS SAFE NOW (operator's sequencing, 2026-08-02):
// shouldCreateUser: false was the right call while the portal had no paywall,
// because a self-created account would then have read everything for free.
// The guard merged in #133 is what replaces it. A new account with no
// subscription reaches /portal/account and nothing else, so account creation
// now grants exactly what it should: the ability to become a customer.
//
// CONFIRM BEFORE PAY (operator, standing): the product is delivered by email,
// so an unverified address means someone pays for a brief that never arrives.
// The account is created by the link click, not by the form post, and Stripe
// is never reached before that.
import { headers } from "next/headers";
import { createClient } from "@/lib/supabase/server";
import {
  validateFreeSignup,
  validateWeeklySignup,
  SIGNUP_DESTINATION,
} from "@/lib/site/signup";

export interface SignupResult {
  ok: boolean;
  message: string;
}

// Where the emailed link lands (app/auth/confirm/route.ts), carrying the
// destination so a confirmed signup arrives at checkout rather than the
// portal index.
function confirmUrl(): string {
  const h = headers();
  const origin =
    h.get("origin") ??
    `https://${h.get("x-forwarded-host") ?? h.get("host") ?? ""}`;
  return `${origin}/auth/confirm?next=${encodeURIComponent(SIGNUP_DESTINATION)}`;
}

const FREE_THANKS =
  "You are on the list. The next free brief goes out with your name on it.";

export async function captureFreeSignup(
  _prev: SignupResult | null,
  formData: FormData,
): Promise<SignupResult> {
  const v = validateFreeSignup({
    email: String(formData.get("email") ?? ""),
    source: String(formData.get("source") ?? ""),
    website: String(formData.get("website") ?? ""),
  });

  if (!v.ok) {
    // The honeypot path returns the SUCCESS message on purpose: a bot that
    // learns it was caught adapts. A human never sees this branch, because a
    // human never fills a field they cannot see.
    if (v.error === "rejected") return { ok: true, message: FREE_THANKS };
    return { ok: false, message: v.error };
  }

  const supabase = createClient();
  const { error } = await supabase.from("brief_signups").insert(v.row);

  if (error) {
    // 23505 is the unique violation on `email`: this address is already on the
    // list. That is the SAME OUTCOME the visitor asked for, so it is a
    // success, and saying so also means the form cannot be used to test
    // whether a given address is already subscribed.
    if (error.code === "23505") return { ok: true, message: FREE_THANKS };
    // Anything else is LOUD, not silent-success. A capture that quietly drops
    // the address tells the operator the list is smaller than the demand.
    console.error("[free-signup] insert failed:", error.message);
    return {
      ok: false,
      message:
        "We could not add you just now. Please try again, or email us and we will do it by hand.",
    };
  }

  return { ok: true, message: FREE_THANKS };
}

export async function startWeeklySignup(
  _prev: SignupResult | null,
  formData: FormData,
): Promise<SignupResult> {
  const v = validateWeeklySignup({
    email: String(formData.get("email") ?? ""),
    website: String(formData.get("website") ?? ""),
  });

  // Identical message on every path below, deliberately. See the note on the
  // return value.
  const sent =
    "Check your email. We have sent a link that confirms your address and takes you to checkout. It expires shortly, so use it soon.";

  if (!v.ok) {
    if (v.error === "rejected") return { ok: true, message: sent };
    return { ok: false, message: v.error };
  }

  const supabase = createClient();
  // shouldCreateUser: true is the whole change. An address with no account
  // gets one; an address that already has one is simply signed in and taken
  // to the same place. Both are correct outcomes for someone pressing "Join
  // Weekly", which is why the result is not branched on.
  const { error } = await supabase.auth.signInWithOtp({
    email: v.email,
    options: { emailRedirectTo: confirmUrl(), shouldCreateUser: true },
  });

  if (error) {
    // Rate limiting is the common case here (Supabase throttles per address).
    // Reported honestly rather than shown as a sent link that never arrives:
    // a false "check your email" is the same defect class as a swallowed
    // error, and it strands someone who was trying to pay us.
    console.error("[weekly-signup] otp failed:", error.message);
    return {
      ok: false,
      message:
        "We could not send that link just now. Wait a minute and try again.",
    };
  }

  // NO USER ENUMERATION: the success text never says whether the address was
  // new or already known. Both cases send mail and both read the same.
  return { ok: true, message: sent };
}

"use server";
// Tier-inquiry capture (operator 2026-08-01). The ONLY write path for the two
// closed pricing columns.
//
// Runs server-side against the anon client, so the insert is governed by the
// tier_inquiries RLS policy (anon may INSERT, nobody but the operator may
// SELECT). The database is the gate; this action is validation and shaping.
//
// It confers NOTHING. No Stripe product, no price, no checkout, no access.
// An Enterprise deal is invoiced by hand the day it closes and portal access
// is provisioned manually, so a row here is a lead, never an entitlement.
import { createClient } from "@/lib/supabase/server";
import { validateInquiry, type InquiryInput } from "@/lib/site/inquiry";

export interface InquiryResult {
  ok: boolean;
  message: string;
}

export async function submitInquiry(
  _prev: InquiryResult | null,
  formData: FormData,
): Promise<InquiryResult> {
  const input: InquiryInput = {
    tier: String(formData.get("tier") ?? ""),
    email: String(formData.get("email") ?? ""),
    companyName: String(formData.get("company_name") ?? ""),
    needs: String(formData.get("needs") ?? ""),
    seatCount: String(formData.get("seat_count") ?? ""),
    timeline: String(formData.get("timeline") ?? ""),
    website: String(formData.get("website") ?? ""),
  };

  const v = validateInquiry(input);
  if (!v.ok) {
    // The honeypot path returns the SUCCESS message on purpose: a bot that
    // learns it was caught adapts. A human never sees this branch, because a
    // human never fills a field they cannot see.
    if (v.error === "rejected") {
      return { ok: true, message: "Thank you. We will be in touch." };
    }
    return { ok: false, message: v.error };
  }

  const supabase = createClient();
  const { error } = await supabase.from("tier_inquiries").insert(v.row);
  if (error) {
    // LOUD, not silent-success. A capture that quietly drops the lead is the
    // demand instrument lying to the operator about demand.
    console.error("[inquiry] insert failed:", error.message);
    return {
      ok: false,
      message:
        "We could not record that. Please email us directly and we will pick it up.",
    };
  }

  return {
    ok: true,
    message:
      v.row.tier === "enterprise"
        ? "Thank you. We will read this and reply personally."
        : "Thank you. We will let you know the moment Pro opens.",
  };
}

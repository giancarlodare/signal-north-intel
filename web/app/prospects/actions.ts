"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";
import { INTERACTION_TYPES, STATUSES, TIERS, WAVES } from "./constants";

// Status changes only — there is deliberately NO delete action anywhere in
// this UI (and no DELETE grant in the DB for the authenticated role).
export async function updateStatus(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const status = String(formData.get("status") ?? "");
  if (!id || !(STATUSES as readonly string[]).includes(status)) return;
  const supabase = createClient();
  await supabase.from("prospects").update({ status }).eq("id", id);
  revalidatePath(`/prospects/${id}`);
  revalidatePath("/prospects");
}

// Tier, wave, and the reference-candidate star in one update, enum-validated
// like updateStatus. An unchecked checkbox posts nothing, so absence = false.
export async function updateClassification(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const tier = String(formData.get("tier") ?? "");
  const wave = Number(formData.get("wave") ?? "");
  if (!id) return;
  if (!(TIERS as readonly string[]).includes(tier)) return;
  if (!(WAVES as readonly number[]).includes(wave)) return;
  const isReference = formData.get("is_reference_candidate") === "on";
  const supabase = createClient();
  await supabase
    .from("prospects")
    .update({ tier, wave, is_reference_candidate: isReference })
    .eq("id", id);
  revalidatePath(`/prospects/${id}`);
  revalidatePath("/prospects");
}

export async function addInteraction(formData: FormData) {
  const prospectId = String(formData.get("prospect_id") ?? "");
  const summary = String(formData.get("summary") ?? "").trim();
  if (!prospectId || !summary) return;

  const type = String(formData.get("interaction_type") ?? "note");
  const occurredOn = String(formData.get("occurred_on") ?? "");
  const followUp = String(formData.get("follow_up") ?? "").trim();
  const followUpDue = String(formData.get("follow_up_due") ?? "");

  const supabase = createClient();
  await supabase.from("prospect_interactions").insert({
    prospect_id: prospectId,
    summary,
    interaction_type: (INTERACTION_TYPES as readonly string[]).includes(type)
      ? type
      : "note",
    // Empty date inputs must become null/omitted, not "" (invalid for date).
    ...(occurredOn ? { occurred_on: occurredOn } : {}),
    follow_up: followUp || null,
    follow_up_due: followUpDue || null,
  });
  revalidatePath(`/prospects/${prospectId}`);
}

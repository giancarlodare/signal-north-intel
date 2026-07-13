"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { reviewNotePayload } from "@/lib/reviewNote.mjs";

// Approve/reject both mark the signal reviewed=true; the outcome and any note
// are recorded in review_note. reviewed_by='human' records that a person
// eyeballed it, distinct from the triage engine's 'triage@v1' auto-approvals.
// The exact update payload comes from reviewNotePayload so every path (single
// and bulk, approve and reject) writes identical fields.
export async function approve(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();
  await supabase.from("signals").update(reviewNotePayload("approve")).eq("id", id);
  revalidatePath("/review");
}

export async function reject(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const note = String(formData.get("note") ?? "");
  const supabase = createClient();
  await supabase
    .from("signals")
    .update(reviewNotePayload("reject", note))
    .eq("id", id);
  revalidatePath("/review");
}

// Bulk approve/reject: the desktop reviewer selects many signals and clears
// them in one action. Same per-row effect as approve/reject above, applied to
// an explicit list of ids -- never to a whole filter blindly, so what gets
// written is exactly what the reviewer checked. reviewed_by='human' (a person
// made the call, even in bulk).
function parseIds(formData: FormData): string[] {
  // Checkbox inputs all named "ids"; FormData.getAll returns each checked one.
  return formData
    .getAll("ids")
    .map((v) => String(v))
    .filter((v) => v.length > 0);
}

export async function approveMany(formData: FormData) {
  const ids = parseIds(formData);
  if (ids.length === 0) return;
  const supabase = createClient();
  await supabase.from("signals").update(reviewNotePayload("approve")).in("id", ids);
  revalidatePath("/review");
}

export async function rejectMany(formData: FormData) {
  const ids = parseIds(formData);
  if (ids.length === 0) return;
  const note = String(formData.get("note") ?? "");
  const supabase = createClient();
  await supabase
    .from("signals")
    .update(reviewNotePayload("reject", note))
    .in("id", ids);
  revalidatePath("/review");
}

export async function signOut() {
  const supabase = createClient();
  await supabase.auth.signOut();
  redirect("/login");
}

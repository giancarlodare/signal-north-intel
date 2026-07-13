"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

// Confirm / reject / merge a proposed procurement. Deliberate buttons, never a
// delete: rejection and merge are non-destructive status changes, matching the
// review, prospects, and discovery pages. The proposer (service_role) never
// confirms its own proposals; only these actions do.

const STAGES = [1, 2, 3, 4, 5];

export async function confirmProcurement(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();
  await supabase
    .from("procurements")
    .update({ status: "confirmed", reviewed_at: new Date().toISOString() })
    .eq("id", id)
    .eq("status", "proposed");
  revalidatePath("/procurements");
}

export async function rejectProcurement(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const note = String(formData.get("note") ?? "").trim();
  if (!id) return;
  const supabase = createClient();
  await supabase
    .from("procurements")
    .update({
      status: "rejected",
      review_note: note || null,
      reviewed_at: new Date().toISOString(),
    })
    .eq("id", id)
    .eq("status", "proposed");
  revalidatePath("/procurements");
}

// Merge one procurement into another: the duplicate is marked merged and points
// at the survivor. Non-destructive. The DB check constraint requires
// merged_into_id to be set exactly when status is merged.
export async function mergeProcurement(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const into = String(formData.get("merged_into_id") ?? "");
  if (!id || !into || id === into) return;
  const supabase = createClient();

  // Move the duplicate's active signal links onto the survivor, skipping any
  // the survivor already has, then mark the duplicate merged.
  const { data: dupLinks } = await supabase
    .from("procurement_signals")
    .select("signal_id")
    .eq("procurement_id", id)
    .eq("active", true);
  const { data: survivorLinks } = await supabase
    .from("procurement_signals")
    .select("signal_id")
    .eq("procurement_id", into);
  const have = new Set((survivorLinks ?? []).map((l) => l.signal_id));
  const toAdd = (dupLinks ?? [])
    .map((l) => l.signal_id)
    .filter((sid) => !have.has(sid));
  if (toAdd.length > 0) {
    await supabase
      .from("procurement_signals")
      .insert(toAdd.map((sid) => ({ procurement_id: into, signal_id: sid, linked_by: "human" })));
  }

  await supabase
    .from("procurements")
    .update({
      status: "merged",
      merged_into_id: into,
      reviewed_at: new Date().toISOString(),
    })
    .eq("id", id)
    .eq("status", "proposed");
  revalidatePath("/procurements");
}

// Edit the reviewer-owned fields: title, scope, and the current stage. The
// proposer never touches these once a human has set them.
export async function editProcurement(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const title = String(formData.get("title") ?? "").trim();
  const scope = String(formData.get("scope") ?? "").trim();
  const stageRaw = Number(formData.get("current_stage"));
  const patch: Record<string, unknown> = {};
  if (title) patch.title = title.slice(0, 500);
  patch.scope = scope || null;
  if (STAGES.includes(stageRaw)) patch.current_stage = stageRaw;
  if (Object.keys(patch).length === 0) return;
  const supabase = createClient();
  await supabase.from("procurements").update(patch).eq("id", id);
  revalidatePath("/procurements");
}

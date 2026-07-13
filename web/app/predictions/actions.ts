"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

// Author a frozen prediction from a procurement, and confirm a reconciliation
// outcome. Predictions are immutable: the database computes made_at and
// claim_hash in a trigger and blocks any later edit, so this action only ever
// INSERTS a claim. Nothing here is a delete.

const MIN_RUNG = 3;
const MAX_RUNG = 5;

type SnapSignal = {
  id: string;
  evidence_grade: number | null;
  title: string | null;
  documents: { id: string; url: string | null; published_on: string | null }
    | { id: string; url: string | null; published_on: string | null }[]
    | null;
};

function one<T>(v: T | T[] | null): T | null {
  return Array.isArray(v) ? v[0] ?? null : v ?? null;
}

export async function authorPrediction(formData: FormData) {
  const procurementId = String(formData.get("procurement_id") ?? "");
  const predictedRung = Number(formData.get("predicted_rung"));
  const horizonMonths = Number(formData.get("horizon_months"));
  const rationale = String(formData.get("rationale") ?? "").trim();
  if (!procurementId || !rationale) return;
  // Q4: a claim must predict commitment or higher.
  if (!(predictedRung >= MIN_RUNG && predictedRung <= MAX_RUNG)) return;
  if (!(horizonMonths > 0 && horizonMonths <= 60)) return;

  const supabase = createClient();

  // The claim's subject must be a real (confirmed) opportunity.
  const { data: proc } = await supabase
    .from("procurements")
    .select("id, status")
    .eq("id", procurementId)
    .maybeSingle();
  if (!proc || proc.status !== "confirmed") return;

  // Freeze the evidence AS IT IS NOW: the procurement's active linked signals.
  const { data: links } = await supabase
    .from("procurement_signals")
    .select("signals(id, evidence_grade, title, documents(id, url, published_on))")
    .eq("procurement_id", procurementId)
    .eq("active", true);

  const evidenceSnapshot: Array<Record<string, unknown>> = [];
  const evidenceSignalIds: string[] = [];
  for (const l of links ?? []) {
    const s = one(l.signals as SnapSignal | SnapSignal[] | null);
    if (!s) continue;
    const doc = one(s.documents);
    evidenceSignalIds.push(s.id);
    evidenceSnapshot.push({
      signal_id: s.id,
      evidence_grade: s.evidence_grade,
      title: s.title,
      document_id: doc?.id ?? null,
      document_url: doc?.url ?? null,
      published_on: doc?.published_on ?? null,
    });
  }
  // A claim cannot exist without public evidence (the provenance rule).
  if (evidenceSignalIds.length === 0) return;

  // horizon_ends_on from today; made_at and claim_hash are set by the DB.
  const ends = new Date();
  ends.setMonth(ends.getMonth() + horizonMonths);

  await supabase.from("predictions").insert({
    subject_kind: "procurement",
    subject_procurement_id: procurementId,
    predicted_rung: predictedRung,
    horizon_months: horizonMonths,
    horizon_ends_on: ends.toISOString().slice(0, 10),
    rationale: rationale.slice(0, 4000),
    evidence_signal_ids: evidenceSignalIds,
    evidence_snapshot: evidenceSnapshot,
    gated: false, // procurement-level: seller-facing. Company-level would gate.
  });
  revalidatePath("/predictions");
}

export async function confirmOutcome(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();
  await supabase
    .from("prediction_outcomes")
    .update({ status: "confirmed", confirmed_at: new Date().toISOString() })
    .eq("id", id)
    .eq("status", "proposed");
  revalidatePath("/predictions");
}

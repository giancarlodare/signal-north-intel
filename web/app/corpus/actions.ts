"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

// The one editorial write on /corpus: hide a clearly-wrong or off-topic signal.
// Non-destructive and reversible (the row stays; it is only excluded from the
// live corpus, the proposer, and the brief). Stamps suppressed_by='human', the
// counterpart to the triage engine's 'triage@v1'. This never deletes and never
// touches the ledger.
export async function suppressSignal(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const reason = String(formData.get("reason") ?? "").trim();
  const supabase = createClient();
  await supabase
    .from("signals")
    .update({
      suppressed: true,
      suppressed_reason: reason ? `human: ${reason}` : "human",
      suppressed_by: "human",
    })
    .eq("id", id);
  revalidatePath("/corpus");
}

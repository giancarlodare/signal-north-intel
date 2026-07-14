"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

// The /brief editor's writes. The generator produces a draft; the operator edits
// here (cut items, reorder, add copy) and publishes. Nothing here authors a
// prediction or touches a signal: the brief is an editorial artifact over the
// corpus. A published brief is frozen (publish only ever flips draft->published).

export async function setBriefMeta(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();
  await supabase
    .from("briefs")
    .update({
      title: String(formData.get("title") ?? "").slice(0, 300),
      intro: String(formData.get("intro") ?? "").slice(0, 4000),
    })
    .eq("id", id)
    .eq("status", "draft"); // never edit a published brief
  revalidatePath("/brief");
}

export async function saveItem(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const rankRaw = String(formData.get("rank") ?? "");
  const rank = rankRaw === "" ? null : Number(rankRaw);
  const supabase = createClient();
  await supabase
    .from("brief_items")
    .update({
      included: formData.get("included") === "on",
      rank: Number.isFinite(rank as number) ? rank : null,
      headline_override: String(formData.get("headline_override") ?? "").slice(0, 300) || null,
      editor_note: String(formData.get("editor_note") ?? "").slice(0, 2000) || null,
    })
    .eq("id", id);
  revalidatePath("/brief");
}

export async function publishBrief(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();
  // Freeze: only a draft can be published, and published_at is set once.
  await supabase
    .from("briefs")
    .update({ status: "published", published_at: new Date().toISOString() })
    .eq("id", id)
    .eq("status", "draft");
  revalidatePath("/brief");
}

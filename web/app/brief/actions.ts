"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";
import { buildBriefView } from "@/lib/brief/view";
import { renderBrief, renderBriefText } from "@/lib/brief/render";

// Pre-gate: the brief is emailed to the operator only. No list, no capture.
const RECIPIENT = "giancarlo97dare@gmail.com";
// onboarding@resend.dev sends to the account owner's address without a verified
// domain, so this ships now; a holdco-domain sender replaces it post-gate.
const SENDER = "The Weekly Signal <onboarding@resend.dev>";

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

// Email a PUBLISHED brief to the operator via Resend. Publish freezes the
// content; Send is a deliberate second step so the brief is reviewed in its
// published form first. Idempotent: refuses if `sent_at` is already set, so a
// double-click or re-open cannot double-send. Returns { ok, error } for the UI.
export async function sendBriefEmail(formData: FormData): Promise<void> {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();

  const { data: b } = await supabase
    .from("briefs")
    .select("id, week_start, status, sent_at")
    .eq("id", id)
    .maybeSingle();
  if (!b || b.status !== "published" || b.sent_at) return; // not sendable / already sent

  const view = await buildBriefView(supabase, b.week_start);
  if (!view) return;

  const key = process.env.RESEND_API_KEY;
  if (!key) {
    console.error("sendBriefEmail: RESEND_API_KEY is not set");
    return;
  }
  const resp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({
      from: SENDER,
      to: [RECIPIENT],
      subject: `${view.masthead}: week of ${view.weekLabel}`,
      html: renderBrief(view),
      text: renderBriefText(view),
    }),
  });
  if (!resp.ok) {
    console.error("sendBriefEmail: Resend returned", resp.status, await resp.text());
    return;
  }
  // Stamp the send only after Resend accepted it; guard against a race.
  await supabase
    .from("briefs")
    .update({ sent_at: new Date().toISOString() })
    .eq("id", id)
    .is("sent_at", null);
  revalidatePath("/brief");
}

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

export type SendState = { ok: boolean; message: string };

// Email a PUBLISHED brief to the operator via Resend. Publish freezes the
// content; Send is a deliberate second step. Idempotent: refuses if `sent_at`
// is already set. Returns a typed result for EVERY path so a dead click can
// never look like a working one (the button surfaces the exact reason). Shaped
// for useFormState: (prevState, formData).
export async function sendBriefEmail(_prev: SendState | null, formData: FormData): Promise<SendState> {
  const id = String(formData.get("id") ?? "");
  if (!id) return { ok: false, message: "No brief id." };
  const supabase = createClient();

  const { data: b } = await supabase
    .from("briefs")
    .select("id, week_start, status, sent_at")
    .eq("id", id)
    .maybeSingle();
  if (!b) return { ok: false, message: "Brief not found." };
  if (b.status !== "published") return { ok: false, message: "Publish the brief before sending." };
  if (b.sent_at) return { ok: false, message: `Already emailed on ${String(b.sent_at).slice(0, 10)}.` };

  const view = await buildBriefView(supabase, b.week_start);
  if (!view) return { ok: false, message: "Could not assemble the brief view." };

  const key = process.env.RESEND_API_KEY;
  if (!key) {
    return { ok: false, message: "RESEND_API_KEY is not set on the server. Set it in the Vercel env, then redeploy." };
  }

  let resp: Response;
  try {
    resp = await fetch("https://api.resend.com/emails", {
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
  } catch (e) {
    return { ok: false, message: `Network error calling Resend: ${String(e).slice(0, 140)}` };
  }
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    return { ok: false, message: `Resend rejected the send (HTTP ${resp.status}): ${body.slice(0, 180)}` };
  }

  // Stamp the send only after Resend accepted it; guard the race.
  await supabase.from("briefs").update({ sent_at: new Date().toISOString() })
    .eq("id", id).is("sent_at", null);
  revalidatePath("/brief");
  return { ok: true, message: `Emailed to ${RECIPIENT}.` };
}

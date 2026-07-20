"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";
import { buildBriefView } from "@/lib/brief/view";
import { renderBrief, renderBriefText } from "@/lib/brief/render";

// Pre-gate: the brief is emailed to the operator only. No list, no capture.
// BRIEF_RECIPIENT (Vercel env) overrides the destination so pointing this at a
// real subscriber list later is a settings change, not a code change. The
// default is the Resend ACCOUNT email: Resend test mode only delivers to the
// account owner, so any other default (e.g. a personal gmail) fails silently.
const RECIPIENT = process.env.BRIEF_RECIPIENT || "giancarlo@signalnorthintel.com";
// Sends from the verified signalnorthintel.com domain (verified in Resend
// 2026-07-20; the onboarding@resend.dev placeholder is retired). With a
// verified domain Resend can deliver to any recipient, so BRIEF_RECIPIENT
// controls the destination.
const SENDER = "The Weekly Signal <signal@signalnorthintel.com>";

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
    // TEMP DIAGNOSTIC: tell the operator WHY the key is invisible without ever
    // printing it. Reports the runtime (env access differs on Edge), which
    // Vercel environment this deployment is (a Production-only var is absent
    // from Preview/branch deploys), whether the var is present at all, and the
    // NAMES of any RESEND-ish keys the server can see (to catch a typo/rename).
    const runtime = process.env.NEXT_RUNTIME ?? "unknown";
    const vercelEnv = process.env.VERCEL_ENV ?? "not-on-vercel";
    const raw = process.env.RESEND_API_KEY;
    const present = typeof raw === "string";
    const len = present ? raw.length : 0;
    const resendKeys = Object.keys(process.env).filter((k) => /resend/i.test(k));
    return {
      ok: false,
      message:
        "RESEND_API_KEY is not visible to the server. " +
        `[diag runtime=${runtime}, VERCEL_ENV=${vercelEnv}, ` +
        `present=${present}, length=${len}, ` +
        `resend-named keys=${resendKeys.length ? resendKeys.join("|") : "none"}] ` +
        "If VERCEL_ENV is preview, the key was set only for Production and this " +
        "is a branch/preview deploy: add it to the Preview scope (or merge to " +
        "the Production branch) and redeploy.",
    };
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

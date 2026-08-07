"use server";
// Stage-3 member actions. All writes run on the member's own session under
// RLS (owner-scoped), so a member can only ever touch their own rows. Errors
// are swallowed into a silent no-op pre-paste (tables absent) rather than
// crashing the portal; the pages render Pending states in that case anyway.
import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

async function me() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return { supabase, userId: user?.id ?? null };
}

function refresh() {
  revalidatePath("/portal");
  revalidatePath("/portal/watching");
  revalidatePath("/portal/saved");
  revalidatePath("/portal/brief");
}

export async function addKeywordWatch(formData: FormData) {
  const keyword = String(formData.get("keyword") ?? "").trim().toLowerCase();
  const { supabase, userId } = await me();
  if (!keyword || !userId) return;
  const { data } = await supabase
    .from("member_watches")
    .insert({ member_id: userId, kind: "keyword", keyword })
    .select("id")
    .single();
  if (data?.id) {
    // The member's own 'follow' record (the only event type RLS lets a
    // member append); match/backfill events come from the daily matcher.
    await supabase.from("watch_events").insert({
      member_id: userId,
      watch_id: data.id,
      event_type: "follow",
      detail: `You started watching "${keyword}".`,
    });
  }
  refresh();
}

export async function removeWatch(formData: FormData) {
  const id = String(formData.get("watch_id") ?? "");
  const { supabase, userId } = await me();
  if (!id || !userId) return;
  // D1: events survive the unfollow (watch_id set null by the FK).
  await supabase.from("member_watches").delete().eq("id", id);
  refresh();
}

export async function followBuyer(formData: FormData) {
  const orgId = String(formData.get("organization_id") ?? "");
  const name = String(formData.get("buyer_name") ?? "");
  const { supabase, userId } = await me();
  if (!orgId || !userId) return;
  const { data } = await supabase
    .from("member_watches")
    .insert({ member_id: userId, kind: "buyer", organization_id: orgId })
    .select("id")
    .single();
  if (data?.id) {
    await supabase.from("watch_events").insert({
      member_id: userId,
      watch_id: data.id,
      event_type: "follow",
      detail: `You followed ${name || "a buyer"}.`,
    });
  }
  refresh();
}

export async function saveItem(formData: FormData) {
  const briefItemId = String(formData.get("brief_item_id") ?? "");
  const { supabase, userId } = await me();
  if (!briefItemId || !userId) return;
  await supabase
    .from("saved_items")
    .insert({ member_id: userId, brief_item_id: briefItemId });
  refresh();
}

export async function unsaveItem(formData: FormData) {
  const briefItemId = String(formData.get("brief_item_id") ?? "");
  const { supabase, userId } = await me();
  if (!briefItemId || !userId) return;
  await supabase
    .from("saved_items")
    .delete()
    .eq("brief_item_id", briefItemId)
    .eq("member_id", userId);
  refresh();
}

export async function dismissOnboarding() {
  const supabase = createClient();
  // Merges into user_metadata; does not clear existing fields.
  await supabase.auth.updateUser({ data: { onboarding_dismissed: true } });
  revalidatePath("/portal");
}

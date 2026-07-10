"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

// Approve/reject both mark the signal reviewed=true; the outcome and any note
// are recorded in review_note. (There's no separate signal status column; a
// dedicated one can be added later if the workflow needs more states.)
export async function approve(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();
  await supabase
    .from("signals")
    .update({ reviewed: true, review_note: "approved" })
    .eq("id", id);
  revalidatePath("/review");
}

export async function reject(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const note = String(formData.get("note") ?? "").trim();
  const supabase = createClient();
  await supabase
    .from("signals")
    .update({
      reviewed: true,
      review_note: note ? `rejected: ${note}` : "rejected",
    })
    .eq("id", id);
  revalidatePath("/review");
}

export async function signOut() {
  const supabase = createClient();
  await supabase.auth.signOut();
  redirect("/login");
}

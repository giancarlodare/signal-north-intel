"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

// Shared auth action for every page's topbar. Lived in review/actions.ts until
// the review queue was retired (editorial model, Phase 2); moved here so it
// outlives that page.
export async function signOut() {
  const supabase = createClient();
  await supabase.auth.signOut();
  redirect("/login");
}

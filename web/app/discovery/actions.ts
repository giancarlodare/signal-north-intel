"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";
import { JURISDICTIONS, ORG_TYPES } from "./constants";

// Approve/reject only — proposals are never deleted (rejection is permanent
// suppression), and nothing here triggers collection: an approved source's
// collector still lands via a reviewed PR.

export async function approveSource(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();

  const { data: proposal } = await supabase
    .from("discovered_sources")
    .select("id, domain, suggested_name, kind, status")
    .eq("id", id)
    .maybeSingle();
  if (!proposal || proposal.status !== "proposed") return;

  const { data: created, error } = await supabase
    .from("sources")
    .insert({
      name: proposal.suggested_name,
      url: `https://${proposal.domain}/`,
    })
    .select("id")
    .maybeSingle();
  if (error || !created) return;

  await supabase
    .from("discovered_sources")
    .update({
      status: "approved",
      reviewed_at: new Date().toISOString(),
      created_source_id: created.id,
    })
    .eq("id", id);
  revalidatePath("/discovery");
}

export async function approveEntity(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();

  const { data: proposal } = await supabase
    .from("discovered_entities")
    .select("id, entity_kind, name, detail, existing_organization_id, status")
    .eq("id", id)
    .maybeSingle();
  if (!proposal || proposal.status !== "proposed") return;

  if (proposal.entity_kind === "organization") {
    const orgType = String(formData.get("org_type") ?? "");
    const jurisdiction = String(formData.get("jurisdiction") ?? "");
    if (
      !(ORG_TYPES as readonly string[]).includes(orgType) ||
      !(JURISDICTIONS as readonly string[]).includes(jurisdiction)
    )
      return;
    const { error } = await supabase.from("organizations").insert({
      canonical_name: proposal.name,
      aliases: [proposal.name],
      org_type: orgType,
      jurisdiction,
    });
    if (error) return;
  } else if (proposal.entity_kind === "alias_update") {
    if (!proposal.existing_organization_id) return;
    const { data: org } = await supabase
      .from("organizations")
      .select("aliases")
      .eq("id", proposal.existing_organization_id)
      .maybeSingle();
    if (!org) return;
    const aliases: string[] = Array.from(
      new Set([...(org.aliases ?? []), proposal.name])
    );
    const { error } = await supabase
      .from("organizations")
      .update({ aliases })
      .eq("id", proposal.existing_organization_id);
    if (error) return;
  }
  // person_appointment / company_canada_intent: approval just marks reviewed —
  // intelligence, not rows. company_canada_intent then offers the separate
  // one-tap "add to prospects" second action below.

  await supabase
    .from("discovered_entities")
    .update({ status: "approved", reviewed_at: new Date().toISOString() })
    .eq("id", id);
  revalidatePath("/discovery");
}

// The §8-approved second explicit action: an APPROVED company_canada_intent
// proposal can be added to the prospects pipeline (never automatically).
export async function addToProspects(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  if (!id) return;
  const supabase = createClient();

  const { data: proposal } = await supabase
    .from("discovered_entities")
    .select("id, entity_kind, name, detail, status")
    .eq("id", id)
    .maybeSingle();
  if (
    !proposal ||
    proposal.entity_kind !== "company_canada_intent" ||
    proposal.status !== "approved"
  )
    return;

  const summary =
    (proposal.detail as { summary?: string } | null)?.summary ?? "";
  await supabase.from("prospects").upsert(
    {
      company_name: proposal.name,
      category: "other",
      tier: "watch_only",
      notes: `Via discovery (${new Date().toISOString().slice(0, 10)}): ${summary}`.slice(0, 1000),
    },
    { onConflict: "company_name", ignoreDuplicates: true }
  );
  revalidatePath("/discovery");
  revalidatePath("/prospects");
}

export async function rejectProposal(formData: FormData) {
  const id = String(formData.get("id") ?? "");
  const table = String(formData.get("table") ?? "");
  if (!id || (table !== "discovered_sources" && table !== "discovered_entities"))
    return;
  const supabase = createClient();
  await supabase
    .from(table)
    .update({ status: "rejected", reviewed_at: new Date().toISOString() })
    .eq("id", id)
    .eq("status", "proposed");
  revalidatePath("/discovery");
}

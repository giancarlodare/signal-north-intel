// Wave 3 stage 2: the member-filtered dashboard DATA LAYER.
//
// PRINCIPLE (inherited from stage 1): the RLS policies are the gate. A member
// session physically cannot read anything but published + gate-cleared rows,
// so this layer does NOT re-implement the gate for security. It queries
// normally and the database enforces the floor.
//
// It DOES add explicit published/included filters anyway, for two non-security
// reasons: (1) an OPERATOR previewing /portal would otherwise see every row
// (operator-all policy), so the explicit filters make the operator's preview
// faithful to what a member sees; (2) belt-and-suspenders clarity.
//
// PRESENTATION-AGNOSTIC: this file returns plain data (no JSX, no styling, no
// copy). The functional page renders it as an unstyled skeleton; Giancarlo's
// Claude Design files replace the presentation without touching this layer.

import type { SupabaseClient } from "@supabase/supabase-js";

export interface PublishedBriefRef {
  id: string;
  weekStart: string;        // ISO date
}

export interface PortalItem {
  itemId: string;
  headline: string;
  buyer: string | null;
  timingPath: "imminent" | "recent";
  defenceRelevant: boolean;
  eventDate: string | null;       // publisher doc's published_on
  datePrecision: string | null;   // 'day' | 'month' (renderer honours it)
  docType: string | null;         // drives the date TYPE label (§7.4)
  sourceUrl: string | null;       // provenance link
  referenceNumber: string | null; // the publisher's own record key, when printed
  vendorSoWhat: string | null;    // editor_note
  amountCad: number | null;
  rank: number;
}

function one<T>(v: T | T[] | null | undefined): T | null {
  return Array.isArray(v) ? v[0] ?? null : v ?? null;
}

// The list of published briefs a member may see, newest first.
export async function listPublishedBriefs(
  supabase: SupabaseClient,
): Promise<PublishedBriefRef[]> {
  const { data } = await supabase
    .from("briefs")
    .select("id, week_start, status")
    .eq("status", "published")
    .order("week_start", { ascending: false });
  return ((data ?? []) as { id: string; week_start: string }[]).map((b) => ({
    id: b.id,
    weekStart: b.week_start,
  }));
}

interface ItemRow {
  id: string;
  rank: number | null;
  timing_path: string | null;
  headline_override: string | null;
  editor_note: string | null;
  signals: {
    title: string | null;
    amount_max_cad: number | null;
    public_safety: boolean | null;
    organizations: { canonical_name: string | null } | { canonical_name: string | null }[] | null;
    // defence_relevant lives on DOCUMENTS (collectors stamp it there); the
    // signals table has no such column, and selecting one 400s the whole
    // query (the 2026-07-28 "0 items" incident).
    documents: {
      url: string | null;
      published_on: string | null;
      date_precision: string | null;
      doc_type: string | null;
      defence_relevant: boolean | null;
      reference_number: string | null;
    } | Record<string, unknown>[] | null;
  } | Record<string, unknown>[] | null;
}

// The included items of ONE published brief, as gate-cleared PortalItems.
export async function getBriefItems(
  supabase: SupabaseClient,
  briefId: string,
): Promise<PortalItem[]> {
  const { data, error } = await supabase
    .from("brief_items")
    .select(
      "id, rank, timing_path, headline_override, editor_note, included, " +
      "signals:lead_signal_id(title, amount_max_cad, public_safety, " +
      "organizations(canonical_name), " +
      "documents(url, published_on, date_precision, doc_type, defence_relevant, reference_number))",
    )
    .eq("brief_id", briefId)
    .eq("included", true)
    .order("rank", { ascending: true });
  if (error) {
    // LOUD FAILURE: a query error must never render as an honest-looking
    // "0 items" (the 2026-07-28 incident: a bad column name 400'd every
    // load and the empty-array fallback swallowed it for a full day).
    console.error("[portal-data] getBriefItems:", error.message);
    throw new Error(`getBriefItems(${briefId}): ${error.message}`);
  }

  return ((data ?? []) as unknown as ItemRow[])
    // Second barrier under the RLS clamp: even if an operator preview (which
    // bypasses RLS) or a future composition path surfaced a non-public-safety
    // item, the member dashboard shows only public-safety-relevant items. The
    // RLS sn_public_safety_clamp is the real gate for a member session; this
    // keeps the operator's preview faithful to what a member actually sees.
    .filter((it) => {
      const s = one(it.signals) as Record<string, unknown> | null;
      return Boolean(s?.public_safety);
    })
    .map((it) => {
    const s = one(it.signals) as Record<string, unknown> | null;
    const org = one((s?.organizations ?? null) as
      { canonical_name: string | null } | { canonical_name: string | null }[] | null);
    const doc = one((s?.documents ?? null) as
      Record<string, unknown> | Record<string, unknown>[] | null);
    return {
      itemId: it.id,
      headline: it.headline_override || ((s?.title as string) ?? "(untitled item)"),
      buyer: (org?.canonical_name as string) ?? null,
      timingPath: it.timing_path === "imminent" ? "imminent" : "recent",
      defenceRelevant: Boolean(doc?.defence_relevant),
      eventDate: (doc?.published_on as string) ?? null,
      datePrecision: (doc?.date_precision as string) ?? null,
      docType: (doc?.doc_type as string) ?? null,
      sourceUrl: (doc?.url as string) ?? null,
      referenceNumber: (doc?.reference_number as string) ?? null,
      vendorSoWhat: it.editor_note ?? null,
      amountCad: (s?.amount_max_cad as number) ?? null,
      rank: it.rank ?? 999,
    };
  });
}

// ---- Pure filter logic (unit-tested; no I/O) --------------------------------

export interface TagFilter {
  buyer?: string | null;
  timing?: "imminent" | "recent" | null;
  defenceOnly?: boolean;
}

// The distinct tag values present in a set of items, so the UI can render only
// chips that would actually match something (no dead filters).
export function availableTags(items: PortalItem[]): {
  buyers: string[];
  timings: ("imminent" | "recent")[];
  hasDefence: boolean;
} {
  const buyers = [...new Set(items.map((i) => i.buyer).filter((b): b is string => !!b))].sort();
  const timings = [...new Set(items.map((i) => i.timingPath))];
  return { buyers, timings, hasDefence: items.some((i) => i.defenceRelevant) };
}

export function filterItems(items: PortalItem[], f: TagFilter): PortalItem[] {
  return items.filter((i) => {
    if (f.buyer && i.buyer !== f.buyer) return false;
    if (f.timing && i.timingPath !== f.timing) return false;
    if (f.defenceOnly && !i.defenceRelevant) return false;
    return true;
  });
}

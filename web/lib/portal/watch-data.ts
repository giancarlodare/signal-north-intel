// Stage-3 member data: watches, the event log, saved items. RLS owner-scopes
// every query (a member reads only their own rows); these helpers add no
// security of their own. Every getter returns null when the stage-3 tables
// are not pasted yet, so the pages fall back to their Pending placeholders
// pre-paste and light up after.
import type { SupabaseClient } from "@supabase/supabase-js";

function one<T>(v: T | T[] | null | undefined): T | null {
  return Array.isArray(v) ? v[0] ?? null : v ?? null;
}

export interface Watch {
  id: string;
  kind: "keyword" | "buyer";
  keyword: string | null;
  organizationId: string | null;
  buyerName: string | null;
}

export interface WatchEvent {
  id: string;
  eventType: "match" | "backfill" | "follow";
  detail: string | null;
  createdAt: string;
  signalTitle: string | null;
  buyer: string | null;
}

export interface SavedItem {
  briefItemId: string;
  savedAt: string;
  headline: string | null;
  buyer: string | null;
}

export async function listWatches(
  supabase: SupabaseClient,
): Promise<Watch[] | null> {
  // No relationship embed here: this query drives the whole Watching page's
  // live/disabled state, so it stays a plain single-table select (embeds
  // depend on FK schema-cache resolution and are the fragile part on a
  // freshly created table). Buyer names resolve in a second plain query.
  const { data, error } = await supabase
    .from("member_watches")
    .select("id, kind, keyword, organization_id")
    .order("created_at", { ascending: true });
  if (error) {
    console.error("[watch-data] listWatches:", error.message);
    return null;
  }
  const rows = (data ?? []) as unknown as Record<string, unknown>[];
  const orgIds = [...new Set(rows.map((w) => w.organization_id as string).filter(Boolean))];
  const names = new Map<string, string>();
  if (orgIds.length) {
    const { data: orgs, error: orgErr } = await supabase
      .from("organizations")
      .select("id, canonical_name")
      .in("id", orgIds);
    if (orgErr) console.error("[watch-data] org names:", orgErr.message);
    for (const o of (orgs ?? []) as { id: string; canonical_name: string | null }[])
      if (o.canonical_name) names.set(o.id, o.canonical_name);
  }
  return rows.map((w) => ({
    id: w.id as string,
    kind: w.kind as "keyword" | "buyer",
    keyword: (w.keyword as string) ?? null,
    organizationId: (w.organization_id as string) ?? null,
    buyerName: names.get(w.organization_id as string) ?? null,
  }));
}

export async function listEvents(
  supabase: SupabaseClient,
  limit = 12,
): Promise<WatchEvent[] | null> {
  const { data, error } = await supabase
    .from("watch_events")
    .select(
      "id, event_type, detail, created_at, " +
        "signals(title, organizations(canonical_name))",
    )
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) {
    console.error("[watch-data] listEvents:", error.message);
    return null;
  }
  return ((data ?? []) as unknown as Record<string, unknown>[]).map((e) => {
    const s = one(e.signals as Record<string, unknown> | Record<string, unknown>[] | null);
    const org = one(
      (s?.organizations ?? null) as
        { canonical_name: string | null } | { canonical_name: string | null }[] | null,
    );
    return {
      id: e.id as string,
      eventType: e.event_type as WatchEvent["eventType"],
      detail: (e.detail as string) ?? null,
      createdAt: e.created_at as string,
      signalTitle: (s?.title as string) ?? null,
      buyer: (org?.canonical_name as string) ?? null,
    };
  });
}

export async function listSaved(
  supabase: SupabaseClient,
): Promise<SavedItem[] | null> {
  const { data, error } = await supabase
    .from("saved_items")
    .select(
      "brief_item_id, saved_at, " +
        "brief_items(headline_override, signals:lead_signal_id(title, " +
        "organizations(canonical_name)))",
    )
    .order("saved_at", { ascending: false });
  if (error) {
    console.error("[watch-data] listSaved:", error.message);
    return null;
  }
  return ((data ?? []) as unknown as Record<string, unknown>[]).map((r) => {
    const bi = one(r.brief_items as Record<string, unknown> | Record<string, unknown>[] | null);
    const s = one((bi?.signals ?? null) as Record<string, unknown> | Record<string, unknown>[] | null);
    const org = one(
      (s?.organizations ?? null) as
        { canonical_name: string | null } | { canonical_name: string | null }[] | null,
    );
    return {
      briefItemId: r.brief_item_id as string,
      savedAt: r.saved_at as string,
      headline:
        ((bi?.headline_override as string) || (s?.title as string)) ?? null,
      buyer: (org?.canonical_name as string) ?? null,
    };
  });
}

export interface FollowableBuyer {
  organizationId: string;
  name: string;
}

// Buyers a member can follow: the resolved organizations of gate-cleared
// (published + included) brief items. RLS already scopes the readable rows.
export async function listFollowableBuyers(
  supabase: SupabaseClient,
): Promise<FollowableBuyer[] | null> {
  const { data, error } = await supabase
    .from("brief_items")
    .select(
      "included, briefs!inner(status), " +
        "signals:lead_signal_id(organization_id, organizations(canonical_name))",
    )
    .eq("included", true)
    .eq("briefs.status", "published");
  if (error) {
    console.error("[watch-data] listFollowableBuyers:", error.message);
    return null;
  }
  const seen = new Map<string, string>();
  for (const r of (data ?? []) as unknown as Record<string, unknown>[]) {
    const s = one(r.signals as Record<string, unknown> | Record<string, unknown>[] | null);
    const org = one(
      (s?.organizations ?? null) as
        { canonical_name: string | null } | { canonical_name: string | null }[] | null,
    );
    const id = (s?.organization_id as string) ?? null;
    if (id && org?.canonical_name && !seen.has(id))
      seen.set(id, org.canonical_name);
  }
  return [...seen.entries()]
    .map(([organizationId, name]) => ({ organizationId, name }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function savedIds(saved: SavedItem[] | null): Set<string> {
  return new Set((saved ?? []).map((s) => s.briefItemId));
}

// "27 Jul" style short date for the event log, Eastern per the standing rule.
export function shortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto",
    day: "numeric",
    month: "short",
  }).format(d);
}

// ---------------------------------------------------------------------------
// Live "closing soon" surface (Wave 3, operator D1-D4 2026-07-28). Reads the
// member_live_items projection table -- a flat, gate-cleared table (the gate
// lives in src/live_surface.py, not here). Returns null when the table is not
// pasted yet, so the page falls back to its Pending block pre-paste.
// ---------------------------------------------------------------------------
export interface LiveItem {
  id: string;
  headline: string;
  buyer: string | null;
  docType: string;
  closingOn: string;
  datePrecision: string | null;
  referenceNumber: string | null;
  url: string | null;
  categorySlug: string | null;
  defenceRelevant: boolean;
  refreshedAt: string | null;
}

export async function listLiveItems(
  supabase: SupabaseClient,
): Promise<LiveItem[] | null> {
  const { data, error } = await supabase
    .from("member_live_items")
    .select(
      "id, headline, buyer_name, doc_type, closing_on, date_precision, " +
      "reference_number, url, category_slug, defence_relevant, refreshed_at",
    )
    .order("closing_on", { ascending: true });
  if (error) {
    // Pre-paste (table absent) returns null so the page shows Pending; this
    // is the one place a query error is a legitimate "not ready yet", not a
    // silent-empty (the table's own absence is the signal, not zero rows).
    console.error("[watch-data] listLiveItems:", error.message);
    return null;
  }
  return ((data ?? []) as unknown as Record<string, unknown>[]).map((r) => ({
    id: r.id as string,
    headline: (r.headline as string) ?? "(untitled opportunity)",
    buyer: (r.buyer_name as string) ?? null,
    docType: (r.doc_type as string) ?? "",
    closingOn: (r.closing_on as string) ?? "",
    datePrecision: (r.date_precision as string) ?? null,
    referenceNumber: (r.reference_number as string) ?? null,
    url: (r.url as string) ?? null,
    categorySlug: (r.category_slug as string) ?? null,
    defenceRelevant: Boolean(r.defence_relevant),
    refreshedAt: (r.refreshed_at as string) ?? null,
  }));
}

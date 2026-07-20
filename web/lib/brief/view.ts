// Server-side assembly of a published brief into the BriefView the pure render
// consumes. This is the SINGLE source the web published route and the email
// send both call, so the two surfaces cannot drift. Pure helpers (weekLabel,
// pickLeadAndSupporting) are split out and unit-tested; the async fetch/assembly
// takes a Supabase client so this module imports no server-only runtime.

import type { SupabaseClient } from "@supabase/supabase-js";
import type { BriefView, RenderItem, Exhibit } from "./render.ts";
import type { TimingPath } from "./date-label.ts";

const MFULL = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"];

// "13 to 19 July 2026", spanning months/years when the week crosses them.
export function weekLabel(weekStart: string): string {
  const s = new Date(`${(weekStart ?? "").slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(s.getTime())) return weekStart;
  const e = new Date(s);
  e.setUTCDate(e.getUTCDate() + 6);
  const sd = s.getUTCDate(), ed = e.getUTCDate();
  const sm = s.getUTCMonth(), em = e.getUTCMonth();
  const sy = s.getUTCFullYear(), ey = e.getUTCFullYear();
  if (sy !== ey) return `${sd} ${MFULL[sm]} ${sy} to ${ed} ${MFULL[em]} ${ey}`;
  if (sm !== em) return `${sd} ${MFULL[sm]} to ${ed} ${MFULL[em]} ${ey}`;
  return `${sd} to ${ed} ${MFULL[em]} ${ey}`;
}

// The lead is the top-ranked IMMINENT item (the actionable thing); if there is
// no imminent item, the top-ranked item leads. Everything else is supporting.
export function pickLeadAndSupporting(
  items: RenderItem[],
): { lead: RenderItem | null; supporting: RenderItem[] } {
  if (items.length === 0) return { lead: null, supporting: [] };
  let li = items.findIndex((it) => it.timing_path === "imminent");
  if (li < 0) li = 0;
  return { lead: items[li], supporting: items.filter((_, i) => i !== li) };
}

function one<T>(v: T | T[] | null | undefined): T | null {
  return Array.isArray(v) ? v[0] ?? null : v ?? null;
}

function currentQuarterStart(): string {
  const d = new Date();
  const q = Math.floor(d.getUTCMonth() / 3) * 3;
  return `${d.getUTCFullYear()}-${String(q + 1).padStart(2, "0")}-01`;
}

interface ItemRow {
  timing_path: string;
  headline_override: string | null;
  editor_note: string | null;
  lead_signal_id: string | null;
}
interface DocRow {
  doc_type: string | null;
  url: string | null;
  published_on: string | null;
  date_precision: string | null;
}
interface SignalRow {
  id: string;
  title: string | null;
  amount_max_cad: number | null;
  documents: DocRow | DocRow[] | null;
  organizations: { canonical_name: string | null } | { canonical_name: string | null }[] | null;
}

function toRenderItem(it: ItemRow, sig: SignalRow | undefined): RenderItem | null {
  const doc = one(sig?.documents);
  const org = one(sig?.organizations)?.canonical_name ?? null;
  const headline = it.headline_override || sig?.title || "(untitled item)";
  return {
    headline,
    timing_path: (it.timing_path === "imminent" ? "imminent" : "recent") as TimingPath,
    vendorSoWhat: it.editor_note ?? null,
    buyer: org,
    amountCad: sig?.amount_max_cad ?? null,
    // The lead signal's own document supplies the date, its precision, its type,
    // and the provenance url, so all four are consistent (never a day fabricated
    // onto a month-precision date, never a label that mismatches the linked doc).
    doc: {
      doc_type: doc?.doc_type ?? null,
      url: doc?.url ?? null,
      published_on: doc?.published_on ?? null,
      date_precision: doc?.date_precision ?? null,
    },
  };
}

async function buildAwardExhibit(supabase: SupabaseClient): Promise<Exhibit[]> {
  const { data } = await supabase
    .from("award_volume_by_quarter")
    .select("jurisdiction, quarter_start, quarter_label, awards")
    .eq("jurisdiction", "municipal")
    .order("quarter_start", { ascending: true });
  const rows = (data ?? []) as { quarter_start: string; quarter_label: string; awards: number }[];
  if (rows.length === 0) return [];
  const total = rows.reduce((a, r) => a + (r.awards ?? 0), 0);
  const curQ = currentQuarterStart();
  const recent = rows.slice(-8).map((r) => ({
    label: r.quarter_label,
    value: r.awards ?? 0,
    note: (r.quarter_start ?? "").slice(0, 10) === curQ ? "partial" : undefined,
  }));
  return [{
    title: "Peel municipal contract awards by quarter",
    basis: `${total.toLocaleString("en-CA")} award notices, ${rows[0].quarter_label} to `
      + `${rows[rows.length - 1].quarter_label} (current quarter partial). `
      + `Source: Region of Peel bids and tenders portal.`,
    format: "count",
    rows: recent,
  }];
}

const METHOD_NOTE =
  "Items are selected on event-date timing (closing soon, or decided in the last "
  + "seven days) and a materiality bar. Every claim links to the publisher's own record.";

// Build the view for a published brief. `week` is a week_start date or "latest".
// Returns null when there is no PUBLISHED brief for that week (drafts never
// render to a reader).
export async function buildBriefView(
  supabase: SupabaseClient,
  week: string,
): Promise<BriefView | null> {
  let query = supabase
    .from("briefs")
    .select("id, week_start, status, title, intro, excluded_below_threshold")
    .eq("status", "published");
  query = week === "latest"
    ? query.order("week_start", { ascending: false }).limit(1)
    : query.eq("week_start", week).limit(1);
  const { data: briefs } = await query;
  const brief = (briefs ?? [])[0] as
    | { id: string; week_start: string; intro: string | null; excluded_below_threshold: number }
    | undefined;
  if (!brief) return null;

  const { data: itemRows } = await supabase
    .from("brief_items")
    .select("timing_path, headline_override, editor_note, lead_signal_id, rank")
    .eq("brief_id", brief.id)
    .eq("included", true)
    .order("rank", { ascending: true, nullsFirst: false });
  const items = (itemRows ?? []) as (ItemRow & { rank: number | null })[];

  const ids = items.map((i) => i.lead_signal_id).filter((x): x is string => !!x);
  const sigById = new Map<string, SignalRow>();
  if (ids.length) {
    const { data: sigs } = await supabase
      .from("signals")
      .select("id, title, amount_max_cad, documents(doc_type,url,published_on,date_precision), organizations(canonical_name)")
      .in("id", ids);
    for (const s of (sigs ?? []) as unknown as SignalRow[]) sigById.set(s.id, s);
  }

  const renderItems = items
    .map((it) => toRenderItem(it, it.lead_signal_id ? sigById.get(it.lead_signal_id) : undefined))
    .filter((x): x is RenderItem => x !== null);
  const { lead, supporting } = pickLeadAndSupporting(renderItems);

  return {
    masthead: "The Weekly Signal",
    weekLabel: weekLabel(brief.week_start),
    weekStart: brief.week_start,
    theRead: brief.intro ?? null,
    lead,
    supporting,
    exhibits: await buildAwardExhibit(supabase),
    reviewedHeldCount: brief.excluded_below_threshold ?? 0,
    methodNote: METHOD_NOTE,
  };
}

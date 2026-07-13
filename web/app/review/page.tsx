import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "./actions";
import BulkReview, { ReviewSignal } from "./BulkReview";

export const dynamic = "force-dynamic";

type Doc = {
  title: string | null;
  url: string | null;
  doc_type: string | null;
  published_on: string | null;
  date_precision: string | null;
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Month-precision dates carry a conventional day=01 placeholder — rendering
// the full date would fabricate a day that isn't in the source. Render
// "Apr 2026" instead. (Binding rule for the brief generator too; ROADMAP.)
function eventDate(doc: Doc | null): string {
  if (!doc?.published_on) return "event date unknown";
  if (doc.date_precision === "month") {
    const [y, m] = doc.published_on.split("-");
    return `${MONTHS[Number(m) - 1] ?? m} ${y}`;
  }
  return doc.published_on;
}

// Demand-strength rungs, indexed by grade (mirrors src/taxonomy.RUNGS).
const RUNGS = ["ungraded", "chatter", "intent", "commitment", "in_market", "awarded"];
const CONFIDENCES = ["confirmed", "probable", "speculative"];

// PostgREST embeds a to-one relationship as either an object or a 1-element
// array depending on inference — normalize to a single value.
function one<T>(v: T | T[] | null): T | null {
  return Array.isArray(v) ? v[0] ?? null : v;
}

type SearchParams = {
  doc_type?: string;
  grade?: string;
  materiality?: string;
  confidence?: string;
  age?: string; // "fresh" | "stale" | "undated"
  sort?: string; // "newest" | "oldest"
};

// Freshness cutoff: matches the Procurements recency threshold (#48). A signal
// whose event date is older than this reads as stale.
const STALE_MONTHS = 6;

export default async function ReviewPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const supabase = createClient();

  // Facets: the doc_types actually present in the unreviewed queue, so the
  // filter dropdown never offers a type with zero matches (and never hides one
  // that exists). Cheap: one column, capped at the queue size.
  const { data: facetRows } = await supabase
    .from("signals")
    .select("documents!inner(doc_type)")
    .eq("reviewed", false)
    .limit(1000);
  const docTypes = Array.from(
    new Set(
      (facetRows ?? [])
        .map((r) => one(r.documents as Doc | Doc[] | null)?.doc_type)
        .filter((d): d is string => !!d)
    )
  ).sort();

  // Main query, filtered by the URL params. documents!inner so a doc_type
  // filter narrows the parent signals (an inner join drops signals whose
  // document doesn't match).
  let query = supabase
    .from("signals")
    .select(
      "id, title, summary, signal_type, confidence, materiality, evidence_grade, needs_org_resolution, unresolved_org_name, documents!inner(title,url,doc_type,published_on,date_precision), organizations(canonical_name)"
    )
    .eq("reviewed", false);

  if (searchParams.doc_type) query = query.eq("documents.doc_type", searchParams.doc_type);
  if (searchParams.confidence) query = query.eq("confidence", searchParams.confidence);
  const gradeMin = Number(searchParams.grade);
  if (gradeMin) query = query.gte("evidence_grade", gradeMin);
  const matMin = Number(searchParams.materiality);
  if (matMin) query = query.gte("materiality", matMin);

  // Event-date (freshness) filter: surface stale or undated signals as a group
  // so they can be bulk-handled. The cutoff is on documents.published_on, the
  // event date we already track (day/month precision).
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - STALE_MONTHS);
  const cutoffISO = cutoff.toISOString().slice(0, 10);
  if (searchParams.age === "undated") {
    query = query.is("documents.published_on", null);
  } else if (searchParams.age === "stale") {
    query = query.lt("documents.published_on", cutoffISO);
  } else if (searchParams.age === "fresh") {
    query = query.gte("documents.published_on", cutoffISO);
  }

  // Sort: default is materiality (most important first); event-date sort lets
  // the reviewer walk newest or oldest evidence. nullsFirst:false keeps undated
  // signals out of the way when sorting by date.
  if (searchParams.sort === "newest" || searchParams.sort === "oldest") {
    query = query.order("published_on", {
      referencedTable: "documents",
      ascending: searchParams.sort === "oldest",
      nullsFirst: false,
    });
  } else {
    query = query
      .order("materiality", { ascending: false })
      .order("created_at", { ascending: false });
  }

  const { data, error } = await query.limit(200);

  type Org = { canonical_name: string | null };
  type Row = {
    id: string;
    title: string;
    summary: string | null;
    signal_type: string;
    confidence: string;
    materiality: number;
    evidence_grade: number | null;
    needs_org_resolution: boolean | null;
    unresolved_org_name: string | null;
    documents: Doc | Doc[] | null;
    organizations: Org | Org[] | null;
  };
  const rows = (data ?? []) as unknown as Row[];

  // Flatten to the exact card shape the client component needs.
  const signals: ReviewSignal[] = rows.map((s) => {
    const doc = one(s.documents);
    const org = one(s.organizations);
    return {
      id: s.id,
      title: s.title,
      summary: s.summary,
      signal_type: s.signal_type,
      confidence: s.confidence,
      materiality: s.materiality,
      evidence_grade: s.evidence_grade,
      needs_org_resolution: !!s.needs_org_resolution,
      org_label:
        org?.canonical_name ??
        (s.needs_org_resolution
          ? `${s.unresolved_org_name ?? "unknown"} — needs resolution`
          : "—"),
      source_url: doc?.url ?? null,
      event_date: eventDate(doc),
      doc_type: doc?.doc_type ?? null,
    };
  });

  return (
    <main className="page wide">
      <div className="topbar">
        <h1>Signal Review</h1>
        <span className="count">{signals.length} shown</span>
        <Link className="link" href="/procurements">Procurements</Link>
        <Link className="link" href="/predictions">Predictions</Link>
        <Link className="link" href="/prospects">Prospects</Link>
        <Link className="link" href="/discovery">Discovery</Link>
        <form action={signOut}>
          <button className="link" type="submit">Sign out</button>
        </form>
      </div>

      {/* GET form: filters live in the URL, so they survive reloads and the
          back button. No client JS needed for filtering. */}
      <form className="filters" method="get">
        <select name="doc_type" defaultValue={searchParams.doc_type ?? ""}>
          <option value="">All doc types</option>
          {docTypes.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select name="confidence" defaultValue={searchParams.confidence ?? ""}>
          <option value="">All confidence</option>
          {CONFIDENCES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select name="grade" defaultValue={searchParams.grade ?? ""}>
          <option value="">Any grade</option>
          {[1, 2, 3, 4, 5].map((g) => (
            <option key={g} value={g}>{RUNGS[g]}+</option>
          ))}
        </select>
        <select name="materiality" defaultValue={searchParams.materiality ?? ""}>
          <option value="">Any materiality</option>
          {[1, 2, 3, 4, 5].map((m) => (
            <option key={m} value={m}>M{m}+</option>
          ))}
        </select>
        <select name="age" defaultValue={searchParams.age ?? ""}>
          <option value="">Any event date</option>
          <option value="fresh">Fresh (&lt; {STALE_MONTHS}mo)</option>
          <option value="stale">Stale (&gt; {STALE_MONTHS}mo)</option>
          <option value="undated">Undated</option>
        </select>
        <select name="sort" defaultValue={searchParams.sort ?? ""}>
          <option value="">Sort: materiality</option>
          <option value="newest">Sort: newest first</option>
          <option value="oldest">Sort: oldest first</option>
        </select>
        <button className="btn" type="submit">Filter</button>
      </form>

      {error ? <p className="err">Could not load signals: {error.message}</p> : null}

      {!error ? <BulkReview signals={signals} /> : null}
    </main>
  );
}

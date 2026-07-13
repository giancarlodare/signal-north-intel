import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { approve, reject, signOut } from "./actions";

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
type Org = { canonical_name: string | null };
type Signal = {
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

// Demand-strength rungs, indexed by grade (mirrors src/taxonomy.RUNGS). Answers
// "is this opportunity real": chatter is talk, awarded is money moved.
const RUNGS = ["ungraded", "chatter", "intent", "commitment", "in_market", "awarded"];

function gradeLabel(grade: number | null): string {
  return RUNGS[grade ?? 0] ?? "ungraded";
}

// PostgREST embeds a to-one relationship as either an object or a 1-element
// array depending on inference — normalize to a single value.
function one<T>(v: T | T[] | null): T | null {
  return Array.isArray(v) ? v[0] ?? null : v;
}

export default async function ReviewPage() {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("signals")
    .select(
      "id, title, summary, signal_type, confidence, materiality, evidence_grade, needs_org_resolution, unresolved_org_name, documents(title,url,doc_type,published_on,date_precision), organizations(canonical_name)"
    )
    .eq("reviewed", false)
    .order("materiality", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(50);

  const signals = (data ?? []) as unknown as Signal[];

  return (
    <main className="page">
      <div className="topbar">
        <h1>Signal Review</h1>
        <span className="count">{signals.length} pending</span>
        <Link className="link" href="/prospects">
          Prospects
        </Link>
        <Link className="link" href="/discovery">
          Discovery
        </Link>
        <form action={signOut}>
          <button className="link" type="submit">
            Sign out
          </button>
        </form>
      </div>

      {error ? (
        <p className="err">Could not load signals: {error.message}</p>
      ) : null}

      {!error && signals.length === 0 ? (
        <p className="empty">Nothing to review right now.</p>
      ) : null}

      {signals.map((s) => {
        const doc = one(s.documents);
        const org = one(s.organizations);
        const orgLabel =
          org?.canonical_name ??
          (s.needs_org_resolution
            ? `${s.unresolved_org_name ?? "unknown"} — needs resolution`
            : "—");
        const mClass = s.materiality >= 5 ? "m5" : s.materiality >= 4 ? "m4" : "";
        // Demand strength (is this opportunity real): commitment and above are
        // the rungs that prove real demand rather than announcement.
        const g = s.evidence_grade ?? 0;
        const gClass = g >= 4 ? "g-strong" : g === 3 ? "g-mid" : "g-weak";
        return (
          <article key={s.id} className="card">
            <div className="meta">
              {/* EVENT date (the source document's published_on) — editorially
                  distinct from collection date, which the review must not
                  confuse with when something actually happened. */}
              <span className="tag event">{eventDate(doc)}</span>
              <span className={"tag grade " + gClass}>{gradeLabel(s.evidence_grade)}</span>
              <span className={"tag " + mClass}>M{s.materiality}</span>
              <span className="tag">{s.confidence}</span>
              <span className="tag">{s.signal_type}</span>
              {s.needs_org_resolution ? <span className="tag warn">org?</span> : null}
            </div>
            <div className="title">{s.title}</div>
            {s.summary ? <p className="summary">{s.summary}</p> : null}
            <p className="sub">
              {orgLabel}
              {doc?.url ? (
                <>
                  {" · "}
                  <a href={doc.url} target="_blank" rel="noreferrer">
                    source
                  </a>
                </>
              ) : null}
            </p>
            <div className="row">
              <form action={approve} style={{ display: "flex", flex: 1 }}>
                <input type="hidden" name="id" value={s.id} />
                <button className="approve" type="submit">
                  Approve
                </button>
              </form>
              <form action={reject} style={{ display: "flex", flex: 1 }}>
                <input type="hidden" name="id" value={s.id} />
                <button className="reject" type="submit">
                  Reject
                </button>
              </form>
            </div>
          </article>
        );
      })}
    </main>
  );
}

import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "../auth-actions";
import {
  confirmProcurement,
  editProcurement,
  mergeProcurement,
  rejectProcurement,
} from "./actions";

export const dynamic = "force-dynamic";

// Demand-strength rungs, indexed by stage (mirrors src/taxonomy.RUNGS).
const RUNGS = ["ungraded", "chatter", "intent", "commitment", "in_market", "awarded"];
const rung = (s: number | null) => RUNGS[s ?? 0] ?? "ungraded";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// Newest evidence older than this reads as a stalled opportunity, not a
// prediction-ready one.
const STALE_MONTHS = 6;

type SignalDoc = { url: string | null; published_on: string | null; date_precision: string | null };
type LinkedSignal = {
  id: string;
  title: string | null;
  evidence_grade: number | null;
  organizations: { canonical_name: string | null } | { canonical_name: string | null }[] | null;
  documents: SignalDoc | SignalDoc[] | null;
};
type Proc = {
  id: string;
  title: string;
  scope: string | null;
  reference_number: string | null;
  current_stage: number | null;
  status: string;
  organizations: { canonical_name: string | null } | { canonical_name: string | null }[] | null;
  procurement_signals: { active: boolean; signals: LinkedSignal | LinkedSignal[] | null }[] | null;
};

function one<T>(v: T | T[] | null | undefined): T | null {
  return Array.isArray(v) ? v[0] ?? null : v ?? null;
}

// Event date, honoring the precision we store: month-precision dates carry a
// day=01 placeholder and must render "Apr 2026", never a fabricated full date
// (same rule as the review page's eventDate).
function eventDate(doc: SignalDoc | null): string | null {
  if (!doc?.published_on) return null;
  if (doc.date_precision === "month") {
    const [y, m] = doc.published_on.split("-");
    return `${MONTHS[Number(m) - 1] ?? m} ${y}`;
  }
  return doc.published_on;
}

// The cutoff date (YYYY-MM-DD) STALE_MONTHS ago. ISO strings sort lexically, so
// a plain string compare against published_on is correct.
function staleCutoff(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - STALE_MONTHS);
  return d.toISOString().slice(0, 10);
}

type Recency = { newest: SignalDoc | null; datedCount: number; stale: boolean };

// Newest dated evidence across a procurement's active signals, and whether the
// cluster is stale (newest older than the cutoff, or no dated evidence at all).
function recency(sigLinks: { active: boolean; signals: LinkedSignal | LinkedSignal[] | null }[],
                 cutoff: string): Recency {
  let newest: SignalDoc | null = null;
  let datedCount = 0;
  for (const l of sigLinks) {
    const doc = one(one(l.signals)?.documents ?? null);
    if (!doc?.published_on) continue;
    datedCount += 1;
    if (!newest || (newest.published_on ?? "") < doc.published_on) newest = doc;
  }
  const stale = datedCount === 0 || (newest?.published_on ?? "") < cutoff;
  return { newest, datedCount, stale };
}

function RecencyTags({ r }: { r: Recency }) {
  if (r.datedCount === 0) {
    return <span className="tag warn">no dated evidence</span>;
  }
  const label = eventDate(r.newest);
  return (
    <>
      <span className={"tag " + (r.stale ? "warn" : "")}>newest {label}</span>
      {r.stale ? <span className="tag warn">stale &gt; {STALE_MONTHS}mo</span> : null}
    </>
  );
}

export default async function ProcurementsPage() {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("procurements")
    .select(
      "id, title, scope, reference_number, current_stage, status, buyer_organization_id, organizations(canonical_name), procurement_signals(active, signals(id, title, evidence_grade, organizations(canonical_name), documents(url, published_on, date_precision)))"
    )
    .in("status", ["proposed", "confirmed"])
    .order("current_stage", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(100);

  const rows = (data ?? []) as unknown as Proc[];
  const proposed = rows.filter((p) => p.status === "proposed");
  const confirmed = rows.filter((p) => p.status === "confirmed");
  // Merge targets: every other open procurement.
  const targets = rows.map((p) => ({ id: p.id, title: p.title }));
  const cutoff = staleCutoff();

  return (
    <main className="page">
      <div className="topbar">
        <h1>Procurements</h1>
        <span className="count">{proposed.length} proposed</span>
        <Link className="link" href="/corpus">Corpus</Link>
        <Link className="link" href="/predictions">
          Predictions
        </Link>
        <Link className="link" href="/prospects">Prospects</Link>
        <Link className="link" href="/discovery">Discovery</Link>
        <form action={signOut}>
          <button className="link" type="submit">Sign out</button>
        </form>
      </div>

      {error ? <p className="err">Could not load procurements: {error.message}</p> : null}
      {!error && proposed.length === 0 ? (
        <p className="empty">No procurement candidates to review.</p>
      ) : null}

      {proposed.map((p) => {
        const buyer = one(p.organizations)?.canonical_name ?? "Unresolved buyer";
        const stage = p.current_stage ?? 1;
        const gClass = stage >= 4 ? "g-strong" : stage === 3 ? "g-mid" : "g-weak";
        const sigLinks = (p.procurement_signals ?? []).filter((l) => l.active);
        const r = recency(sigLinks, cutoff);
        return (
          <article key={p.id} className="card">
            <div className="meta">
              <span className={"tag grade " + gClass}>{rung(stage)}</span>
              <span className="tag">{sigLinks.length} signals</span>
              <RecencyTags r={r} />
              {p.reference_number ? <span className="tag">ref {p.reference_number}</span> : null}
            </div>
            <div className="title">{p.title}</div>
            <p className="sub">
              {buyer}
              {p.scope ? ` · ${p.scope}` : ""}
            </p>

            <details>
              <summary className="sub">Evidence ({sigLinks.length})</summary>
              <ul className="evidence">
                {sigLinks.map((l) => {
                  const s = one(l.signals);
                  if (!s) return null;
                  const doc = one(s.documents);
                  const url = doc?.url ?? null;
                  const when = eventDate(doc);
                  // The signal's own source org. On a merged procurement the
                  // survivor's buyer is one org, but each evidence signal keeps
                  // its own attribution here, so a board signal and a service
                  // signal stay distinguishable and provenance is never lost.
                  const srcOrg = one(s.organizations)?.canonical_name ?? null;
                  return (
                    <li key={s.id}>
                      <span className="tag event">{when ?? "date unknown"}</span>{" "}
                      <span className="tag grade g-weak">{rung(s.evidence_grade)}</span>{" "}
                      {srcOrg ? <span className="srcorg">{srcOrg}</span> : null}{" "}
                      {url ? (
                        <a href={url} target="_blank" rel="noreferrer">{s.title ?? "signal"}</a>
                      ) : (
                        s.title ?? "signal"
                      )}
                    </li>
                  );
                })}
              </ul>
            </details>

            {/* Edit reviewer-owned fields: title, scope, stage. */}
            <form action={editProcurement} className="field">
              <input type="hidden" name="id" value={p.id} />
              <label>Title</label>
              <input name="title" defaultValue={p.title} />
              <label>Scope</label>
              <input name="scope" defaultValue={p.scope ?? ""} />
              <label>Stage</label>
              <select name="current_stage" defaultValue={String(stage)}>
                {[1, 2, 3, 4, 5].map((g) => (
                  <option key={g} value={g}>{RUNGS[g]}</option>
                ))}
              </select>
              <button className="btn" type="submit">Save edits</button>
            </form>

            <div className="row">
              <form action={confirmProcurement} style={{ display: "flex", flex: 1 }}>
                <input type="hidden" name="id" value={p.id} />
                <button className="approve" type="submit">Confirm</button>
              </form>
              <form action={rejectProcurement} style={{ display: "flex", flex: 1 }}>
                <input type="hidden" name="id" value={p.id} />
                <button className="reject" type="submit">Reject</button>
              </form>
            </div>

            {/* Merge into another procurement (non-destructive). */}
            {targets.length > 1 ? (
              <form action={mergeProcurement} className="field">
                <input type="hidden" name="id" value={p.id} />
                <label>Merge into</label>
                <select name="merged_into_id" defaultValue="">
                  <option value="" disabled>choose survivor…</option>
                  {targets
                    .filter((t) => t.id !== p.id)
                    .map((t) => (
                      <option key={t.id} value={t.id}>{t.title}</option>
                    ))}
                </select>
                <button className="btn" type="submit">Merge</button>
              </form>
            ) : null}
          </article>
        );
      })}

      {confirmed.length > 0 ? (
        <>
          <div className="topbar" style={{ marginTop: 8 }}>
            <h1 style={{ fontSize: 15 }}>Confirmed</h1>
            <span className="count">{confirmed.length}</span>
          </div>
          {confirmed.map((p) => {
            const buyer = one(p.organizations)?.canonical_name ?? "Unresolved buyer";
            const stage = p.current_stage ?? 1;
            const gClass = stage >= 4 ? "g-strong" : stage === 3 ? "g-mid" : "g-weak";
            const sigLinks = (p.procurement_signals ?? []).filter((l) => l.active);
            const r = recency(sigLinks, cutoff);
            return (
              <article key={p.id} className="card">
                <div className="meta">
                  <span className={"tag grade " + gClass}>{rung(stage)}</span>
                  <span className="tag ok">confirmed</span>
                  <RecencyTags r={r} />
                </div>
                <div className="title">{p.title}</div>
                <p className="sub">{buyer}{p.scope ? ` · ${p.scope}` : ""}</p>
                {r.stale ? (
                  <p className="sub warntext">
                    Newest evidence is over {STALE_MONTHS} months old. Confirm the
                    opportunity is still live before predicting on it.
                  </p>
                ) : null}
              </article>
            );
          })}
        </>
      ) : null}
    </main>
  );
}

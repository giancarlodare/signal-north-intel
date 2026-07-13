import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "../review/actions";
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

type LinkedSignal = {
  id: string;
  title: string | null;
  evidence_grade: number | null;
  organizations: { canonical_name: string | null } | { canonical_name: string | null }[] | null;
  documents: { url: string | null } | { url: string | null }[] | null;
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

export default async function ProcurementsPage() {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("procurements")
    .select(
      "id, title, scope, reference_number, current_stage, status, buyer_organization_id, organizations(canonical_name), procurement_signals(active, signals(id, title, evidence_grade, organizations(canonical_name), documents(url)))"
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

  return (
    <main className="page">
      <div className="topbar">
        <h1>Procurements</h1>
        <span className="count">{proposed.length} proposed</span>
        <Link className="link" href="/review">Review</Link>
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
        return (
          <article key={p.id} className="card">
            <div className="meta">
              <span className={"tag grade " + gClass}>{rung(stage)}</span>
              <span className="tag">{sigLinks.length} signals</span>
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
                  const url = one(s.documents)?.url ?? null;
                  // The signal's own source org. On a merged procurement the
                  // survivor's buyer is one org, but each evidence signal keeps
                  // its own attribution here, so a board signal and a service
                  // signal stay distinguishable and provenance is never lost.
                  const srcOrg = one(s.organizations)?.canonical_name ?? null;
                  return (
                    <li key={s.id}>
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
            return (
              <article key={p.id} className="card">
                <div className="meta">
                  <span className={"tag grade " + gClass}>{rung(stage)}</span>
                  <span className="tag ok">confirmed</span>
                </div>
                <div className="title">{p.title}</div>
                <p className="sub">{buyer}{p.scope ? ` · ${p.scope}` : ""}</p>
              </article>
            );
          })}
        </>
      ) : null}
    </main>
  );
}

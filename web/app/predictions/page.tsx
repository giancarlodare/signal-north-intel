import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "../auth-actions";
import { confirmOutcome } from "./actions";

export const dynamic = "force-dynamic";

const RUNGS = ["ungraded", "chatter", "intent", "commitment", "in_market", "awarded"];
const rung = (s: number | null) => RUNGS[s ?? 0] ?? "ungraded";

type Org = { canonical_name: string | null };
type Proc = {
  id: string;
  title: string;
  current_stage: number | null;
  organizations: Org | Org[] | null;
};
type Outcome = {
  id: string;
  outcome: string;
  status: string;
  settling_document_id: string | null;
  resolved_on: string | null;
};
type Prediction = {
  id: string;
  made_at: string;
  subject_procurement_id: string | null;
  predicted_rung: number;
  horizon_ends_on: string;
  rationale: string;
  claim_hash: string;
  evidence_signal_ids: string[] | null;
  procurements: Proc | Proc[] | null;
  prediction_outcomes: Outcome[] | null;
  prediction_anchors: { anchor_type: string }[] | null;
};

function one<T>(v: T | T[] | null): T | null {
  return Array.isArray(v) ? v[0] ?? null : v ?? null;
}

export default async function PredictionsPage() {
  const supabase = createClient();

  const [{ data: predData }, { data: scoreData }] = await Promise.all([
    // seller-facing predictions (company-level gated ones are excluded)
    supabase
      .from("predictions")
      .select(
        "id, made_at, subject_procurement_id, predicted_rung, horizon_ends_on, rationale, claim_hash, evidence_signal_ids, procurements(id, title, current_stage, organizations(canonical_name)), prediction_outcomes(id, outcome, status, settling_document_id, resolved_on), prediction_anchors(anchor_type)"
      )
      .eq("gated", false)
      .order("made_at", { ascending: false })
      .limit(100),
    supabase.from("prediction_scorecard").select("outcome, lead_days"),
  ]);

  const predictions = (predData ?? []) as unknown as Prediction[];

  // Scorecard: correct rate and median-ish lead time over confirmed outcomes.
  const scored = (scoreData ?? []) as { outcome: string; lead_days: number | null }[];
  const settled = scored.filter((s) =>
    ["correct", "partial", "incorrect", "expired"].includes(s.outcome)
  );
  const correct = scored.filter((s) => s.outcome === "correct");
  const leadDays = correct
    .map((s) => s.lead_days)
    .filter((d): d is number => typeof d === "number");
  const avgLead =
    leadDays.length > 0
      ? Math.round(leadDays.reduce((a, b) => a + b, 0) / leadDays.length)
      : null;

  return (
    <main className="page">
      <div className="topbar">
        <h1>Predictions</h1>
        <span className="count">{predictions.length} claims</span>
        <Link className="link" href="/brief">Brief</Link>
        <Link className="link" href="/corpus">Corpus</Link>
        <Link className="link" href="/procurements">Procurements</Link>
        <Link className="link" href="/prospects">Prospects</Link>
        <form action={signOut}>
          <button className="link" type="submit">Sign out</button>
        </form>
      </div>

      {/* Track record */}
      <article className="card">
        <div className="title">Track record</div>
        <p className="sub">
          {settled.length === 0
            ? "No settled claims yet."
            : `${correct.length}/${settled.length} correct` +
              (avgLead !== null ? ` · avg lead ${avgLead} days ahead of the market` : "")}
        </p>
      </article>

      {/* Authoring lives on the Procurements candidate feed (evidence recency
          is shown there); this page is the ledger. */}
      <p className="sub">
        Author claims on the{" "}
        <Link className="link" href="/procurements">Procurements</Link> candidate
        feed, where evidence recency is shown. This page is the track record.
      </p>

      {/* Open + settled claims */}
      <div className="topbar" style={{ marginTop: 8 }}>
        <h1 style={{ fontSize: 15 }}>Claims</h1>
      </div>
      {predictions.map((p) => {
        const proc = one(p.procurements);
        const buyer = one(proc?.organizations ?? null)?.canonical_name ?? "";
        const anchored = (p.prediction_anchors ?? []).length > 0;
        const proposed = (p.prediction_outcomes ?? []).filter((o) => o.status === "proposed");
        const confirmed = (p.prediction_outcomes ?? []).filter((o) => o.status === "confirmed");
        return (
          <article key={p.id} className="card">
            <div className="meta">
              <span className="tag grade g-mid">→ {rung(p.predicted_rung)}</span>
              <span className="tag">by {p.horizon_ends_on}</span>
              <span className="tag">{(p.evidence_signal_ids ?? []).length} evidence</span>
              {confirmed.map((o) => (
                <span key={o.id} className={"tag " + (o.outcome === "correct" ? "ok" : "no")}>
                  {o.outcome}
                </span>
              ))}
              <span className={"tag " + (anchored ? "ok" : "warn")}>
                {anchored ? "anchored" : "unanchored"}
              </span>
            </div>
            <div className="title">{proc?.title ?? "procurement"}</div>
            <p className="sub">
              {buyer}
              {" · called "}
              {new Date(p.made_at).toISOString().slice(0, 10)}
              {" · "}
              <span title={p.claim_hash}>hash {p.claim_hash.slice(0, 10)}</span>
            </p>
            {p.rationale ? <p className="summary">{p.rationale}</p> : null}
            {proposed.map((o) => (
              <form key={o.id} action={confirmOutcome} className="row">
                <input type="hidden" name="id" value={o.id} />
                <span className="sub" style={{ flex: 1 }}>
                  Reconcile proposes: <strong>{o.outcome}</strong>
                </span>
                <button className="approve" type="submit">Confirm {o.outcome}</button>
              </form>
            ))}
          </article>
        );
      })}
    </main>
  );
}

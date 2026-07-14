import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "../auth-actions";
import {
  addToProspects,
  approveEntity,
  approveSource,
  rejectProposal,
} from "./actions";
import { JURISDICTIONS, ORG_TYPES, label } from "./constants";

export const dynamic = "force-dynamic";

type SourceProposal = {
  id: string;
  domain: string;
  suggested_name: string;
  kind: string;
  sample_urls: string[];
  evidence_document_ids: string[];
  mention_count: number;
  source_count: number;
  first_seen_on: string;
  last_seen_on: string;
  proposed_by: string;
};

type EntityProposal = {
  id: string;
  entity_kind: string;
  name: string;
  detail: { summary?: string; role?: string; organization?: string; add_alias_to?: string } | null;
  existing_organization_id: string | null;
  evidence_document_ids: string[];
  mention_count: number;
  proposed_by: string;
  status: string;
};

type EvidenceDoc = { id: string; title: string | null; url: string | null };

export default async function DiscoveryPage() {
  const supabase = createClient();

  const [{ data: srcData, error: srcError }, { data: entData, error: entError }] =
    await Promise.all([
      supabase
        .from("discovered_sources")
        .select(
          "id, domain, suggested_name, kind, sample_urls, evidence_document_ids, mention_count, source_count, first_seen_on, last_seen_on, proposed_by"
        )
        .eq("status", "proposed")
        .order("mention_count", { ascending: false }),
      supabase
        .from("discovered_entities")
        .select(
          "id, entity_kind, name, detail, existing_organization_id, evidence_document_ids, mention_count, proposed_by, status"
        )
        .in("status", ["proposed", "approved"])
        .order("mention_count", { ascending: false }),
    ]);

  const sources = (srcData ?? []) as SourceProposal[];
  const allEntities = (entData ?? []) as EntityProposal[];
  const entities = allEntities.filter((e) => e.status === "proposed");
  // Approved company-intent rows keep offering the second explicit action.
  const prospectCandidates = allEntities.filter(
    (e) => e.status === "approved" && e.entity_kind === "company_canada_intent"
  );

  // Resolve evidence document IDs to publisher links (provenance on screen).
  const evidenceIds = Array.from(
    new Set(
      [...sources, ...entities].flatMap((p) => p.evidence_document_ids).slice(0, 200)
    )
  );
  const { data: docData } = evidenceIds.length
    ? await supabase.from("documents").select("id, title, url").in("id", evidenceIds)
    : { data: [] };
  const docById = new Map((docData ?? []).map((d: EvidenceDoc) => [d.id, d]));

  const evidence = (ids: string[]) => (
    <p className="sub">
      Evidence:{" "}
      {ids.slice(0, 5).map((docId, i) => {
        const doc = docById.get(docId);
        return (
          <span key={docId}>
            {i > 0 ? " · " : ""}
            {doc?.url ? (
              <a href={doc.url} target="_blank" rel="noreferrer">
                {doc.title?.slice(0, 60) ?? "document"}
              </a>
            ) : (
              "document"
            )}
          </span>
        );
      })}
    </p>
  );

  return (
    <main className="page">
      <div className="topbar">
        <h1>Discovery</h1>
        <span className="count">
          {sources.length + entities.length} proposed
        </span>
        <Link className="link" href="/brief">Brief</Link>
        <Link className="link" href="/corpus">
          Corpus
        </Link>
        <Link className="link" href="/procurements">
          Procurements
        </Link>
        <Link className="link" href="/predictions">
          Predictions
        </Link>
        <Link className="link" href="/prospects">
          Prospects
        </Link>
        <form action={signOut}>
          <button className="link" type="submit">
            Sign out
          </button>
        </form>
      </div>

      {srcError ? (
        <p className="err">Could not load source proposals: {srcError.message}</p>
      ) : null}
      {entError ? (
        <p className="err">Could not load entity proposals: {entError.message}</p>
      ) : null}

      <div className="title" style={{ margin: "6px 2px 10px" }}>
        Proposed sources <span className="count">({sources.length})</span>
      </div>
      {sources.length === 0 ? <p className="empty">No source proposals.</p> : null}
      {sources.map((s) => (
        <article key={s.id} className="card">
          <div className="meta">
            <span className="tag">{label(s.kind)}</span>
            <span className="tag">{s.mention_count} docs</span>
            <span className="tag">{s.source_count} sources</span>
            <span className="tag">{s.proposed_by}</span>
          </div>
          <div className="title">{s.suggested_name}</div>
          <p className="sub">
            <a href={s.sample_urls[0]} target="_blank" rel="noreferrer">
              {s.domain}
            </a>{" "}
            · seen {s.first_seen_on} → {s.last_seen_on}
          </p>
          {evidence(s.evidence_document_ids)}
          <div className="row">
            <form action={approveSource} style={{ display: "flex", flex: 1 }}>
              <input type="hidden" name="id" value={s.id} />
              <button className="approve" type="submit">
                Approve source
              </button>
            </form>
            <form action={rejectProposal} style={{ display: "flex", flex: 1 }}>
              <input type="hidden" name="id" value={s.id} />
              <input type="hidden" name="table" value="discovered_sources" />
              <button className="reject" type="submit">
                Reject
              </button>
            </form>
          </div>
          <p className="sub" style={{ marginTop: 8 }}>
            Approving creates the sources row only — collection starts when its
            collector lands via a reviewed PR.
          </p>
        </article>
      ))}

      <div className="title" style={{ margin: "18px 2px 10px" }}>
        Proposed entities <span className="count">({entities.length})</span>
      </div>
      {entities.length === 0 ? <p className="empty">No entity proposals.</p> : null}
      {entities.map((e) => (
        <article key={e.id} className="card">
          <div className="meta">
            <span className="tag">{label(e.entity_kind)}</span>
            <span className="tag">{e.mention_count} docs</span>
            <span className="tag">{e.proposed_by}</span>
          </div>
          <div className="title">{e.name}</div>
          {e.detail?.role ? (
            <p className="sub">
              {e.detail.role}
              {e.detail.organization ? ` — ${e.detail.organization}` : ""}
            </p>
          ) : null}
          {e.detail?.summary ? <p className="summary">{e.detail.summary}</p> : null}
          {e.entity_kind === "alias_update" && e.detail?.add_alias_to ? (
            <p className="sub">Add as alias to: {e.detail.add_alias_to}</p>
          ) : null}
          {evidence(e.evidence_document_ids)}

          <form action={approveEntity}>
            <input type="hidden" name="id" value={e.id} />
            {e.entity_kind === "organization" ? (
              <div className="row" style={{ marginBottom: 8 }}>
                <div className="field" style={{ flex: 1, marginTop: 0 }}>
                  <select name="org_type" defaultValue="police_service">
                    {ORG_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {label(t)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field" style={{ flex: 1, marginTop: 0 }}>
                  <select name="jurisdiction" defaultValue="municipal">
                    {JURISDICTIONS.map((j) => (
                      <option key={j} value={j}>
                        {j}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ) : null}
            <div className="row">
              <button className="approve" type="submit" style={{ flex: 1 }}>
                {e.entity_kind === "organization"
                  ? "Approve → add organization"
                  : e.entity_kind === "alias_update"
                    ? "Approve → add alias"
                    : "Approve (mark reviewed)"}
              </button>
            </div>
          </form>
          <form action={rejectProposal} className="row" style={{ marginTop: 8 }}>
            <input type="hidden" name="id" value={e.id} />
            <input type="hidden" name="table" value="discovered_entities" />
            <button className="reject" type="submit">
              Reject
            </button>
          </form>
        </article>
      ))}

      {prospectCandidates.length > 0 ? (
        <>
          <div className="title" style={{ margin: "18px 2px 10px" }}>
            Approved company intent{" "}
            <span className="count">({prospectCandidates.length})</span>
          </div>
          {prospectCandidates.map((e) => (
            <article key={e.id} className="card">
              <div className="title">{e.name}</div>
              {e.detail?.summary ? (
                <p className="summary">{e.detail.summary}</p>
              ) : null}
              <form action={addToProspects} className="row">
                <input type="hidden" name="id" value={e.id} />
                <button className="approve" type="submit">
                  Add to prospects (watch only)
                </button>
              </form>
            </article>
          ))}
        </>
      ) : null}
    </main>
  );
}

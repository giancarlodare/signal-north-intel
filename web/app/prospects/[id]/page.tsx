import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { addInteraction, updateClassification, updateStatus } from "../actions";
import { INTERACTION_TYPES, STATUSES, TIERS, WAVES, label } from "../constants";

export const dynamic = "force-dynamic";

type Prospect = {
  id: string;
  company_name: string;
  category: string;
  tier: string;
  is_reference_candidate: boolean;
  conflict_flag: boolean;
  conflict_note: string | null;
  warm_path: string | null;
  wave: number;
  status: string;
  hq_location: string | null;
  notes: string | null;
};

type Interaction = {
  id: string;
  occurred_on: string;
  interaction_type: string;
  summary: string;
  follow_up: string | null;
  follow_up_due: string | null;
};

export default async function ProspectDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const supabase = createClient();

  const { data: prospect, error } = await supabase
    .from("prospects")
    .select(
      "id, company_name, category, tier, is_reference_candidate, conflict_flag, conflict_note, warm_path, wave, status, hq_location, notes"
    )
    .eq("id", params.id)
    .maybeSingle<Prospect>();

  if (error || !prospect) {
    return (
      <main className="page">
        <div className="topbar">
          <h1>Prospect</h1>
          <Link className="link" href="/prospects">
            ← All prospects
          </Link>
        </div>
        <p className="err">
          {error ? `Could not load prospect: ${error.message}` : "Not found."}
        </p>
      </main>
    );
  }

  const { data: interactionsData } = await supabase
    .from("prospect_interactions")
    .select("id, occurred_on, interaction_type, summary, follow_up, follow_up_due")
    .eq("prospect_id", prospect.id)
    .order("occurred_on", { ascending: false })
    .order("created_at", { ascending: false });
  const interactions = (interactionsData ?? []) as Interaction[];

  const today = new Date().toISOString().slice(0, 10);

  return (
    <main className="page">
      <div className="topbar">
        <h1>
          {prospect.is_reference_candidate ? <span className="star">★ </span> : null}
          {prospect.company_name}
        </h1>
        <Link className="link" href="/prospects">
          ← All
        </Link>
      </div>

      <article className="card">
        <div className="meta">
          <span className="tag">wave {prospect.wave}</span>
          <span className="tag">{label(prospect.tier)}</span>
          <span className="tag">{label(prospect.category)}</span>
        </div>
        {prospect.hq_location ? <p className="sub">HQ: {prospect.hq_location}</p> : null}
        {prospect.warm_path ? <p className="sub">Warm path: {prospect.warm_path}</p> : null}
        {prospect.conflict_flag ? (
          <p className="sub">
            <span className="tag warn">conflict</span>{" "}
            {prospect.conflict_note ?? "flagged — see notes"}
          </p>
        ) : null}
        {prospect.notes ? <p className="summary">{prospect.notes}</p> : null}

        <form action={updateStatus} className="row" style={{ marginTop: 10 }}>
          <input type="hidden" name="id" value={prospect.id} />
          <div className="field" style={{ flex: 2, marginTop: 0 }}>
            <select name="status" defaultValue={prospect.status}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {label(s)}
                </option>
              ))}
            </select>
          </div>
          <button className="approve" type="submit" style={{ flex: 1 }}>
            Update status
          </button>
        </form>

        <form action={updateClassification} style={{ marginTop: 10 }}>
          <input type="hidden" name="id" value={prospect.id} />
          <div className="row">
            <div className="field" style={{ flex: 2, marginTop: 0 }}>
              <label htmlFor="tier">Tier</label>
              <select id="tier" name="tier" defaultValue={prospect.tier}>
                {TIERS.map((t) => (
                  <option key={t} value={t}>
                    {label(t)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field" style={{ flex: 1, marginTop: 0 }}>
              <label htmlFor="wave">Wave</label>
              <select id="wave" name="wave" defaultValue={prospect.wave}>
                {WAVES.map((w) => (
                  <option key={w} value={w}>
                    wave {w}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <label className="checkrow" htmlFor="is_reference_candidate">
            <input
              id="is_reference_candidate"
              name="is_reference_candidate"
              type="checkbox"
              defaultChecked={prospect.is_reference_candidate}
            />
            <span className="star">★</span> Reference candidate
          </label>
          <div className="row" style={{ marginTop: 10 }}>
            <button type="submit">Update classification</button>
          </div>
        </form>
      </article>

      <article className="card">
        <div className="title">Log an interaction</div>
        {/* Governance (from the migration header): venture-clean facts only.
            Nothing learned in an official capacity belongs in this log. */}
        <p className="sub">Venture-clean notes only.</p>
        <form action={addInteraction}>
          <input type="hidden" name="prospect_id" value={prospect.id} />
          <div className="row">
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="occurred_on">Date</label>
              <input id="occurred_on" name="occurred_on" type="date" defaultValue={today} />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="interaction_type">Type</label>
              <select id="interaction_type" name="interaction_type" defaultValue="note">
                {INTERACTION_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {label(t)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="summary">Summary</label>
            <textarea id="summary" name="summary" className="note" required />
          </div>
          <div className="row">
            <div className="field" style={{ flex: 2 }}>
              <label htmlFor="follow_up">Follow-up</label>
              <input id="follow_up" name="follow_up" type="text" placeholder="optional" />
            </div>
            <div className="field" style={{ flex: 1 }}>
              <label htmlFor="follow_up_due">Due</label>
              <input id="follow_up_due" name="follow_up_due" type="date" />
            </div>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="approve" type="submit">
              Add interaction
            </button>
          </div>
        </form>
      </article>

      <div className="title" style={{ margin: "18px 2px 10px" }}>
        Interaction log <span className="count">({interactions.length})</span>
      </div>
      {interactions.length === 0 ? (
        <p className="empty">No interactions yet.</p>
      ) : null}
      {interactions.map((i) => (
        <article key={i.id} className="card">
          <div className="meta">
            <span className="tag">{i.occurred_on}</span>
            <span className="tag">{label(i.interaction_type)}</span>
            {i.follow_up_due ? (
              <span className="tag warn">due {i.follow_up_due}</span>
            ) : null}
          </div>
          <p className="summary">{i.summary}</p>
          {i.follow_up ? <p className="sub">Follow-up: {i.follow_up}</p> : null}
        </article>
      ))}
    </main>
  );
}

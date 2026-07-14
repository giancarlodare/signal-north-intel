import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "../auth-actions";
import { setBriefMeta, saveItem, publishBrief } from "./actions";

export const dynamic = "force-dynamic";

const RUNGS = ["ungraded", "chatter", "intent", "commitment", "in_market", "awarded"];

type Doc = { url: string | null; published_on: string | null; date_precision: string | null };
type Org = { canonical_name: string | null };
type Signal = {
  id: string;
  title: string | null;
  evidence_grade: number | null;
  materiality: number | null;
  documents: Doc | Doc[] | null;
  organizations: Org | Org[] | null;
};
type Item = {
  id: string;
  cluster_kind: string;
  timing_path: string;
  soonest_date: string | null;
  included: boolean;
  rank: number | null;
  headline_override: string | null;
  editor_note: string | null;
  lead_signal_id: string | null;
};
type Brief = {
  id: string;
  week_start: string;
  status: string;
  title: string | null;
  intro: string | null;
  excluded_below_threshold: number;
  exclusion_breakdown: Record<string, number> | null;
  published_at: string | null;
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function fmtDate(d: Doc | null): string {
  if (!d?.published_on) return "date unknown";
  if (d.date_precision === "month") {
    const [y, m] = d.published_on.split("-");
    return `${MONTHS[Number(m) - 1] ?? m} ${y}`;
  }
  return d.published_on;
}
function one<T>(v: T | T[] | null): T | null {
  return Array.isArray(v) ? v[0] ?? null : v;
}

export default async function BriefPage() {
  const supabase = createClient();
  const { data: briefs } = await supabase
    .from("briefs")
    .select("id, week_start, status, title, intro, excluded_below_threshold, exclusion_breakdown, published_at")
    .order("week_start", { ascending: false })
    .limit(1);
  const brief = (briefs?.[0] ?? null) as Brief | null;

  let items: Item[] = [];
  let sigById = new Map<string, Signal>();
  if (brief) {
    const { data: itemRows } = await supabase
      .from("brief_items")
      .select("id, cluster_kind, timing_path, soonest_date, included, rank, headline_override, editor_note, lead_signal_id")
      .eq("brief_id", brief.id)
      .order("rank", { ascending: true, nullsFirst: false });
    items = (itemRows ?? []) as Item[];
    const ids = items.map((i) => i.lead_signal_id).filter((x): x is string => !!x);
    if (ids.length) {
      const { data: sigs } = await supabase
        .from("signals")
        .select("id, title, evidence_grade, materiality, documents(url,published_on,date_precision), organizations(canonical_name)")
        .in("id", ids);
      sigById = new Map(((sigs ?? []) as unknown as Signal[]).map((s) => [s.id, s]));
    }
  }

  const isDraft = brief?.status === "draft";

  return (
    <main className="page wide">
      <div className="topbar">
        <h1>Weekly Signal</h1>
        <Link className="link" href="/corpus">Corpus</Link>
        <Link className="link" href="/procurements">Procurements</Link>
        <Link className="link" href="/predictions">Predictions</Link>
        <Link className="link" href="/discovery">Discovery</Link>
        <form action={signOut}>
          <button className="link" type="submit">Sign out</button>
        </form>
      </div>

      {!brief ? (
        <p className="empty">
          No brief yet. The weekly generator writes a draft each week (or run
          <code> python -m src.brief_generator --apply</code>).
        </p>
      ) : (
        <>
          <div className="meta">
            <span className="tag">week of {brief.week_start}</span>
            <span className={"tag " + (isDraft ? "warn" : "ok")}>{brief.status}</span>
            {brief.published_at ? (
              <span className="tag">published {brief.published_at.slice(0, 10)}</span>
            ) : null}
            <span className="tag">
              {brief.excluded_below_threshold} below the bar
              {brief.exclusion_breakdown
                ? ` (${Object.entries(brief.exclusion_breakdown).map(([k, v]) => `${k}: ${v}`).join(", ")})`
                : ""}
            </span>
          </div>

          {isDraft ? (
            <form action={setBriefMeta} className="field">
              <input type="hidden" name="id" value={brief.id} />
              <label>Title</label>
              <input name="title" defaultValue={brief.title ?? ""} placeholder="Weekly Signal headline" />
              <label>Intro</label>
              <textarea name="intro" className="note" defaultValue={brief.intro ?? ""} placeholder="Editorial framing" />
              <button className="btn" type="submit">Save framing</button>
            </form>
          ) : (
            <>
              {brief.title ? <div className="title">{brief.title}</div> : null}
              {brief.intro ? <p className="summary">{brief.intro}</p> : null}
            </>
          )}

          {items.length === 0 ? (
            <p className="empty">This brief has no items.</p>
          ) : null}

          <div className="cards">
            {items.map((it) => {
              const s = it.lead_signal_id ? sigById.get(it.lead_signal_id) : null;
              const doc = one(s?.documents ?? null);
              const org = one(s?.organizations ?? null)?.canonical_name ?? "unresolved";
              const g = s?.evidence_grade ?? 0;
              const gClass = g >= 4 ? "g-strong" : g === 3 ? "g-mid" : "g-weak";
              const headline = it.headline_override || s?.title || "(signal)";
              const dimmed = !it.included ? { opacity: 0.5 } : undefined;
              return (
                <article key={it.id} className="card" style={dimmed}>
                  <div className="meta">
                    <span className="tag">#{it.rank ?? "-"}</span>
                    <span className={"tag " + (it.timing_path === "imminent" ? "event" : "")}>
                      {it.timing_path}
                    </span>
                    <span className={"tag grade " + gClass}>{RUNGS[g] ?? "ungraded"}</span>
                    {s?.materiality ? <span className="tag">M{s.materiality}</span> : null}
                    <span className="tag">{it.cluster_kind}</span>
                    {it.soonest_date ? <span className="tag">{it.soonest_date}</span> : null}
                    {!it.included ? <span className="tag no">cut</span> : null}
                  </div>
                  <div className="title">{headline}</div>
                  <p className="sub">
                    {org}
                    {doc?.url ? (
                      <>
                        {" · "}
                        <a href={doc.url} target="_blank" rel="noreferrer">source</a>
                        {" · "}{fmtDate(doc)}
                      </>
                    ) : null}
                  </p>

                  {isDraft ? (
                    <form action={saveItem} className="field">
                      <input type="hidden" name="id" value={it.id} />
                      <label className="checkrow">
                        <input type="checkbox" name="included" defaultChecked={it.included} />
                        Include in brief
                      </label>
                      <label>Rank</label>
                      <input name="rank" type="number" defaultValue={it.rank ?? ""} />
                      <label>Headline override</label>
                      <input name="headline_override" defaultValue={it.headline_override ?? ""} />
                      <label>Editor note</label>
                      <input name="editor_note" defaultValue={it.editor_note ?? ""} />
                      <button className="btn" type="submit">Save item</button>
                    </form>
                  ) : it.editor_note ? (
                    <p className="sub">{it.editor_note}</p>
                  ) : null}
                </article>
              );
            })}
          </div>

          {isDraft ? (
            <form action={publishBrief} style={{ marginTop: 12 }}>
              <input type="hidden" name="id" value={brief.id} />
              <button className="approve" type="submit">Publish brief</button>
            </form>
          ) : null}
        </>
      )}
    </main>
  );
}

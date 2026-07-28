// Member dashboard home (Claude Design handoff: dashboard/index.html).
// Replaces the stage-2 unstyled skeleton wholesale, per its own contract;
// the data layer (web/lib/portal/data.ts) is unchanged.
//
// Wired today: the date line, the this-week's-brief panel (latest published
// brief + its lead item), and navigation. STAGE-GAPS (flagged, expected, all
// rendered as honest Pending blocks that light up as their stages land):
//  - personalized "N things changed" headline + watch summary  -> stage 3a
//  - "Flagged for you" watchlist matches                        -> stage 3a
//  - saved-items rail                                           -> stage 3b
//  - "We told you first" event log                              -> stage 3a
import { createClient } from "@/lib/supabase/server";
import { listPublishedBriefs, getBriefItems } from "@/lib/portal/data";
import {
  listWatches,
  listEvents,
  listSaved,
  shortDate,
} from "@/lib/portal/watch-data";
import Pending from "@/components/portal/Pending";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Home — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

// ALL times Eastern (America/Toronto), standing operator rule.
function todayEastern(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto",
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date());
}

export default async function PortalHome() {
  const supabase = createClient();
  const [briefs, watches, events, saved] = await Promise.all([
    listPublishedBriefs(supabase),
    listWatches(supabase),
    listEvents(supabase),
    listSaved(supabase),
  ]);
  // Same fallback as the brief page: the panel features the newest published
  // brief that actually has a member-visible item.
  let latest = briefs[0] ?? null;
  let leadHeadline: string | null = null;
  for (const b of briefs) {
    const its = await getBriefItems(supabase, b.id);
    if (its.length > 0) {
      latest = b;
      leadHeadline = its[0]?.headline ?? null;
      break;
    }
  }
  const stage3 = watches !== null;
  const nBuyers = (watches ?? []).filter((w) => w.kind === "buyer").length;
  const nTopics = (watches ?? []).filter((w) => w.kind === "keyword").length;
  const flags = (events ?? [])
    .filter((e) => e.eventType === "match" || e.eventType === "backfill")
    .slice(0, 4);
  const weekAgo = Date.now() - 7 * 86400e3;
  const changed = (events ?? []).filter(
    (e) => e.eventType === "match" && new Date(e.createdAt).getTime() >= weekAgo,
  ).length;
  const trustLog = (events ?? [])
    .filter((e) => e.eventType === "match" || e.eventType === "follow")
    .slice(0, 3);

  return (
    <main className="fade-rise" data-testid="portal-dashboard">
      <section className="dash-hero">
        <div className="dash-hero__inner">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span className="dash-hero__date" data-field="date">
              {todayEastern()}
            </span>
            <h1 className="dash-hero__title" data-field="headline">
              {changed === 1
                ? "Good morning. One thing changed in your world."
                : changed > 1
                  ? `Good morning. ${changed} things changed in your world.`
                  : "Welcome back."}
            </h1>
          </div>
          <span
            style={{ fontSize: 14, color: "var(--blue-dim)" }}
            data-field="watch-summary"
          >
            {stage3 ? (
              <>
                Watching {nBuyers} {nBuyers === 1 ? "buyer" : "buyers"} and{" "}
                {nTopics} {nTopics === 1 ? "topic" : "topics"} ·{" "}
                <a
                  href="/portal/watching"
                  style={{
                    color: "var(--blue-soft)",
                    textDecoration: "underline",
                  }}
                >
                  adjust
                </a>
              </>
            ) : (
              "Watchlists arrive with the next portal stage."
            )}
          </span>
        </div>
      </section>

      <div className="dash-main dash-cols">
        <section
          style={{ display: "flex", flexDirection: "column", gap: 20 }}
          data-testid="flags"
        >
          <span className="t-label">Flagged for you</span>
          {flags.length === 0 ? (
            <Pending
              title="Nothing flagged yet."
              note={
                stage3
                  ? "Matches to your watched buyers and keywords will appear here."
                  : "Matches to your watched buyers and keywords will appear here when Watching launches."
              }
              testid="flags-pending"
            />
          ) : (
            flags.map((e) => (
              <article className="card flag-card" data-testid="flag-item" key={e.id}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                    gap: 16,
                    flexWrap: "wrap",
                  }}
                >
                  <span className="flag-card__match" data-field="match">
                    {e.eventType === "backfill"
                      ? "Recent match in your area"
                      : `Matches: ${(e.detail ?? "").replace(/^(keyword|buyer): /, "")}`}
                  </span>
                </div>
                <h3 data-field="title">{e.signalTitle ?? "(untitled item)"}</h3>
                <div className="flag-card__meta">
                  {e.buyer ? (
                    <span className="mono-meta" data-field="buyer">
                      {e.buyer}
                    </span>
                  ) : null}
                  <span className="mono-meta">{shortDate(e.createdAt)}</span>
                  <a href="/portal/brief" className="src-link">
                    Read in the brief →
                  </a>
                </div>
              </article>
            ))
          )}
        </section>

        <aside style={{ display: "flex", flexDirection: "column", gap: 32 }}>
          <div className="brief-panel">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: 12,
              }}
            >
              <span className="t-label" style={{ color: "#fff" }}>
                This week&apos;s brief
              </span>
              <span className="live-dot"></span>
            </div>
            {latest ? (
              <>
                <h3 data-field="brief-headline">
                  {leadHeadline ?? `Week of ${latest.weekStart}`}
                </h3>
                <a
                  href="/portal/brief"
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    color: "var(--blue-soft)",
                  }}
                >
                  Read the Weekly Signal →
                </a>
              </>
            ) : (
              <h3 data-testid="portal-empty">No published briefs yet.</h3>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
              }}
            >
              <span className="t-label">Saved</span>
              <a
                href="/portal/saved"
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                All saved →
              </a>
            </div>
            {(saved ?? []).length === 0 ? (
              <Pending
                title="Nothing saved yet."
                note={
                  stage3
                    ? "Use Save on any item in the brief."
                    : "Saving arrives with the next portal stage."
                }
                testid="saved-pending"
              />
            ) : (
              (saved ?? []).slice(0, 2).map((it) => (
                <div
                  key={it.briefItemId}
                  className="card"
                  style={{
                    padding: "16px 20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 5,
                  }}
                >
                  <span style={{ fontSize: 15, color: "var(--ink)" }}>
                    {it.headline ?? "(untitled item)"}
                  </span>
                  <span className="mono-meta" style={{ fontSize: 11 }}>
                    Saved {shortDate(it.savedAt)}
                  </span>
                </div>
              ))
            )}
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              borderTop: "1px solid var(--line)",
              paddingTop: 20,
            }}
            data-testid="activity-log"
          >
            <span className="t-label">We told you first</span>
            {trustLog.length === 0 ? (
              <Pending
                title="The record starts with your first watch."
                note="Every time we surface something for you, it is logged here with its date."
                testid="activity-pending"
              />
            ) : (
              trustLog.map((e) => (
                <div
                  className="activity-row"
                  style={{ borderTop: 0, paddingTop: 0 }}
                  key={e.id}
                >
                  <time>{shortDate(e.createdAt)}</time>
                  <span style={{ fontSize: 13.5 }}>
                    {e.eventType === "match"
                      ? `Flagged ${e.signalTitle ?? "an item"} for you.`
                      : e.detail ?? "You updated your watches."}
                  </span>
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}

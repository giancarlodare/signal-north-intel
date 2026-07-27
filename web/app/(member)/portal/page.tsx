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
  const briefs = await listPublishedBriefs(supabase);
  const latest = briefs[0] ?? null;
  const leadHeadline = latest
    ? ((await getBriefItems(supabase, latest.id))[0]?.headline ?? null)
    : null;

  return (
    <main className="fade-rise" data-testid="portal-dashboard">
      <section className="dash-hero">
        <div className="dash-hero__inner">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span className="dash-hero__date" data-field="date">
              {todayEastern()}
            </span>
            {/* Stage-3 gap: the designed headline counts watchlist changes
                ("Two things changed in your world"); until watches exist the
                greeting stays neutral. */}
            <h1 className="dash-hero__title" data-field="headline">
              Welcome back.
            </h1>
          </div>
          <span
            style={{ fontSize: 14, color: "var(--blue-dim)" }}
            data-field="watch-summary"
            data-placeholder="true"
          >
            Watchlists arrive with the next portal stage.
          </span>
        </div>
      </section>

      <div className="dash-main dash-cols">
        <section
          style={{ display: "flex", flexDirection: "column", gap: 20 }}
          data-testid="flags"
        >
          <span className="t-label">Flagged for you</span>
          <Pending
            title="Nothing flagged yet."
            note="Matches to your watched buyers and keywords will appear here when Watching launches."
            testid="flags-pending"
          />
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
            <Pending
              title="Nothing saved yet."
              note="Saving arrives with the next portal stage."
              testid="saved-pending"
            />
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
            <Pending
              title="The record starts with your first watch."
              note="Every time we surface something for you, it is logged here with its date."
              testid="activity-pending"
            />
          </div>
        </aside>
      </div>
    </main>
  );
}

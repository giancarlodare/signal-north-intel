// Watching (Claude Design handoff: dashboard/watching.html), live against
// stage-3 member_watches / watch_events. Keyword chips and buyer follows
// write through owner-scoped RLS; the "we told you first" log shows only
// forward 'match' events plus the member's own follows (decision B: backfill
// never enters the trust log; backfill items surface on Home as "recent
// matches in your area"). Pre-paste (queries null) the panels show pending
// notes and disabled controls.
import { createClient } from "@/lib/supabase/server";
import {
  listWatches,
  listEvents,
  listFollowableBuyers,
  shortDate,
} from "@/lib/portal/watch-data";
import { addKeywordWatch, removeWatch, followBuyer } from "../actions";
import { COVERAGE_STATUS } from "@/lib/marketing/coverage-status";
import RequireTier from "@/components/portal/RequireTier";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Watching — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

export default async function WatchingPage() {
  // Paywall. The account page deliberately does NOT use this.
  // Pro surface (tier ship-gate 2026-08-04): paid AND pro-or-above.
  await RequireTier("/portal/watching");
  const supabase = createClient();
  const [watches, events, buyers] = await Promise.all([
    listWatches(supabase),
    listEvents(supabase),
    listFollowableBuyers(supabase),
  ]);
  const live = watches !== null;
  const keywords = (watches ?? []).filter((w) => w.kind === "keyword");
  const followed = new Set(
    (watches ?? [])
      .filter((w) => w.kind === "buyer")
      .map((w) => w.organizationId),
  );
  const trustLog = (events ?? []).filter(
    (e) => e.eventType === "match" || e.eventType === "follow",
  );

  return (
    <main className="fade-rise">
      <div
        className="dash-main"
        style={{
          paddingTop: 64,
          display: "flex",
          flexDirection: "column",
          gap: 40,
        }}
      >
        <div className="page-head">
          <h1>Watching</h1>
          <span style={{ fontSize: 15, color: "var(--muted)" }}>
            Tell the record what matters to you. Matches surface on your home
            and in your flags.
          </span>
        </div>

        <div className="watch-grid">
          <section
            className="card"
            style={{
              padding: "28px 30px",
              display: "flex",
              flexDirection: "column",
              gap: 18,
            }}
            data-testid="keywords-panel"
          >
            <span className="t-label">Topics and keywords</span>
            {!live ? (
              <span style={{ fontSize: 14, color: "var(--faint)" }}>
                Watching is temporarily unavailable; retry shortly.
              </span>
            ) : null}
            <div
              style={{ display: "flex", gap: 10, flexWrap: "wrap" }}
              data-keywords
            >
              {keywords.map((w) => (
                <span className="kw-chip" key={w.id}>
                  <span>{w.keyword}</span>
                  <form action={removeWatch} style={{ display: "inline" }}>
                    <input type="hidden" name="watch_id" value={w.id} />
                    <button type="submit" aria-label="Stop watching">
                      ×
                    </button>
                  </form>
                </span>
              ))}
            </div>
            <form action={addKeywordWatch} style={{ display: "flex", gap: 10 }}>
              <input
                data-kw-input
                name="keyword"
                placeholder="Add a keyword, e.g. dispatch"
                disabled={!live}
                title={live ? undefined : "Temporarily unavailable"}
                style={{
                  flex: 1,
                  border: "1px solid var(--line)",
                  borderRadius: 2,
                  padding: "11px 14px",
                  fontSize: 14,
                  fontFamily: "var(--font-sans)",
                  color: "var(--ink)",
                  outline: "none",
                }}
              />
              <button
                data-kw-add
                type="submit"
                disabled={!live}
                style={{
                  padding: "11px 20px",
                  letterSpacing: "0.08em",
                  fontSize: 12,
                  border: 0,
                  cursor: live ? "pointer" : "default",
                  background: live ? "var(--red)" : "var(--line)",
                  color: "#fff",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  fontFamily: "var(--font-sans)",
                }}
              >
                Watch
              </button>
            </form>
          </section>

          <section
            className="card"
            style={{
              padding: "28px 30px",
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
            data-testid="buyers-panel"
          >
            <span className="t-label" style={{ paddingBottom: 12 }}>
              Buyers you follow
            </span>
            {!live ? (
              <span style={{ fontSize: 14, color: "var(--faint)" }}>
                Watching is temporarily unavailable; retry shortly.
              </span>
            ) : (buyers ?? []).length === 0 ? (
              <span style={{ fontSize: 14, color: "var(--faint)" }}>
                Buyers appear here as briefs publish.
              </span>
            ) : (
              (buyers ?? []).map((b) => (
                <div className="follow-row" key={b.organizationId}>
                  <span style={{ fontSize: 15, color: "var(--ink)" }}>
                    {b.name}
                  </span>
                  {followed.has(b.organizationId) ? (
                    <button className="follow-btn is-on" disabled>
                      Following
                    </button>
                  ) : (
                    <form action={followBuyer}>
                      <input
                        type="hidden"
                        name="organization_id"
                        value={b.organizationId}
                      />
                      <input type="hidden" name="buyer_name" value={b.name} />
                      <button className="follow-btn" data-buyer={b.organizationId} type="submit">
                        Follow
                      </button>
                    </form>
                  )}
                </div>
              ))
            )}
          </section>
        </div>

        <section
          className="card"
          style={{
            padding: "28px 30px",
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
          data-testid="coverage-panel"
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <span className="t-label">What we watch today</span>
            <a
              href="mailto:giancarlo@signalnorthintel.com?subject=Coverage request"
              className="src-link"
              style={{ marginLeft: 0 }}
            >
              Request coverage →
            </a>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0,1fr))",
              gap: 24,
            }}
          >
            {COVERAGE_STATUS.map((cell) => (
              <div
                key={cell.label}
                style={{ display: "flex", flexDirection: "column", gap: 6 }}
              >
                <span
                  className="t-label"
                  style={{
                    fontSize: 11,
                    letterSpacing: "0.14em",
                    color: cell.tone === "firm" ? "var(--navy)" : "var(--faint)",
                  }}
                >
                  {cell.label}
                </span>
                <span style={{ fontSize: 14 }}>{cell.text}</span>
              </div>
            ))}
          </div>
          <span
            style={{
              fontSize: 13,
              lineHeight: 1.7,
              color: "var(--faint)",
              borderTop: "1px solid var(--line-soft)",
              paddingTop: 14,
            }}
          >
            If a keyword returns nothing, this is why it might: we either do
            not cover that ground yet, or nothing is happening on it. We will
            always tell you which.
          </span>
        </section>

        <section
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            maxWidth: 720,
          }}
          data-testid="activity-log"
        >
          <span className="t-label">We told you first</span>
          {trustLog.length === 0 ? (
            <span style={{ fontSize: 14, color: "var(--faint)" }}>
              Every time we surface something for you, it is logged here with
              its date. The record starts with your first watch.
            </span>
          ) : (
            trustLog.map((e) => (
              <div className="activity-row" key={e.id}>
                <time>{shortDate(e.createdAt)}</time>
                <span style={{ fontSize: 14 }}>
                  {e.eventType === "match"
                    ? `Flagged ${e.signalTitle ?? "an item"} for you (${e.detail ?? "watch match"}).`
                    : e.detail ?? "You updated your watches."}
                </span>
              </div>
            ))
          )}
        </section>
      </div>
    </main>
  );
}

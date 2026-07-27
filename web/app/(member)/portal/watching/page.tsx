// Watching (Claude Design handoff: dashboard/watching.html).
// STAGE-3A GAP (flagged, expected): member_watches / watch_events have not
// landed, so the keyword and buyer panels render the designed shells with
// controls disabled and no fake persistence. The coverage panel is static
// handoff content and stands as-is.
import { COVERAGE_STATUS } from "@/lib/marketing/coverage-status";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Watching — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

export default function WatchingPage() {
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

        <div className="watch-grid" data-placeholder="true">
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
            <span style={{ fontSize: 14, color: "var(--faint)" }}>
              Keyword watching arrives with the next portal stage.
            </span>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }} data-keywords></div>
            <div style={{ display: "flex", gap: 10 }}>
              <input
                data-kw-input
                placeholder="Add a keyword, e.g. dispatch"
                disabled
                title="Arrives with the next portal stage"
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
                disabled
                title="Arrives with the next portal stage"
                style={{
                  padding: "11px 20px",
                  letterSpacing: "0.08em",
                  fontSize: 12,
                  border: 0,
                  cursor: "default",
                  background: "var(--line)",
                  color: "#fff",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  fontFamily: "var(--font-sans)",
                }}
              >
                Watch
              </button>
            </div>
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
            <span style={{ fontSize: 14, color: "var(--faint)" }}>
              Following buyers arrives with the next portal stage.
            </span>
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
              href="mailto:briefings@signalnorth.ca?subject=Coverage request"
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
          <span
            style={{ fontSize: 14, color: "var(--faint)" }}
            data-placeholder="true"
          >
            Every time we surface something for you, it is logged here with its
            date. The record starts with your first watch.
          </span>
        </section>
      </div>
    </main>
  );
}

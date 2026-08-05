// About page (Claude Design handoff: marketing-site/about.html).
// LIVE DATA RULE (operator 2026-07-27): the stats strip renders MEASURED
// corpus numbers via marketing_stats(), or is omitted entirely; the
// handoff's placeholder figures ($4.1B etc.) never render. Note wording is
// kept defensible: no "every service in Ontario" claims beyond what the
// register shows.
import SiteHeader from "@/components/site/SiteHeader";
import SiteFooter from "@/components/site/SiteFooter";
import {
  getMarketingStats,
  formatCadCompact,
  formatCountFloor,
  type MarketingStats,
} from "@/lib/marketing/data";

export const metadata = { title: "About — Signal North" };
// ISR: stats refresh every 30 minutes without a redeploy.
export const revalidate = 1800;

// Only substantiated figures render (audit 2026-07-27): the live-contract
// cells join the strip once the end-date extraction backlog gives them a
// real value; until then the strip leads with what the record genuinely
// holds.
function statCells(s: MarketingStats) {
  const cells = [
    {
      value: String(s.police_and_boards),
      label: "Police services and oversight boards",
      note: "Municipal and regional services, the provincial force, and the boards that approve their spending.",
    },
    {
      value: String(s.councils_ministries_departments),
      label: "Councils, ministries and departments",
      note: "The bodies that fund public safety and run the grant programs it draws on, federal and provincial.",
    },
    {
      value: String(s.sources_registered),
      label: "Public sources collected continuously",
      note: "Portals, boards, newsrooms, registers and legislatures, each linked to its publisher.",
    },
    {
      value: formatCadCompact(s.total_disclosed_value_cad),
      label: "In disclosed contract value on the record",
      note: "The disclosed value of the awards we hold, across the full award history.",
    },
    {
      value: String(s.years_of_award_history),
      label: "Years of disclosed award history",
      // Interval-timing claim removed (operator 2026-08-05): calibration showed
      // decision-to-tender intervals aren't reliably derivable at the org level,
      // so the product no longer makes that claim. This subline states what the
      // depth genuinely gives -- cross-buyer disclosed VALUES across years -- and
      // deliberately avoids any return-to-market/expiry timing claim, which end
      // dates (0 of 548 awards carry one) can't back either.
      note: "Enough history to compare what different organisations have paid for the same work, going back years.",
    },
    {
      value: formatCountFloor(s.documents_last_7_days),
      label: "Public documents read this week",
      note: "Agendas, minutes, budgets, staff reports, notices and registers, collected the day they publish.",
    },
  ];
  // "Contracts held, with end dates" was removed (operator 2026-08-03): while
  // that figure is a single digit it reads as a weakness, not a proof point.
  // Restore the cell here once the end-date backfill lifts the number.
  return cells;
}

const PRINCIPLES = [
  { num: "01", title: "Human judgment", body: "Every projection carries the name of the analyst who reviewed it." },
  { num: "02", title: "Independently held", body: "No ownership by, and no ties to, anyone in the market we cover." },
  { num: "03", title: "Public records only", body: "If a member cannot obtain the source, it does not go in." },
  { num: "04", title: "Neutral by design", body: "No one can pay to change what the record shows." },
];

export default async function AboutPage() {
  const stats = await getMarketingStats();
  return (
    <>
      <SiteHeader current="about" />
      <main>
        <section className="hero">
          <div
            className="container"
            style={{
              paddingTop: "var(--sp-9)",
              paddingBottom: 72,
              display: "flex",
              flexDirection: "column",
              gap: 26,
            }}
          >
            <span className="hero__eyebrow fade-rise">About Signal North</span>
            <h1
              className="hero__title fade-rise"
              style={{ fontSize: 58, maxWidth: 960 }}
            >
              The information that decides this market is already public.{" "}
              <span style={{ color: "var(--blue-dim)" }}>
                Almost no one reads it properly.
              </span>
            </h1>
            <p className="hero__sub fade-rise" style={{ margin: 0, maxWidth: 640 }}>
              Signal North reads all of it, every day, and holds it in one
              neutral record.
            </p>
          </div>
          {stats ? (
            <div className="stats">
              <div className="container stats__grid">
                {statCells(stats).map((s) => (
                  <div className="stat" key={s.label}>
                    <span className="stat__value" data-field="value">
                      {s.value}
                    </span>
                    <span className="stat__label">{s.label}</span>
                    <span className="stat__note">{s.note}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section
          className="band band--paper"
          style={{ paddingTop: 88, paddingBottom: 88 }}
        >
          <div className="container">
            <div className="about-section">
              <div className="about-rail">
                <span className="about-rail__num">01</span>
                <span className="about-rail__label">The mission</span>
                <span className="about-rail__rule"></span>
              </div>
              <div className="about-content">
                <p
                  style={{
                    margin: 0,
                    fontFamily: "var(--font-serif)",
                    fontSize: "var(--fs-heading)",
                    lineHeight: 1.45,
                    letterSpacing: "-0.01em",
                    color: "var(--ink-soft)",
                  }}
                >
                  Every major purchase in Canadian public safety and defence
                  leaves a trail long before it becomes a tender, in a lifecycle
                  report, a budget reserve, a council motion, a board decision.
                </p>
                <p style={{ margin: 0, fontSize: "var(--fs-body)", lineHeight: 1.85 }}>
                  Each one is published. None of them are assembled. Signal North
                  brings the entire public record together in one place and holds
                  it neutrally, so everyone who operates in this market works from
                  the same complete picture.{" "}
                  <strong>
                    We cover one market deeply rather than every market thinly.
                  </strong>
                </p>
                {/* Canadian-owned callout: one of the two deliberate shadows. */}
                <div
                  style={{
                    background: "var(--navy)",
                    borderRadius: "var(--radius)",
                    boxShadow: "var(--shadow-lg)",
                    padding: 36,
                    display: "flex",
                    flexDirection: "column",
                    gap: 14,
                  }}
                >
                  <span
                    className="t-label"
                    style={{ color: "var(--red-on-dark)", letterSpacing: "0.2em" }}
                  >
                    Canadian-owned and operated
                  </span>
                  <h3
                    style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: 26,
                      lineHeight: 1.3,
                      color: "#fff",
                    }}
                  >
                    Signal North is a wholly Canadian-owned company, founded and
                    headquartered in Ontario.
                  </h3>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "var(--fs-ui)",
                      lineHeight: 1.8,
                      color: "var(--blue-mist)",
                    }}
                  >
                    Critical intelligence for Canada&apos;s public-safety and
                    defence sector should be built and held here: independent,
                    domestic, and accountable to the market it serves.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          className="band band--paper band--rule"
          style={{ paddingTop: 88, paddingBottom: 88 }}
        >
          <div className="container">
            <div className="about-section">
              <div className="about-rail">
                <span className="about-rail__num">02</span>
                <span className="about-rail__label">What we stand on</span>
                <span className="about-rail__rule"></span>
              </div>
              <div className="principles">
                {PRINCIPLES.map((p) => (
                  <article className="principle" key={p.num}>
                    <span className="principle__num">{p.num}</span>
                    <h3>{p.title}</h3>
                    <p>{p.body}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section
          className="band band--navy"
          style={{
            paddingTop: "var(--sp-9)",
            paddingBottom: "var(--sp-9)",
          }}
        >
          <div className="container">
            <div className="about-section">
              <div className="about-rail about-rail--dark">
                <span className="about-rail__num">03</span>
                <span className="about-rail__label">The Principle</span>
                <span className="about-rail__rule"></span>
              </div>
              <div className="about-content">
            <h2
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 48,
                lineHeight: 1.22,
                letterSpacing: "-0.025em",
                color: "#fff",
                maxWidth: 820,
              }}
            >
              We report on the market. We never participate in it.
            </h2>
            <p
              style={{
                margin: 0,
                fontSize: "var(--fs-body)",
                lineHeight: 1.8,
                color: "var(--blue-pale)",
                maxWidth: 680,
              }}
            >
              We do not broker, resell, or advise on bids, and no one can pay to
              influence what the network shows.
            </p>
            <p
              style={{
                margin: 0,
                fontSize: 16,
                lineHeight: 1.8,
                color: "var(--blue-soft)",
                borderTop: "1px solid var(--navy-line)",
                paddingTop: 18,
                maxWidth: 680,
              }}
            >
              Where members want help acting on what they see, advisory services
              are available separately through{" "}
              <a href="#" style={{ color: "var(--blue-pale)" }}>
                Da-Ré Advisory
              </a>
              .
            </p>
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

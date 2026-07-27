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

function statCells(s: MarketingStats) {
  return [
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
      value: formatCountFloor(s.live_contracts_with_end_dates),
      label: "Contracts held, with end dates",
      note: "Each one carrying its supplier, its disclosed value, and the date it comes back to market.",
    },
    {
      value: formatCadCompact(s.live_contract_value_cad),
      label: "In contract value on the record",
      note: "The disclosed value of every live agreement we hold.",
    },
    {
      value: String(s.years_of_award_history),
      label: "Years of disclosed award history",
      note: "Enough depth to measure how long each organisation actually takes between decision and tender.",
    },
    {
      value: formatCountFloor(s.documents_last_7_days),
      label: "Public documents read this week",
      note: "Agendas, minutes, budgets, staff reports, notices and registers, collected the day they publish.",
    },
  ];
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
            <div className="section-head">
              <span className="section-head__num">01</span>
              <h2 className="t-title" style={{ fontSize: 40 }}>
                The mission
              </h2>
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(320px,1.1fr) minmax(280px,0.9fr)",
                gap: 64,
                alignItems: "start",
              }}
            >
              <p
                style={{
                  margin: 0,
                  fontFamily: "var(--font-serif)",
                  fontSize: 30,
                  lineHeight: 1.45,
                  letterSpacing: "-0.01em",
                  color: "var(--ink-soft)",
                }}
              >
                Every major purchase in Canadian public safety leaves a trail
                long before it becomes a tender, in a lifecycle report, a budget
                reserve, a council motion, a board decision.
              </p>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 18,
                  paddingTop: 6,
                }}
              >
                <p style={{ margin: 0, fontSize: 17, lineHeight: 1.85 }}>
                  Each one is published. None of them are assembled. Signal
                  North brings the entire public record together in one place
                  and holds it neutrally, so everyone who operates in this
                  market works from the same complete picture.
                </p>
                <p
                  style={{
                    margin: 0,
                    fontFamily: "var(--font-serif)",
                    fontSize: 25,
                    lineHeight: 1.5,
                    color: "var(--ink-soft)",
                    borderLeft: "2px solid var(--red)",
                    paddingLeft: 22,
                  }}
                >
                  We cover one market deeply rather than every market thinly.
                  That is the entire strategy.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section
          className="band band--cream"
          style={{ paddingTop: 88, paddingBottom: 88 }}
        >
          <div className="container">
            <div className="section-head">
              <span className="section-head__num">02</span>
              <h2 className="t-title" style={{ fontSize: 40 }}>
                The Team
              </h2>
            </div>
            <div
              className="card card--hover"
              style={{
                padding: 40,
                display: "grid",
                gridTemplateColumns: "minmax(160px,200px) minmax(300px,1fr)",
                gap: 48,
                alignItems: "start",
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div
                  style={{
                    width: "100%",
                    aspectRatio: "4/5",
                    background: "#dedbd4",
                    border: "1px solid var(--line)",
                  }}
                  data-field="portrait"
                  aria-label="Portrait placeholder"
                ></div>
                <span className="t-label" style={{ fontSize: 10 }}>
                  Portrait to be supplied
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 20,
                  maxWidth: 700,
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
                  <h3
                    style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: 36,
                      lineHeight: 1.15,
                      letterSpacing: "-0.02em",
                      color: "var(--ink)",
                    }}
                  >
                    Giancarlo Da-Ré
                  </h3>
                  <span
                    className="t-label"
                    style={{ color: "var(--red)", letterSpacing: "0.2em" }}
                  >
                    Founder &amp; Chief Executive
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: 16, lineHeight: 1.8 }}>
                  Giancarlo Da-Ré spent his career inside the Ontario
                  government&apos;s most consequential public safety files. As
                  Executive Director of Policy to the Premier, he worked across
                  a portfolio spanning public safety, emergency management,
                  justice, critical infrastructure, transportation, housing, and
                  procurement. Before that, as Director of Policy and
                  Stakeholder Relations to the Solicitor General, the ministry
                  responsible for policing, firefighting, private security, and
                  corrections in Canada&apos;s largest province, he worked on
                  law enforcement policy, public safety technology, and
                  next-generation 9-1-1 infrastructure.
                </p>
                <p style={{ margin: 0, fontSize: 16, lineHeight: 1.8 }}>
                  He built Signal North after leaving government, drawing on
                  that vantage point: writing the business cases, sitting
                  through the board cycles, and helping design the competitions
                  this platform now follows. He never took part in scoring,
                  reading, or choosing a winner, and Signal North never will.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section
          className="band band--paper"
          style={{
            borderTop: "1px solid var(--line)",
            paddingTop: 88,
            paddingBottom: 88,
          }}
        >
          <div className="container">
            <div className="section-head">
              <span className="section-head__num">03</span>
              <h2 className="t-title" style={{ fontSize: 40 }}>
                What we stand on
              </h2>
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
        </section>

        <section
          className="band band--navy"
          style={{ paddingTop: 96, paddingBottom: 96 }}
        >
          <div
            className="container"
            style={{ display: "flex", flexDirection: "column", gap: 24 }}
          >
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
                fontSize: 17,
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
                Synapse Advisory
              </a>
              .
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

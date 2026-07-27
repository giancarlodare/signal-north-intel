// Marketing home (Claude Design handoff: marketing-site/index.html).
//
// FLAG-AWARE ROOT: while PORTAL_ENABLED is off this route preserves the
// pre-incorporation behavior exactly (authenticated users are sent to the
// review queue; middleware sends everyone else to /login). With the flag on,
// it renders the designed marketing home.
//
// LIVE DATA RULE (operator 2026-07-27): time-sensitive content renders from
// the live record or the section is OMITTED, never static. Wired here: the
// "Closing soon" panel (real in-market deadlines), the coverage register
// (real on-the-record organizations), and the market-record capability rows
// (real recent awards). Capability panels 02-06 are removed until their
// engines are real (real-data-or-nothing, operator 2026-07-27).
import { redirect } from "next/navigation";
import { portalEnabled } from "@/lib/auth/roles";
import SiteHeader from "@/components/site/SiteHeader";
import SiteFooter from "@/components/site/SiteFooter";
import {
  getClosingSoon,
  getMarketingCoverage,
  getRecentAwards,
} from "@/lib/marketing/data";
import { COVERAGE_STATUS } from "@/lib/marketing/coverage-status";

export const dynamic = "force-dynamic";
export const metadata = {
  title:
    "Signal North — The intelligence network for Canadian public safety procurement",
};

// The urgency bar: fuller as the deadline nears, over the 90-day window.
function barWidth(daysLeft: number): string {
  const pct = Math.round((1 - daysLeft / 90) * 100);
  return `${Math.min(95, Math.max(5, pct))}%`;
}

// "Waterloo Regional Police, digital forensics tooling" composition, without
// doubling a buyer the title already names.
function rowTitle(buyer: string | null, title: string): string {
  if (!buyer) return title;
  return title.toLowerCase().includes(buyer.toLowerCase())
    ? title
    : `${buyer}, ${title}`;
}

type CapRow = { title: string; meta: string; val: string };
// Capability panels 02-06 REMOVED (operator 2026-07-27): the site is
// real-data-or-nothing, and an "illustrative sample" label is a crack in
// that discipline. Each panel returns when its backing engine is real
// (network view, price ranges, recompete calendar, foresight). Capability
// 01 renders live recent awards.
const CAPS: { id: string; name: string; label: string; rows: CapRow[] }[] = [
  {
    id: "01",
    name: "The market record",
    label: "Recently added",
    rows: [],
  },
];

// Coverage tabs are populated from the live record (marketing_coverage RPC);
// the whole register section is omitted when the data is unavailable, so the
// transparency feature can never show a stale list.

const ARC_STEPS = [
  { kind: "On the record", date: "Nov 2025", title: "A news story", body: "Regional press reports the camera fleet is out of warranty, raised at a board meeting." },
  { kind: "On the record", date: "Feb 2026", title: "A budget line", body: "$7.1M carried in the capital budget for camera and evidence renewal." },
  { kind: "On the record", date: "May 2026", title: "A board decision", body: "The board receives the staff report and directs procurement options." },
  { kind: "On the record", date: "Jul 2026", title: "Vendors invited in", body: "An information session is posted to the regional purchasing portal." },
];

export default async function SiteHome() {
  // Dark: exactly the old app/page.tsx behavior for signed-in users.
  if (!portalEnabled()) redirect("/corpus");

  const [closing, coverage, recentAwards] = await Promise.all([
    getClosingSoon(),
    getMarketingCoverage(),
    getRecentAwards(),
  ]);
  const coverageTabs = coverage
    ? [
        { id: "services", tab: "Police services", names: coverage.services },
        { id: "oversight", tab: "Boards and councils", names: coverage.oversight },
        { id: "government", tab: "Ministries and departments", names: coverage.government },
      ].filter((t) => t.names.length > 0)
    : [];

  return (
    <>
      <SiteHeader />
      <main>
        {/* HERO */}
        <section className="hero">
          <div className="container hero__inner">
            <div
              className="fade-rise"
              style={{ display: "flex", flexDirection: "column", gap: 30 }}
            >
              <span className="hero__eyebrow">
                Canadian public safety &amp; defence procurement
              </span>
              <h1 className="hero__title">
                The intelligence network for everyone who buys and sells in
                Canadian public safety.
              </h1>
              <p className="hero__sub" style={{ margin: 0 }}>
                Every agency, every contract, every supplier, assembled from the
                public record and held in one place.
              </p>
              <div>
                <a className="btn btn--primary" href="/contact">
                  Request access
                </a>
              </div>
            </div>
            {closing ? (
              <aside className="live-panel fade-rise" aria-label="Closing soon">
                <div className="live-panel__head">
                  <span className="live-panel__title">Closing soon</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="live-dot"></span>
                    <span
                      className="t-mono"
                      style={{
                        fontSize: 11,
                        letterSpacing: "0.12em",
                        color: "var(--blue-mist)",
                      }}
                    >
                      LIVE
                    </span>
                  </span>
                </div>
                {closing.rows.map((row, i) => (
                  <div
                    key={i}
                    className={`live-row${i === 0 ? " live-row--hot" : ""}`}
                    data-testid={`live-row-${i}`}
                  >
                    <div className="live-row__grid">
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 5,
                          minWidth: 0,
                        }}
                      >
                        <span className="live-row__kind">
                          {i === 0 ? `${row.kind} · closing next` : row.kind}
                        </span>
                        <span className="live-row__title" data-field="title">
                          {rowTitle(row.buyer, row.title)}
                        </span>
                      </div>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 7,
                          alignItems: "flex-end",
                        }}
                      >
                        <span className="live-row__days" data-field="days">
                          {row.days_left} {row.days_left === 1 ? "day" : "days"}
                        </span>
                        <span className="live-row__bar">
                          <i style={{ width: barWidth(row.days_left) }}></i>
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
                <div className="live-panel__foot">
                  <span style={{ fontSize: 13, color: "var(--blue-dim)" }}>
                    {closing.rows.length} of {closing.total_open} open in the
                    next 90 days.
                  </span>
                  <a
                    href="/contact"
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: "0.14em",
                      textTransform: "uppercase",
                      color: "#fff",
                    }}
                  >
                    Request access →
                  </a>
                </div>
              </aside>
            ) : null}
          </div>
        </section>

        {/* 01 TWO SIDES */}
        <section className="band band--paper">
          <div className="container">
            <div className="section-head" data-tabs="sides">
              <span className="section-head__num">01</span>
              <h2 className="t-title">One market, two sides of the table.</h2>
              <span style={{ flex: 1 }}></span>
              <div className="tabs">
                <button className="tab is-active" data-panel="supplier">
                  For suppliers
                </button>
                <button className="tab" data-panel="agency">
                  For public safety services
                </button>
              </div>
            </div>
            <div className="point-grid" data-panel-group="sides" data-panel="supplier">
              <article className="point">
                <h3>Every contract in your category</h3>
                <p>Who holds it, what was paid, and when it comes back to market.</p>
              </article>
              <article className="point">
                <h3>What comparable buyers paid</h3>
                <p>Observed ranges from published awards, not list prices.</p>
              </article>
              <article className="point">
                <h3>Where money is converging</h3>
                <p>Budget lines, board decisions and council motions on the same file.</p>
              </article>
              <article className="point">
                <h3>Competitions forming early</h3>
                <p>Surfaced while the requirement can still be shaped.</p>
              </article>
            </div>
            <div className="point-grid" data-panel-group="sides" data-panel="agency" hidden>
              <article className="point">
                <h3>Grants as they open</h3>
                <p>Programs your service is eligible for, with windows and conditions.</p>
              </article>
              <article className="point">
                <h3>What your peers paid</h3>
                <p>Award values normalised across services of similar size.</p>
              </article>
              <article className="point">
                <h3>Who supplies whom</h3>
                <p>Category concentration, useful before any sole-source case.</p>
              </article>
              <article className="point">
                <h3>Your recompete calendar</h3>
                <p>Every agreement approaching expiry, in one place.</p>
              </article>
            </div>
          </div>
        </section>

        {/* 02 CAPABILITIES */}
        <section className="band band--cream">
          <div className="container">
            <div className="section-head">
              <span className="section-head__num">02</span>
              <h2 className="t-title">The market record.</h2>
            </div>
            <div className="caps" data-placeholder="true">
              <div className="caps__list">
                {CAPS.map((cap) => (
                  <button
                    key={cap.id}
                    className={`caps__item${cap.id === "01" ? " is-active" : ""}`}
                    data-cap={cap.id}
                  >
                    <span className="caps__num">{cap.id}</span>
                    <span className="caps__name">{cap.name}</span>
                  </button>
                ))}
              </div>
              <div>
                {CAPS.map((cap) => (
                  <div
                    key={cap.id}
                    className="caps__detail"
                    data-cap-detail={cap.id}
                    hidden={cap.id !== "01"}
                  >
                    <div className="caps__detail-head">
                      <h3 className="t-heading">{cap.name}</h3>
                      <span className="caps__detail-label">{cap.label}</span>
                    </div>
                    {cap.id === "01" ? (
                      recentAwards ? (
                        recentAwards.map((a, i) => (
                          <div className="caps__row" key={i}>
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 4,
                                minWidth: 0,
                                flex: "1 1 220px",
                              }}
                            >
                              <span className="caps__row-title">
                                {a.title.length > 70
                                  ? `${a.title.slice(0, 70)}…`
                                  : a.title}
                              </span>
                              <span className="caps__row-meta">
                                {a.vendor ?? "Vendor not disclosed"}
                              </span>
                            </div>
                            <span className="caps__row-val">
                              {a.end_year
                                ? `Ends ${a.end_year}`
                                : a.awarded_year
                                  ? `Awarded ${a.awarded_year}`
                                  : "Date not disclosed"}
                            </span>
                          </div>
                        ))
                      ) : (
                        <div className="caps__row" data-placeholder="true">
                          <span className="caps__row-title">
                            Recent additions publish here from the live record.
                          </span>
                        </div>
                      )
                    ) : null}
                    {cap.rows.map((row, i) => (
                      <div className="caps__row" key={i}>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                            minWidth: 0,
                            flex: "1 1 220px",
                          }}
                        >
                          <span className="caps__row-title">{row.title}</span>
                          <span className="caps__row-meta">{row.meta}</span>
                        </div>
                        <span className="caps__row-val">{row.val}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* 03 COVERAGE (live register; omitted entirely when unavailable) */}
        {coverageTabs.length > 0 ? (
          <section
            className="band band--paper"
            style={{ borderTop: "1px solid var(--line)" }}
          >
            <div className="container">
              <div className="section-head">
                <span className="section-head__num">03</span>
                <h2 className="t-title">Coverage you can check, name by name.</h2>
                <span className="section-head__note">
                  Every organisation on the record, and the ones that are not
                  yet.
                </span>
              </div>
              <div className="coverage">
                <div className="coverage__tabs" data-tabs="coverage">
                  {coverageTabs.map((c, i) => (
                    <button
                      key={c.id}
                      className={`tab${i === 0 ? " is-active" : ""}`}
                      data-panel={c.id}
                    >
                      {c.tab}
                    </button>
                  ))}
                </div>
                {coverageTabs.map((c, i) => (
                  <div
                    key={c.id}
                    className="coverage__list"
                    data-panel-group="coverage"
                    data-panel={c.id}
                    hidden={i !== 0}
                  >
                    {c.names.map((n) => (
                      <span className="coverage__name" key={n}>
                        {n}
                      </span>
                    ))}
                  </div>
                ))}
                <div className="coverage__status">
                  {COVERAGE_STATUS.map((cell) => (
                    <div className="coverage__cell" key={cell.label}>
                      <span
                        className="t-label"
                        style={{
                          color:
                            cell.tone === "firm" ? "var(--navy)" : "var(--faint)",
                        }}
                      >
                        {cell.label}
                      </span>
                      <span style={{ fontSize: 15 }}>{cell.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        ) : null}

        {/* 04 PREDICTION */}
        <section className="band band--cream">
          <div className="container">
            <div className="section-head">
              <span className="section-head__num">04</span>
              <h2 className="t-title">
                Predictive modelling on the next phase of your opportunity.
              </h2>
            </div>
            <div className="arc">
              <div className="arc__rail"></div>
              <div className="arc__rail-dash"></div>
              <div className="arc__trail"></div>
              <div className="arc__cursor"></div>
              {ARC_STEPS.map((step, i) => (
                <div style={{ display: "contents" }} key={i}>
                  <div className="arc__dotcell">
                    <span className="arc__dot"></span>
                  </div>
                  <article className="arc__step">
                    <div
                      style={{
                        display: "flex",
                        gap: 18,
                        alignItems: "baseline",
                        flexWrap: "wrap",
                      }}
                    >
                      <span className="arc__kind">{step.kind}</span>
                      <span className="arc__date">{step.date}</span>
                    </div>
                    <h3>{step.title}</h3>
                    <p className="arc__body">{step.body}</p>
                  </article>
                </div>
              ))}
              <div className="arc__dotcell">
                <span className="arc__dot arc__dot--pred"></span>
              </div>
              <article className="arc__step arc__step--pred">
                <div
                  style={{
                    display: "flex",
                    gap: 18,
                    alignItems: "baseline",
                    flexWrap: "wrap",
                  }}
                >
                  <span className="arc__kind">Predicted</span>
                  <span className="arc__date">Q1 2027</span>
                </div>
                <h3>The forecast</h3>
                <p className="arc__body">
                  A tender, February to March 2027, and unlikely to slip past
                  June. Modelled from the measured interval between these steps
                  across comparable organisations.
                </p>
              </article>
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 40,
                flexWrap: "wrap",
                alignItems: "center",
                paddingTop: 44,
              }}
            >
              <p style={{ margin: 0, fontSize: 16, maxWidth: 560 }}>
                A sample file, read top to bottom, showing how a prediction is
                built. Every step is a public document, and public buying
                follows this same sequence almost every time. Because we measure
                how long each step takes at comparable services, we can model
                when the tender lands, months before it is posted.
              </p>
              <a className="btn btn--primary" href="/contact">
                Request access
              </a>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

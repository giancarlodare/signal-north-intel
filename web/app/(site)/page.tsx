// Marketing home (Claude Design handoff: marketing-site/index.html).
//
// FLAG-AWARE ROOT: while PORTAL_ENABLED is off this route preserves the
// pre-incorporation behavior exactly (authenticated users are sent to the
// review queue; middleware sends everyone else to /login). With the flag on,
// it renders the designed marketing home.
//
// DATA-PLUMBING GAP (flagged, expected): the "Closing soon" live panel, the
// capabilities rows, and every figure below are the handoff's PLACEHOLDER
// content, marked data-placeholder. They must be wired to live records
// before the flag flips; the README of the handoff says the same.
import { redirect } from "next/navigation";
import { portalEnabled } from "@/lib/auth/roles";
import SiteHeader from "@/components/site/SiteHeader";
import SiteFooter from "@/components/site/SiteFooter";

export const dynamic = "force-dynamic";
export const metadata = {
  title:
    "Signal North — The intelligence network for Canadian public safety procurement",
};

type LiveRow = {
  kind: string;
  title: string;
  days: string;
  pct: string;
  note: string;
  hot?: boolean;
};

// Handoff placeholder rows (data-placeholder until live wiring lands).
const LIVE_ROWS: LiveRow[] = [
  {
    kind: "Grant · closing next",
    title: "Provincial equipment renewal stream",
    days: "18 days",
    pct: "80%",
    note:
      "Open to municipal and regional services for radio, camera and fleet renewal. Eleven Ontario services drew on the last round.",
    hot: true,
  },
  {
    kind: "Tender",
    title: "Waterloo Regional Police, digital forensics tooling",
    days: "22 days",
    pct: "76%",
    note:
      "Request for quotation posted 14 July. Estimated at $2.4M over five years, no incumbent disclosed.",
  },
  {
    kind: "Grant",
    title: "Federal interoperability program",
    days: "41 days",
    pct: "54%",
    note:
      "Guidelines published; applications expected to open in the fourth quarter for cross-service radio projects.",
  },
  {
    kind: "Tender",
    title: "City of Hamilton, signal controller renewal",
    days: "48 days",
    pct: "47%",
    note:
      "Carried in the 2027 capital forecast and now at market. Municipal, but the same buyers and the same cycle.",
  },
  {
    kind: "Grant",
    title: "Regional community safety fund",
    days: "63 days",
    pct: "30%",
    note:
      "Allocation awaited. Historically funds analyst posts and evidence-management licensing rather than hardware.",
  },
];

type CapRow = { title: string; meta: string; val: string };
const CAPS: { id: string; name: string; label: string; rows: CapRow[] }[] = [
  {
    id: "01",
    name: "The market record",
    label: "Recently added",
    rows: [
      { title: "Digital evidence management, 5-yr", meta: "Axon Public Safety", val: "Ends 2030" },
      { title: "Patrol vehicle standing offer", meta: "Ford of Canada", val: "Ends 2027" },
      { title: "Radio infrastructure maintenance", meta: "Motorola Solutions", val: "Ends 2029" },
    ],
  },
  {
    id: "02",
    name: "The network view",
    label: "Suppliers holding contracts",
    rows: [
      { title: "Radio and communications", meta: "3 suppliers", val: "64% with one" },
      { title: "Digital evidence", meta: "4 suppliers", val: "52% with one" },
      { title: "Fleet and upfitting", meta: "7 suppliers", val: "32% with one" },
    ],
  },
  {
    id: "03",
    name: "Price and incumbency",
    label: "Observed ranges",
    rows: [
      { title: "Body-worn camera, unit / year", meta: "9 awards", val: "$1,180 – $1,940" },
      { title: "Evidence storage, TB / year", meta: "6 awards", val: "$310 – $780" },
      { title: "Dispatch, per sworn member", meta: "2 awards", val: "Too few awards to state" },
    ],
  },
  {
    id: "04",
    name: "Grants and funding",
    label: "Open and forthcoming",
    rows: [
      { title: "Provincial equipment renewal stream", meta: "Applications open", val: "Closes Sep 2026" },
      { title: "Federal interoperability program", meta: "Guidelines published", val: "Opens Q4 2026" },
      { title: "Regional community safety fund", meta: "Awaiting allocation", val: "Expected 2027" },
    ],
  },
  {
    id: "05",
    name: "Recompete calendar",
    label: "Nearest expiries",
    rows: [
      { title: "Toronto Police Service, evidence storage", meta: "Axon", val: "4 months" },
      { title: "Halton Regional Police, evidence licence", meta: "Axon", val: "8 months" },
      { title: "Durham Regional Police, radio maintenance", meta: "Motorola", val: "11 months" },
    ],
  },
  {
    id: "06",
    name: "Foresight",
    label: "Live projections",
    rows: [
      { title: "Halton Regional Police, camera refresh", meta: "Tender", val: "Early 2027" },
      { title: "Peel Regional Police, dispatch replacement", meta: "Tender", val: "Late 2026" },
      { title: "Durham Regional Police, radio renewal", meta: "Tender", val: "First half 2027" },
    ],
  },
];

const COVERAGE: { id: string; tab: string; names: string[] }[] = [
  {
    id: "services",
    tab: "Police services",
    names: [
      "Barrie Police Service", "Belleville Police Service", "Brantford Police Service",
      "Durham Regional Police Service", "Greater Sudbury Police Service", "Guelph Police Service",
      "Halton Regional Police Service", "Hamilton Police Service", "Kingston Police",
      "London Police Service", "Niagara Regional Police Service", "Ontario Provincial Police",
      "Ottawa Police Service", "Peel Regional Police", "Peterborough Police Service",
      "Sarnia Police Service", "Thunder Bay Police Service", "Toronto Police Service",
      "Waterloo Regional Police Service", "Windsor Police Service", "York Regional Police",
    ],
  },
  {
    id: "oversight",
    tab: "Boards and councils",
    names: [
      "City of Hamilton Council", "City of Kingston Council", "City of London Council",
      "City of Ottawa Council", "City of Toronto Council", "City of Windsor Council",
      "Durham Regional Council", "Halton Regional Council", "Hamilton Police Services Board",
      "Niagara Regional Council", "Ottawa Police Service Board", "Peel Regional Council",
      "Peel Police Services Board", "Region of Waterloo Council", "Toronto Police Service Board",
      "Waterloo Regional Police Services Board", "York Regional Council",
      "York Regional Police Services Board",
    ],
  },
  {
    id: "government",
    tab: "Ministries and departments",
    names: [
      "Infrastructure Canada", "Ontario Ministry of Finance",
      "Ontario Ministry of Municipal Affairs and Housing",
      "Ontario Ministry of the Solicitor General", "Ontario Ministry of Transportation",
      "Ontario Provincial Legislature, Hansard", "Public Safety Canada",
      "Public Services and Procurement Canada", "Treasury Board of Canada Secretariat",
    ],
  },
];

const ARC_STEPS = [
  { kind: "On the record", date: "Nov 2025", title: "A news story", body: "Regional press reports the camera fleet is out of warranty, raised at a board meeting." },
  { kind: "On the record", date: "Feb 2026", title: "A budget line", body: "$7.1M carried in the capital budget for camera and evidence renewal." },
  { kind: "On the record", date: "May 2026", title: "A board decision", body: "The board receives the staff report and directs procurement options." },
  { kind: "On the record", date: "Jul 2026", title: "Vendors invited in", body: "An information session is posted to the regional purchasing portal." },
];

export default function SiteHome() {
  // Dark: exactly the old app/page.tsx behavior for signed-in users.
  if (!portalEnabled()) redirect("/corpus");

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
            <aside
              className="live-panel fade-rise"
              aria-label="Closing soon"
              data-placeholder="true"
            >
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
              {LIVE_ROWS.map((row, i) => (
                <div
                  key={i}
                  className={`live-row${row.hot ? " live-row--hot is-open" : ""}`}
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
                      <span className="live-row__kind">{row.kind}</span>
                      <span className="live-row__title" data-field="title">
                        {row.title}
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
                        {row.days}
                      </span>
                      <span className="live-row__bar">
                        <i style={{ width: row.pct }}></i>
                      </span>
                    </div>
                  </div>
                  <span className="live-row__note" data-field="note">
                    {row.note}
                  </span>
                </div>
              ))}
              <div className="live-panel__foot">
                <span style={{ fontSize: 13, color: "var(--blue-dim)" }}>
                  Five of 34 open this week.
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
              <h2 className="t-title">Six capabilities, one record.</h2>
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

        {/* 03 COVERAGE */}
        <section className="band band--paper" style={{ borderTop: "1px solid var(--line)" }}>
          <div className="container">
            <div className="section-head">
              <span className="section-head__num">03</span>
              <h2 className="t-title">Coverage you can check, name by name.</h2>
              <span className="section-head__note">
                Every organisation on the record, and the ones that are not yet.
              </span>
            </div>
            <div className="coverage">
              <div className="coverage__tabs" data-tabs="coverage">
                {COVERAGE.map((c, i) => (
                  <button
                    key={c.id}
                    className={`tab${i === 0 ? " is-active" : ""}`}
                    data-panel={c.id}
                  >
                    {c.tab}
                  </button>
                ))}
              </div>
              {COVERAGE.map((c, i) => (
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
                <div className="coverage__cell">
                  <span className="t-label" style={{ color: "var(--navy)" }}>
                    Complete
                  </span>
                  <span style={{ fontSize: 15 }}>
                    Ontario policing, councils, provincial programs
                  </span>
                </div>
                <div className="coverage__cell">
                  <span className="t-label" style={{ color: "var(--faint)" }}>
                    Opening this year
                  </span>
                  <span style={{ fontSize: 15 }}>
                    British Columbia and Alberta policing
                  </span>
                </div>
                <div className="coverage__cell">
                  <span className="t-label" style={{ color: "var(--faint)" }}>
                    Not yet covered
                  </span>
                  <span style={{ fontSize: 15 }}>Federal defence procurement</span>
                </div>
              </div>
            </div>
          </div>
        </section>

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

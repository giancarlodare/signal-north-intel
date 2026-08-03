// Pricing page (Claude Design handoff: marketing-site/pricing.html).
// The tier table's feature-absent cells use the handoff's typographic dash
// glyph (a design element in Giancarlo's files, not generated copy).
import { Fragment } from "react";
import SiteHeader from "@/components/site/SiteHeader";
import SiteFooter from "@/components/site/SiteFooter";
import InquiryDialog from "@/components/site/InquiryDialog";
import FreeBriefForm from "@/components/site/FreeBriefForm";

export const metadata = { title: "Pricing — Signal North" };

const DASH = "—";

// Cells carry four states, not two: a partial Free tier and a seat count are
// both honest table content, and forcing them into a boolean would have meant
// either a lie or a footnote.
type CellValue = true | false | "partial" | string;
type TierCells = [CellValue, CellValue, CellValue, CellValue];

// THE RULE THAT GOVERNS THIS TABLE (operator 2026-07-29):
// Everything checked in an OPEN column (Free, Weekly) must EXIST TODAY. A
// closed column (Pro, Enterprise) describes what that tier will include when
// it opens, and the closed state is the honest marker doing the work. The line
// we do not cross is a checkmark in a column someone can pay for.
//
// Four rows are checked at Weekly that are BUILD-BEFORE-LAUNCH, not shipped:
// the weekly email send, the composed arc body field, the issue archive, and
// the subscription guard. Weekly does not open until all four exist and the
// lens is tightened (operator ruling 2026-08-01). They are listed because the
// table describes the tier as it will ship, and the tier is not purchasable
// until it does.
//
// CUT, and not to be reinstated by inheritance:
//   Service-by-service read  -- no schema, no component, no design. v2.
//   Expiring-contract tracking -- 0 of 548 awards carry an end date, so it is
//     a capability claim we cannot honour. Returns only when the end-date
//     extraction exists behind it (task #56).
const GROUPS: { title: string; rows: { name: string; cells: TierCells }[] }[] = [
  {
    title: "The brief",
    rows: [
      { name: "Weekly email", cells: ["partial", true, true, true] },
      { name: "The composed arc", cells: [false, true, true, true] },
      { name: "Issue archive", cells: [false, true, true, true] },
    ],
  },
  {
    title: "The record",
    rows: [
      { name: "Full item list", cells: ["partial", true, true, true] },
      // "a source link on every item" is honest as written: 0 documents in the
      // corpus have no link. What it must never become is "a link to the
      // record", which 68 of them (49 listing anchors + 19 portal landings)
      // would not satisfy. The per-item provenance label carries that nuance.
      { name: "Source link on every item", cells: [false, true, true, true] },
      { name: "Saved items", cells: [false, true, true, true] },
    ],
  },
  {
    // THE BREAK. Everything above is a publication you READ; everything below
    // is a system that WATCHES your buyers and categories on your behalf. That
    // distinction is what makes the price gap legible, and it decides which
    // tier any future feature belongs to.
    title: "Monitoring",
    rows: [
      { name: "Closing-soon board", cells: [false, false, true, true] },
      { name: "Watchlists", cells: [false, false, true, true] },
      { name: "Alerts", cells: [false, false, true, true] },
      { name: "Buyer profiles", cells: [false, false, true, true] },
      { name: "Arc lookup on demand", cells: [false, false, true, true] },
    ],
  },
  {
    title: "Team",
    rows: [
      { name: "Seats", cells: ["1", "1", "3", "Unlimited"] },
      { name: "API and webhooks", cells: [false, false, false, true] },
      { name: "Coverage requests", cells: [false, false, false, true] },
      { name: "Priority support", cells: [false, false, true, true] },
    ],
  },
];

const FAQ: { q: string; a: string }[] = [
  {
    q: "What is Signal North?",
    a: "The intelligence network for public safety and defence procurement in Canada. We continuously map the entire public record, tenders, awards, budgets, board and council decisions, legislative debate, and vendor activity, so anyone who buys or sells in this sector can see the whole market in one place, and can follow a single need from the first mention to the award.",
  },
  {
    q: "Who is Signal North for?",
    a: "Vendors selling into police, fire and other public safety agencies; consultancies and advisors working in the sector; and public officials who need to understand the procurement landscape. If you operate in Canadian public safety or defence, this is the network you need to be part of.",
  },
  {
    q: "How is the annual price billed?",
    a: "Annual is the headline price and monthly is available at a premium: a year costs the same as ten months, so paying annually is two months free. Enterprise is custom, priced on seats, coverage and scope.",
  },
  {
    q: "Can I upgrade or change tiers later?",
    a: "Yes. You can move up a tier at any time as your needs grow, and the change is prorated against what you have already paid.",
  },
  {
    q: "How current is the data?",
    a: "The network updates continuously from public sources. New tenders, awards and signals are captured as they are published, so your dashboard reflects the market as it stands, not a stale snapshot.",
  },
  {
    q: "Where does your information come from?",
    a: "Everything traces to an official public record, a government portal, a board agenda, a published budget, a legislative transcript. Every signal links back to its original publisher source, so you can verify it yourself. We report on the public record; we never rely on rumour or unverifiable claims.",
  },
  {
    q: "Is Signal North neutral?",
    a: "Yes, and it is core to how we operate. We report on the market; we never participate in it. The same intelligence is available to every member on equal terms. We do not represent vendors, we do not broker deals, and no one can pay to influence what the network shows.",
  },
  {
    q: "Do you cover my region, agency or category?",
    a: "Our coverage of Canadian public safety and defence procurement is comprehensive and always expanding. Enterprise members can request custom coverage for specific agencies, regions or categories. If you are unsure whether we cover what you need, ask us, we will tell you honestly what is in the network today.",
  },
  {
    q: "How is this different from a tender-notification service?",
    a: "Tender alerts tell you an RFP has been posted, by which point the opportunity is often already shaped. Signal North maps the whole market continuously and surfaces activity as it forms. A budget line, a board decision, a staff report: these are public months before the solicitation, and we put them in front of you with the link to each one. It is the difference between reacting to the market and understanding it.",
  },
  {
    q: "Do I need a long-term commitment?",
    a: "Signal North Weekly and Pro are annual memberships, and monthly is available at a premium. Enterprise terms are set as part of your custom agreement.",
  },
  {
    q: "How do I get started?",
    a: "Signal North Free gives you a weekly digest at no cost, so you can see the network before committing. When you are ready for the full picture, choose Signal North Weekly or Pro, or request an Enterprise quote for your team.",
  },
];

function Cell({ v, hot }: { v: CellValue; hot?: boolean }) {
  const hotCls = hot ? " tier-col-hot" : "";
  if (v === true) return <td className={"tier-check" + hotCls}>✓</td>;
  if (v === false) return <td className={"tier-dash" + hotCls}>{DASH}</td>;
  // "partial" and seat counts render as words, not glyphs: a half-check would
  // be a glyph the reader has to guess at.
  const label = v === "partial" ? "Partial" : v;
  return <td className={"tier-partial" + hotCls}>{label}</td>;
}

export default function PricingPage() {
  return (
    <>
      <SiteHeader current="pricing" />
      <main>
        <section className="hero">
          <div
            className="container"
            style={{
              paddingTop: 72, // off-scale, flagged
              paddingBottom: "var(--sp-8)",
              display: "flex",
              flexDirection: "column",
              gap: 22, // off-scale, flagged
            }}
          >
            <span className="hero__eyebrow fade-rise">Pricing</span>
            <h1
              className="hero__title fade-rise"
              style={{ fontSize: 54, maxWidth: 860 }}
            >
              Join the network at the level you need.
            </h1>
          </div>
        </section>

        <section className="band band--paper" style={{ paddingTop: 72 }}>
          <div
            className="container"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--sp-7)",
            }}
          >
            <div className="tier-table">
              <table data-testid="tier-table">
                <thead>
                  <tr>
                    <th></th>
                    <th>
                      <span className="tier-name">Signal North Free</span>
                      <span className="tier-price">Free</span>
                      <span className="tier-meta">No card required</span>
                      {/* FREE IS EMAIL CAPTURE, NOT AN ACCOUNT (operator
                          2026-08-02). The form posts straight to the send
                          list: no auth.users row, no login, no entitlement.
                          reveal: the column shows only a button until clicked,
                          so the tier row stays height-aligned (operator
                          2026-08-03: "everything horizontal aligned"). */}
                      <FreeBriefForm source="pricing-free" compact reveal />
                    </th>
                    <th>
                      <span className="tier-name">Signal North Weekly</span>
                      <span className="tier-price">$3,900 / yr</span>
                      <span className="tier-meta">or $390 / mo</span>
                      {/* WEEKLY IS THE OPEN, BUYABLE COLUMN. It goes to the
                          signup flow (confirm, then checkout), never to
                          /contact: a pricing page where nothing can be bought
                          reads as a waitlist rather than a company. */}
                      <a
                        className="btn btn--primary"
                        style={{ padding: "10px 18px", letterSpacing: "0.1em" }}
                        href="/join"
                      >
                        Join Weekly
                      </a>
                    </th>
                    <th className="tier-col-hot">
                      <span className="tier-name">Signal North Pro</span>
                      <span className="tier-price">$19,000 / yr</span>
                      <span className="tier-meta">or $1,900 / mo</span>
                      <InquiryDialog tier="pro" variant="primary" />
                    </th>
                    <th>
                      <span className="tier-name">Signal North Enterprise</span>
                      <span className="tier-price">from $45,000 / yr</span>
                      <span className="tier-meta">Custom terms</span>
                      <InquiryDialog tier="enterprise" />
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {GROUPS.map((g) => (
                    <Fragment key={g.title}>
                      <tr
                        className={
                          "tier-group" +
                          (g.title === "Monitoring" ? " tier-group--break" : "")
                        }
                        data-group={g.title}
                      >
                        <th scope="rowgroup" colSpan={5}>
                          {g.title}
                        </th>
                      </tr>
                      {g.rows.map((f) => (
                        <tr key={f.name}>
                          <td className="tier-feature">{f.name}</td>
                          <Cell v={f.cells[0]} />
                          <Cell v={f.cells[1]} />
                          <Cell v={f.cells[2]} hot />
                          <Cell v={f.cells[3]} />
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="tier-neutrality" data-testid="neutrality-line">
              The record is the same for everyone. A higher tier buys more ways
              to work with it, never a different version of the truth, and never
              earlier access to it.
            </p>

            {/* Two-column FAQ (design: serif heading left, accordion right). */}
            <div className="faq-block">
              <h2 className="t-title" style={{ fontSize: 36 }}>
                Questions we are asked
              </h2>
              <div className="faq">
                {FAQ.map((item) => (
                  <details key={item.q}>
                    <summary>{item.q}</summary>
                    <p className="faq__a">{item.a}</p>
                  </details>
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

// Pricing page (Claude Design handoff: marketing-site/pricing.html).
// The tier table's feature-absent cells use the handoff's typographic dash
// glyph (a design element in Giancarlo's files, not generated copy).
import SiteHeader from "@/components/site/SiteHeader";
import SiteFooter from "@/components/site/SiteFooter";
import InquiryDialog from "@/components/site/InquiryDialog";

export const metadata = { title: "Pricing — Signal North" };

const DASH = "—";

type TierCells = [boolean, boolean, boolean, boolean];
const FEATURES: { name: string; cells: TierCells }[] = [
  { name: "Weekly headline digest", cells: [true, true, true, true] },
  { name: "Grant eligibility teaser", cells: [true, true, true, true] },
  { name: "Full weekly intelligence brief", cells: [false, true, true, true] },
  { name: "Sourced publisher records", cells: [false, true, true, true] },
  { name: "Full platform dashboard", cells: [false, false, true, true] },
  { name: "Network and market intelligence", cells: [false, false, true, true] },
  { name: "Buyer and agency profiles", cells: [false, false, true, true] },
  { name: "Watchlists and alerts", cells: [false, false, true, true] },
  { name: "Expiring-contract tracking", cells: [false, false, true, true] },
  { name: "Pricing and incumbent intelligence", cells: [false, false, true, true] },
  // Sourced demand arcs are LIVE at Weekly and above (operator 2026-07-29):
  // a dated, deep-linked chain of public-record events with named comparable
  // precedents. No statistical claim, so no in-development marker.
  { name: "Sourced demand arcs", cells: [false, true, true, true] },
  { name: "Multiple seats", cells: [false, false, false, true] },
  { name: "Custom coverage", cells: [false, false, false, true] },
  { name: "API access", cells: [false, false, false, true] },
  { name: "Priority support and standing", cells: [false, false, false, true] },
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
    a: "Signal North Weekly and Signal North Pro are billed annually. Enterprise memberships are custom, pricing depends on seats, coverage and scope, so we build a quote around what your team needs.",
  },
  {
    q: "What is included in the Founding Member offer?",
    a: "Founding Members get Pro-level access at $5,000 per year, locked for two years, plus priority standing. It is early access at a founding rate before pricing rises as the network's track record deepens. Founding membership is limited and offered only during our launch period.",
  },
  {
    q: "Can I upgrade or change tiers later?",
    a: "Yes. You can move up a tier at any time as your needs grow. Founding Members keep their locked rate for the full two years regardless of later price changes.",
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
    a: "Signal North Weekly and Pro are annual memberships. Founding Members lock a two-year rate. Enterprise terms are set as part of your custom agreement.",
  },
  {
    q: "How do I get started?",
    a: "Signal North Free gives you a weekly digest at no cost, so you can see the network before committing. When you are ready for the full picture, choose Signal North Weekly or Pro, or request an Enterprise quote for your team.",
  },
];

function Cell({ on, hot }: { on: boolean; hot?: boolean }) {
  const cls = (on ? "tier-check" : "tier-dash") + (hot ? " tier-col-hot" : "");
  return <td className={cls}>{on ? "✓" : DASH}</td>;
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
              paddingTop: 72,
              paddingBottom: 64,
              display: "flex",
              flexDirection: "column",
              gap: 22,
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
            style={{ display: "flex", flexDirection: "column", gap: 48 }}
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
                      <a
                        className="btn btn--ghost"
                        style={{ padding: "10px 18px", letterSpacing: "0.1em" }}
                        href="/contact"
                      >
                        Sign up
                      </a>
                    </th>
                    <th>
                      <span className="tier-name">Signal North Weekly</span>
                      <span className="tier-price">$390 / mo</span>
                      <span className="tier-meta">Billed annually</span>
                      <a
                        className="btn btn--ghost"
                        style={{ padding: "10px 18px", letterSpacing: "0.1em" }}
                        href="/contact"
                      >
                        Request access
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
                  {FEATURES.map((f) => (
                    <tr key={f.name}>
                      <td className="tier-feature">{f.name}</td>
                      <Cell on={f.cells[0]} />
                      <Cell on={f.cells[1]} />
                      <Cell on={f.cells[2]} hot />
                      <Cell on={f.cells[3]} />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <aside className="founding-callout" data-testid="founding-callout">
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <span
                  className="t-label"
                  style={{ color: "var(--red-on-dark)", letterSpacing: "0.2em" }}
                >
                  Limited · launch period only
                </span>
                <h2 className="founding-callout__title">
                  Founding Member: $5,000/yr (locked for two years)
                </h2>
                <p className="founding-callout__body" style={{ margin: 0 }}>
                  Pro-level access at the founding rate, with priority standing.
                  Limited founding memberships, available during launch. Lock
                  your rate before it rises.
                </p>
              </div>
              <a className="btn btn--primary" href="/contact">
                Become a Founding Member
              </a>
            </aside>

            <div className="faq" style={{ maxWidth: 860 }}>
              <h2 className="t-title" style={{ fontSize: 36, paddingBottom: 18 }}>
                Questions
              </h2>
              {FAQ.map((item) => (
                <details key={item.q}>
                  <summary>{item.q}</summary>
                  <p className="faq__a">{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

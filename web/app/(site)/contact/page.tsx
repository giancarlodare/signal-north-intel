// Request-access page (Claude Design handoff: marketing-site/contact.html).
// BACKEND GAP (flagged, expected): the form submits via the handoff's mailto
// fallback (SiteInteractions); swap for a pipeline endpoint / CRM webhook
// when one exists.
import SiteHeader from "@/components/site/SiteHeader";
import SiteFooter from "@/components/site/SiteFooter";

export const metadata = { title: "Request access — Signal North" };

export default function ContactPage() {
  return (
    <>
      <SiteHeader />
      <main>
        <section className="hero">
          <div
            className="container"
            style={{
              paddingTop: 80,
              paddingBottom: 64,
              display: "grid",
              gridTemplateColumns: "minmax(300px,1.1fr) minmax(280px,1fr)",
              gap: 80,
              alignItems: "end",
            }}
          >
            <div
              className="fade-rise"
              style={{ display: "flex", flexDirection: "column", gap: 24 }}
            >
              <span className="hero__eyebrow">Contact</span>
              <h1 className="hero__title" style={{ fontSize: 54 }}>
                Talk to us about coverage, Pro, or Enterprise.
              </h1>
            </div>
            <p
              className="fade-rise"
              style={{
                margin: 0,
                fontSize: 18,
                fontWeight: 300,
                lineHeight: 1.75,
                color: "var(--blue-mist)",
              }}
            >
              Weekly is self-serve: you can join at /join and be reading
              this week&apos;s brief today. This page is for everything that
              needs a conversation, coverage requests, Pro early access, and
              Enterprise terms.
            </p>
          </div>
        </section>

        <section
          className="band band--paper"
          style={{ paddingTop: 88, paddingBottom: 88 }}
        >
          <div
            className="container"
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(320px,1.15fr) minmax(280px,1fr)",
              gap: 80,
              alignItems: "start",
            }}
          >
            <form
              className="card"
              data-form="request-access"
              data-testid="request-access-form"
              style={{
                padding: "36px 38px",
                display: "flex",
                flexDirection: "column",
                gap: 24,
              }}
            >
              <h2 className="t-heading">Request access</h2>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 20,
                }}
              >
                <div className="field">
                  <label htmlFor="f-name">Name</label>
                  <input id="f-name" name="name" placeholder="Full name" required />
                </div>
                <div className="field">
                  <label htmlFor="f-org">Organisation</label>
                  <input
                    id="f-org"
                    name="org"
                    placeholder="Company or agency"
                    required
                  />
                </div>
                <div className="field">
                  <label htmlFor="f-email">Work email</label>
                  <input
                    id="f-email"
                    name="email"
                    type="email"
                    placeholder="name@organisation.ca"
                    required
                  />
                </div>
                <div className="field">
                  <label htmlFor="f-phone">Telephone</label>
                  <input id="f-phone" name="phone" placeholder="Optional" />
                </div>
              </div>
              <div className="field">
                <label>I am here as</label>
                <div className="chip-row chip-row--select">
                  <button type="button" className="chip is-active">
                    A supplier
                  </button>
                  <button type="button" className="chip">
                    A public safety service
                  </button>
                  <button type="button" className="chip">
                    Government
                  </button>
                  <button type="button" className="chip">
                    An advisor
                  </button>
                </div>
              </div>
              <div className="field">
                <label htmlFor="f-scope">
                  Which organisations or categories matter to you
                </label>
                <textarea
                  id="f-scope"
                  name="scope"
                  rows={4}
                  placeholder="For example: digital evidence across the GTA services, or fleet across Ontario regional police."
                ></textarea>
              </div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 22,
                  flexWrap: "wrap",
                }}
              >
                <button
                  className="btn btn--primary"
                  type="submit"
                  data-submit
                  style={{
                    padding: "14px 30px",
                    letterSpacing: "0.08em",
                    fontSize: 12,
                  }}
                >
                  Request access
                </button>
                <span style={{ fontSize: 14, color: "var(--muted)" }} data-hint></span>
              </div>
            </form>

            <aside style={{ display: "flex", flexDirection: "column", gap: 36 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <span className="t-label">What happens next</span>
                <div style={{ display: "flex", gap: 16, alignItems: "baseline" }}>
                  <span className="t-mono" style={{ color: "var(--red)" }}>
                    01
                  </span>
                  <span style={{ fontSize: 16 }}>
                    We confirm the organisations and categories you care about.
                  </span>
                </div>
                <div style={{ display: "flex", gap: 16, alignItems: "baseline" }}>
                  <span className="t-mono" style={{ color: "var(--red)" }}>
                    02
                  </span>
                  <span style={{ fontSize: 16 }}>
                    Thirty minutes with an analyst, run against your real market.
                  </span>
                </div>
                <div style={{ display: "flex", gap: 16, alignItems: "baseline" }}>
                  <span className="t-mono" style={{ color: "var(--red)" }}>
                    03
                  </span>
                  <span style={{ fontSize: 16 }}>
                    A written scope the same week, or an honest answer that our
                    coverage does not yet serve you.
                  </span>
                </div>
              </div>
              <address
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  borderTop: "1px solid var(--line)",
                  paddingTop: 24,
                  fontStyle: "normal",
                }}
              >
                <span style={{ fontSize: 16, color: "var(--ink)" }}>
                  giancarlo@signalnorthintel.com
                </span>
                <span style={{ fontSize: 16 }}>+1 647 221 8123</span>
                <span style={{ fontSize: 16, color: "var(--muted)" }}>
                  Toronto, Ontario
                </span>
              </address>
            </aside>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

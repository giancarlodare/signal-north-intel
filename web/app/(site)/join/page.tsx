// Join Weekly: the public signup (operator 2026-08-02).
//
// "No one should have to already have an account to become a customer." This
// page is the fix for that. It is deliberately PUBLIC (see SITE_PATHS in
// lib/auth/roles.ts): gating it behind a session would mean you need an
// account to get an account.
//
// It is NOT the free-brief form. Free is email capture with no account and no
// login, and it lives in FreeBriefForm on the home and pricing pages. The two
// stay distinct because they are distinct products, and because Free having
// no login is what keeps the entitlement layer small until Pro arrives.
import SiteHeader from "@/components/site/SiteHeader";
import SiteFooter from "@/components/site/SiteFooter";
import JoinWeeklyForm from "@/components/site/JoinWeeklyForm";

export const dynamic = "force-dynamic";
export const metadata = { title: "Join Weekly — Signal North" };

// The three steps, stated before they happen. Someone handing over an email
// address should know it ends at a card, and know it does not end there yet.
const STEPS = [
  {
    n: "1",
    t: "Confirm your address",
    d: "We send one link. Clicking it creates your account and proves the address works, which matters because the brief is delivered to it.",
  },
  {
    n: "2",
    t: "Choose your term",
    d: "$3,900 a year, or $390 a month. The link lands you on your account page, where both are one button each.",
  },
  {
    n: "3",
    t: "Read Thursday",
    d: "The composed arc, the full item list, and a source link on every item.",
  },
];

export default function JoinPage() {
  return (
    <>
      <SiteHeader current="pricing" />
      <main>
        <section className="hero">
          <div
            className="container"
            style={{
              paddingTop: 80,
              paddingBottom: 72,
              display: "grid",
              gridTemplateColumns: "minmax(300px,1.05fr) minmax(300px,0.95fr)",
              gap: 72,
              alignItems: "start",
            }}
          >
            <div
              className="fade-rise"
              style={{ display: "flex", flexDirection: "column", gap: 26 }}
            >
              <span className="hero__eyebrow">Signal North Weekly</span>
              <h1 className="hero__title" style={{ fontSize: 50 }}>
                One brief a week, and the record behind every line of it.
              </h1>
              <p
                style={{
                  margin: 0,
                  fontSize: 17,
                  lineHeight: 1.8,
                  color: "var(--muted)",
                  maxWidth: 520,
                }}
              >
                Start with your work email. Nothing is charged until you have
                confirmed the address and picked a term.
              </p>

              <ol
                data-testid="join-steps"
                style={{
                  margin: 0,
                  padding: 0,
                  listStyle: "none",
                  display: "flex",
                  flexDirection: "column",
                  gap: 22,
                  paddingTop: 8,
                }}
              >
                {STEPS.map((s) => (
                  <li
                    key={s.n}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "auto 1fr",
                      gap: 16,
                      alignItems: "start",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "var(--font-serif)",
                        fontSize: 19,
                        color: "var(--red)",
                        lineHeight: 1.4,
                      }}
                    >
                      {s.n}
                    </span>
                    <span
                      style={{ display: "flex", flexDirection: "column", gap: 4 }}
                    >
                      <span style={{ fontSize: 16, fontWeight: 600 }}>
                        {s.t}
                      </span>
                      <span
                        style={{
                          fontSize: 15,
                          lineHeight: 1.75,
                          color: "var(--muted)",
                        }}
                      >
                        {s.d}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            </div>

            <aside
              className="card fade-rise"
              style={{
                padding: "32px 34px",
                display: "flex",
                flexDirection: "column",
                gap: 18,
              }}
              data-testid="join-panel"
            >
              <div
                style={{ display: "flex", flexDirection: "column", gap: 6 }}
              >
                <span className="t-label">Join Weekly</span>
                <span
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontSize: 30,
                    lineHeight: 1.2,
                  }}
                >
                  $3,900 / yr
                </span>
                <span style={{ fontSize: 14, color: "var(--muted)" }}>
                  or $390 / mo, cancel by writing to us
                </span>
              </div>

              <JoinWeeklyForm />

              <p
                style={{
                  margin: 0,
                  fontSize: 13,
                  lineHeight: 1.7,
                  color: "var(--faint)",
                  borderTop: "1px solid var(--line-soft)",
                  paddingTop: 16,
                }}
              >
                Already a member?{" "}
                <a href="/login" style={{ fontSize: 13 }}>
                  Log in
                </a>
                . Wanted the free brief instead?{" "}
                <a href="/pricing" style={{ fontSize: 13 }}>
                  It is on the pricing page
                </a>
                , and it needs no account at all.
              </p>
            </aside>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

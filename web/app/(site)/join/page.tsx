// Join Weekly: the public signup (operator 2026-08-02, template 2026-08-03).
//
// Same centred template as /login (the operator's original for both): logo
// mark, serif heading that says what the page is for, one honest instruction
// line, one email input, one full-width button, a hairline, a small footer
// line. NO password fallback -- this is a signup, not a sign-in.
//
// It is deliberately PUBLIC (see SITE_PATHS in lib/auth/roles.ts): gating it
// behind a session would mean you need an account to get an account.
//
// CONFIRM BEFORE PAY: the emailed link creates the account and proves the
// address; the term is chosen and paid on the account page after that, never
// before. The instruction line states that sequence honestly.
import SiteHeader, { BrandMark } from "@/components/site/SiteHeader";
import JoinWeeklyForm from "@/components/site/JoinWeeklyForm";

export const dynamic = "force-dynamic";
export const metadata = { title: "Join Weekly — Signal North" };

export default function JoinPage() {
  return (
    <>
      <SiteHeader />
      <main className="login-wrap">
        <div className="login-card fade-rise">
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 18,
              textAlign: "center",
            }}
          >
            <BrandMark size={34} fill="#ffffff" />
            <h1
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 30,
                lineHeight: 1.2,
                letterSpacing: "-0.015em",
                color: "#fff",
              }}
            >
              Join Signal North Weekly
            </h1>
            <p
              style={{
                margin: 0,
                fontSize: 15,
                lineHeight: 1.75,
                color: "var(--blue-soft)",
              }}
            >
              Enter your work email and we send one link. Clicking it creates
              your account and confirms the address. You choose your term, $3,900
              a year or $390 a month, and pay on your account page after that,
              never before.
            </p>
          </div>

          <JoinWeeklyForm />

          <div
            style={{
              borderTop: "1px solid var(--navy-mid)",
              paddingTop: 20,
              display: "flex",
              flexDirection: "column",
              gap: 6,
              textAlign: "center",
            }}
          >
            <span
              style={{
                fontSize: 13,
                lineHeight: 1.7,
                color: "var(--blue-ghost)",
              }}
            >
              Already have an account?
            </span>
            <a
              href="/login"
              style={{
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--blue-soft)",
              }}
            >
              Log in
            </a>
          </div>
        </div>
      </main>
    </>
  );
}

// Join Weekly: the public purchase (operator 2026-08-03, change A, CHECKOUT
// FIRST). This reverses the earlier confirm-before-pay flow. "Join Weekly" no
// longer sends a link and waits for an account before checkout; it goes
// straight to Stripe. The account is created by the webhook from the email
// Stripe collects, and the sign-in link is emailed after the payment clears.
//
// The ONLY thing chosen here is the term, because hosted Checkout cannot toggle
// it in session (operator's "option c"). It is deliberately PUBLIC (see
// SITE_PATHS in lib/auth/roles.ts).
import SiteHeader, { BrandMark } from "@/components/site/SiteHeader";
import JoinWeeklyCheckout from "@/components/site/JoinWeeklyCheckout";

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
              Choose your term and continue to secure checkout. You enter your
              details and pay with Stripe on the next screen; there is nothing to
              set up first.
            </p>
          </div>

          <JoinWeeklyCheckout />

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

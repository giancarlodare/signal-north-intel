// Where Stripe returns after a successful checkout-first purchase (operator
// 2026-08-03, change A). The buyer has NO session here: the account is
// provisioned asynchronously by the webhook, and the sign-in link arrives by
// email. So this page cannot show the portal -- it confirms the payment landed
// and tells them to watch their inbox. Public (SITE_PATHS).
import SiteHeader, { BrandMark } from "@/components/site/SiteHeader";
import { firstBriefMonday } from "@/lib/billing/provision";

export const dynamic = "force-dynamic";
export const metadata = { title: "Payment received — Signal North" };

// The Monday the member's first brief lands, computed by the SAME function the
// welcome email uses (firstBriefMonday), so the page and the email can never
// disagree about the date. Formatted here as "10 August" (the email formats the
// same date as "August 10"); the shared thing is the date, not the wording. The
// page is force-dynamic, so this is the request (≈ purchase) time, and the edge
// cases -- a Sunday buy, a Monday buy after the brief has gone -- are handled in
// firstBriefMonday, not by naive day-adding.
export default function JoinThankYouPage() {
  const firstBrief = new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "long",
  }).format(firstBriefMonday(new Date()));
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
                fontSize: 28,
                lineHeight: 1.2,
                letterSpacing: "-0.015em",
                color: "#fff",
              }}
            >
              Payment received
            </h1>
            <p
              style={{
                margin: 0,
                fontSize: 15,
                lineHeight: 1.75,
                color: "var(--blue-soft)",
              }}
            >
              Your membership is on record. We are setting up your account now
              and sending your sign-in link to the address you paid with. It
              usually arrives within a minute; check your inbox to sign in.
            </p>
            <p
              style={{
                margin: 0,
                fontSize: 13,
                lineHeight: 1.7,
                color: "var(--blue-ghost)",
              }}
            >
              The member edition of the intelligence brief begins this coming
              Monday, {firstBrief}. If the link does not arrive, reply to your
              receipt or write to{" "}
              <a
                href="mailto:giancarlo@signalnorthintel.com"
                style={{ fontSize: 13, color: "var(--blue-soft)" }}
              >
                giancarlo@signalnorthintel.com
              </a>{" "}
              and we will sign you in by hand.
            </p>
          </div>
        </div>
      </main>
    </>
  );
}

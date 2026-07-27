// Member entrance (Claude Design handoff: marketing-site/login.html).
//
// AUTH-MODEL DIVERGENCE (flagged, operator decision pending): the handoff
// designs a passwordless magic-link flow; stage 1 built email + password
// (signInWithPassword), and the operator signs in here daily. This page keeps
// the designed shell but wires the REAL password flow (email + password
// fields, same server action as before). Switching to magic-link is a
// separate approved change, not a silent one.
import { signIn } from "./actions";
import SiteHeader, { BrandMark } from "@/components/site/SiteHeader";

export const dynamic = "force-dynamic";
export const metadata = { title: "Log in — Signal North" };

export default function LoginPage({
  searchParams,
}: {
  searchParams: { error?: string };
}) {
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
              Member entrance
            </h1>
            <p
              style={{
                margin: 0,
                fontSize: 15,
                lineHeight: 1.75,
                color: "var(--blue-soft)",
              }}
            >
              Sign in with your work email and password.
            </p>
          </div>
          <form
            action={signIn}
            data-form="login"
            style={{ display: "flex", flexDirection: "column", gap: 14 }}
          >
            {searchParams.error ? (
              <p
                style={{
                  margin: 0,
                  fontSize: 14,
                  lineHeight: 1.6,
                  color: "var(--red-on-dark)",
                  textAlign: "center",
                }}
              >
                {searchParams.error}
              </p>
            ) : null}
            <input
              type="email"
              name="email"
              placeholder="name@organisation.ca"
              autoComplete="username"
              required
            />
            <input
              type="password"
              name="password"
              placeholder="Password"
              autoComplete="current-password"
              required
            />
            <button
              className="btn btn--primary"
              type="submit"
              style={{ width: "100%" }}
            >
              Sign in
            </button>
          </form>
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
              Membership is by request while the founding cohort is open.
            </span>
            <a
              href="/contact"
              style={{
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--blue-soft)",
              }}
            >
              Request access
            </a>
          </div>
        </div>
      </main>
    </>
  );
}

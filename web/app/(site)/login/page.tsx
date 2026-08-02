// Member entrance (Claude Design handoff: marketing-site/login.html).
//
// DUAL-MODE AUTH (operator decision 2026-07-27): the designed magic-link
// flow is the default; password sign-in stays fully working underneath
// (vendor/gov mail filters can eat the link, and the operator signs in
// daily). The sent state never confirms whether an address is a member.
import { sendMagicLink, signIn } from "./actions";
import SiteHeader, { BrandMark } from "@/components/site/SiteHeader";

export const dynamic = "force-dynamic";
export const metadata = { title: "Log in — Signal North" };

export default function LoginPage({
  searchParams,
}: {
  searchParams: { error?: string; sent?: string };
}) {
  const sent = searchParams.sent === "1";
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
              Enter your work email and we will send a sign-in link.
            </p>
          </div>

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

          {sent ? (
            <div
              data-login-sent
              style={{
                border: "1px solid var(--navy-line)",
                background: "var(--navy-panel)",
                padding: "26px 28px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
                textAlign: "center",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 21,
                  color: "#fff",
                }}
              >
                Check your email.
              </span>
              <span
                style={{
                  fontSize: 14,
                  lineHeight: 1.7,
                  color: "var(--blue-soft)",
                }}
              >
                If that address belongs to a member, a sign-in link is on its
                way. It expires shortly, so use it soon.
              </span>
            </div>
          ) : (
            <form
              action={sendMagicLink}
              data-form="login"
              style={{ display: "flex", flexDirection: "column", gap: 14 }}
            >
              <input
                type="email"
                name="email"
                placeholder="name@organisation.ca"
                autoComplete="username"
                required
              />
              <button
                className="btn btn--primary"
                type="submit"
                style={{ width: "100%" }}
              >
                Send sign-in link
              </button>
            </form>
          )}

          <details style={{ textAlign: "center" }} data-testid="password-fallback">
            <summary
              style={{
                cursor: "pointer",
                listStyle: "none",
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--blue-dim)",
              }}
            >
              Use a password instead
            </summary>
            <form
              action={signIn}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 14,
                paddingTop: 14,
              }}
            >
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
          </details>

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
              Not a member yet? Signal North Weekly is open. You can be
              reading this week&apos;s brief today.
            </span>
            <a
              href="/join"
              style={{
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--blue-soft)",
              }}
            >
              Join Weekly
            </a>
          </div>
        </div>
      </main>
    </>
  );
}

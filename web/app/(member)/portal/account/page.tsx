// Account (Claude Design handoff: dashboard/account.html).
// Wired today: work email (session), sign-out (real signOut action), and the
// coverage-request mailto. HONEST VALUES ONLY: name and organisation render
// from user metadata when provisioned, otherwise "Not on file"; membership
// tier is a STAGE-4 GAP (Stripe) and says so; the sign-in row states the
// real method (email + password), not the handoff's passwordless copy, until
// the operator decides the auth model.
import { signOut } from "@/app/auth-actions";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Account — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

export default async function AccountPage() {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const meta = (user?.user_metadata ?? {}) as Record<string, unknown>;
  const name = (meta["full_name"] as string) || "Not on file";
  const org = (meta["organisation"] as string) || (meta["org"] as string) || "Not on file";

  return (
    <main className="fade-rise">
      <div
        className="dash-main dash-main--narrow"
        style={{
          paddingTop: 64,
          display: "flex",
          flexDirection: "column",
          gap: 32,
        }}
      >
        <div
          className="page-head"
          style={{
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "flex-end",
            gap: 24,
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <h1>Account</h1>
            <span style={{ fontSize: 15, color: "var(--muted)" }}>
              Your membership, kept simple.
            </span>
          </div>
          <form action={signOut}>
            <button
              data-signout
              className="follow-btn"
              style={{
                padding: "10px 22px",
                fontWeight: 600,
                letterSpacing: "0.1em",
              }}
            >
              Sign out
            </button>
          </form>
        </div>

        <section
          className="card"
          style={{ padding: "30px 32px" }}
          data-testid="account-sheet"
        >
          <dl className="account-sheet" style={{ margin: 0 }}>
            <dt>Name</dt>
            <dd data-field="name">{name}</dd>
            <dt>Work email</dt>
            <dd data-field="email">{user?.email ?? "Not signed in"}</dd>
            <dt>Organisation</dt>
            <dd data-field="org">{org}</dd>
            <dt>Membership</dt>
            <dd data-placeholder="true">
              <span className="mono-meta" data-field="tier-terms">
                Provisioned manually; billing details arrive with the Stripe
                stage.
              </span>
            </dd>
            <dt>Sign-in</dt>
            <dd>Email and password</dd>
          </dl>
          <p
            style={{
              fontSize: 13,
              lineHeight: 1.7,
              color: "var(--faint)",
              borderTop: "1px solid var(--line-soft)",
              margin: "22px 0 0",
              paddingTop: 16,
            }}
          >
            To change your name, email, or organisation, write to{" "}
            <a
              href="mailto:briefings@signalnorth.ca"
              style={{ fontSize: 13 }}
            >
              briefings@signalnorth.ca
            </a>{" "}
            and we will make the change same-day.
          </p>
        </section>

        <section
          style={{
            background: "var(--cream)",
            border: "1px solid var(--line)",
            borderRadius: "var(--radius)",
            padding: "26px 30px",
            display: "grid",
            gridTemplateColumns: "minmax(260px,1fr) auto",
            gap: 24,
            alignItems: "center",
          }}
          data-testid="coverage-request"
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span
              className="t-label"
              style={{ fontSize: 11, letterSpacing: "0.16em" }}
            >
              Wish we covered something?
            </span>
            <span style={{ fontSize: 15, lineHeight: 1.7 }}>
              Founding members shape what we build next. Tell us the
              organisations or categories you need.
            </span>
          </div>
          <a
            href="mailto:briefings@signalnorth.ca?subject=Coverage request"
            className="follow-btn"
            style={{
              textDecoration: "none",
              padding: "11px 22px",
              fontWeight: 600,
              letterSpacing: "0.1em",
            }}
          >
            Request coverage
          </a>
        </section>
      </div>
    </main>
  );
}

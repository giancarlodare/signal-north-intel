// Account (Claude Design handoff: dashboard/account.html).
// Wired today: work email (session), sign-out (real signOut action), and the
// coverage-request mailto. HONEST VALUES ONLY: name and organisation render
// from user metadata when provisioned, otherwise "Not on file"; membership
// tier is a STAGE-4 GAP (Stripe) and says so; the sign-in row states the
// real method (email + password), not the handoff's passwordless copy, until
// the operator decides the auth model.
import { signOut } from "@/app/auth-actions";
import { createClient } from "@/lib/supabase/server";
import { billingEnabled } from "@/lib/billing/stripe";
import { getMemberSubscription } from "@/lib/billing/stripe";
import { TIER_LABELS } from "@/lib/billing/config";
import { startCheckout } from "./billing-actions";

export const dynamic = "force-dynamic";
export const metadata = {
  title: "Account — Signal North Member",
  robots: { index: false, follow: false, nocache: true },
};

export default async function AccountPage({
  searchParams,
}: {
  searchParams: { checkout?: string };
}) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const billing = billingEnabled();
  const sub = billing && user ? await getMemberSubscription(user.id) : null;
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
            <dd>
              {sub ? (
                <>
                  <span
                    style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: 19,
                      color: "var(--red)",
                    }}
                    data-field="tier"
                  >
                    {TIER_LABELS[sub.tier]}
                  </span>{" "}
                  <span className="mono-meta" data-field="tier-terms">
                    {sub.status}
                    {sub.currentPeriodEnd
                      ? ` · renews ${sub.currentPeriodEnd.slice(0, 10)}`
                      : ""}
                    {sub.testMode ? " · TEST MODE" : ""}
                  </span>
                </>
              ) : (
                <span className="mono-meta" data-field="tier-terms">
                  {billing
                    ? "No subscription on file."
                    : "Provisioned manually; billing arrives when the Stripe stage is configured."}
                </span>
              )}
            </dd>
            <dt>Sign-in</dt>
            <dd>Email link, with a password fallback</dd>
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

        {billing && !sub ? (
          <section
            className="card"
            style={{
              padding: "26px 30px",
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
            data-testid="billing-checkout"
          >
            <span className="t-label">Set up billing (test mode)</span>
            {searchParams.checkout === "cancelled" ? (
              <span style={{ fontSize: 14, color: "var(--faint)" }}>
                Checkout cancelled; nothing was charged.
              </span>
            ) : null}
            {searchParams.checkout === "unavailable" ? (
              <span style={{ fontSize: 14, color: "var(--faint)" }}>
                That tier is not configured yet.
              </span>
            ) : null}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {(["founding", "pro", "weekly"] as const).map((t) => (
                <form action={startCheckout} key={t}>
                  <input type="hidden" name="tier" value={t} />
                  <button
                    className="follow-btn"
                    type="submit"
                    style={{ padding: "10px 18px" }}
                  >
                    {TIER_LABELS[t]}
                  </button>
                </form>
              ))}
            </div>
            <span style={{ fontSize: 12, color: "var(--faint)" }}>
              Test keys only: no real charge is possible while the portal is
              dark.
            </span>
          </section>
        ) : null}
        {searchParams.checkout === "success" ? (
          <section
            style={{
              border: "1px solid var(--line)",
              background: "var(--cream)",
              padding: "18px 24px",
              fontSize: 14,
            }}
            data-testid="billing-success"
          >
            Checkout complete. Your membership updates here as Stripe
            confirms it.
          </section>
        ) : null}

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

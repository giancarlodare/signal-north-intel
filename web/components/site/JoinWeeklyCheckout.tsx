"use client";
// "Join Weekly" -- checkout-first (operator 2026-08-03, change A). The term is
// chosen HERE, on the card, because hosted Checkout cannot toggle it in
// session. Pressing continue opens Stripe Checkout directly: no account, no
// login, no form of our own in front of the card. The account is created by the
// webhook from the email Stripe collects, and the sign-in link is emailed after.
import { useState } from "react";
import { useFormStatus } from "react-dom";
import { startAnonymousCheckout } from "@/app/(site)/join/checkout-actions";

const TERMS = [
  { value: "annual", label: "Annual", price: "$3,900 / year", note: "Two months free" },
  { value: "monthly", label: "Monthly", price: "$390 / month", note: "Cancel anytime" },
] as const;

function ContinueButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      className="btn btn--primary"
      disabled={pending}
      style={{ width: "100%", letterSpacing: "0.1em" }}
    >
      {pending ? "Opening secure checkout..." : "Continue to secure checkout"}
    </button>
  );
}

export default function JoinWeeklyCheckout() {
  const [interval, setInterval] = useState<string>("annual");

  return (
    <form
      action={startAnonymousCheckout}
      data-testid="join-weekly-checkout"
      style={{ display: "flex", flexDirection: "column", gap: 18 }}
    >
      {/* The interval selector: a segmented radio, annual first (the default
          and headline term). The chosen value rides to Stripe in the form. */}
      <div
        role="radiogroup"
        aria-label="Billing term"
        style={{ display: "flex", flexDirection: "column", gap: 10 }}
      >
        {TERMS.map((t) => {
          const active = interval === t.value;
          return (
            <label
              key={t.value}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                padding: "14px 18px",
                cursor: "pointer",
                border: `1px solid ${active ? "var(--red)" : "var(--navy-line)"}`,
                background: active ? "rgba(200,16,46,0.06)" : "var(--navy-panel)",
                transition: "border-color 120ms ease, background 120ms ease",
              }}
            >
              <input
                type="radio"
                name="interval"
                value={t.value}
                checked={active}
                onChange={() => setInterval(t.value)}
                style={{ position: "absolute", opacity: 0, width: 1, height: 1 }}
              />
              <span style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                <span style={{ fontSize: 15, fontWeight: 600, color: "#fff" }}>
                  {t.label}
                </span>
                <span style={{ fontSize: 12.5, color: "var(--blue-ghost)" }}>
                  {t.note}
                </span>
              </span>
              <span
                style={{
                  fontFamily: "var(--font-serif)",
                  fontSize: 18,
                  color: active ? "var(--red)" : "var(--blue-soft)",
                  whiteSpace: "nowrap",
                }}
              >
                {t.price}
              </span>
            </label>
          );
        })}
      </div>

      <ContinueButton />

      <span style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--blue-ghost)", textAlign: "center" }}>
        You pay securely with Stripe. Your account is created automatically and
        we email your sign-in link.
      </span>
    </form>
  );
}

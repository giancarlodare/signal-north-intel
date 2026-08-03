"use client";
// "Join Weekly" -- the real signup (operator 2026-08-02).
//
// One field, because that is genuinely all we need: the address IS the
// account, and everything else (name, organisation) can be filled in later
// from the account page without blocking the purchase.
//
// CONFIRM BEFORE PAY. This form sends a link; it does not sign anyone in and
// it does not open Stripe. The account exists once the link is clicked, and
// only then does the member reach checkout. The product is delivered by
// email, so an unverified address means someone pays for a brief that never
// arrives, which is the failure this ordering prevents.
import { useFormState, useFormStatus } from "react-dom";
import {
  startWeeklySignup,
  type SignupResult,
} from "@/app/(site)/signup-actions";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      className="btn btn--primary"
      disabled={pending}
      style={{ width: "100%", letterSpacing: "0.1em" }}
    >
      {pending ? "Sending..." : "Send my sign-up link"}
    </button>
  );
}

export default function JoinWeeklyForm() {
  const [state, formAction] = useFormState<SignupResult | null, FormData>(
    startWeeklySignup,
    null,
  );

  if (state?.ok) {
    return (
      <div
        data-testid="join-sent"
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
          style={{ fontFamily: "var(--font-serif)", fontSize: 21, color: "#fff" }}
        >
          Check your email.
        </span>
        <span
          style={{ fontSize: 14, lineHeight: 1.7, color: "var(--blue-soft)" }}
        >
          {state.message}
        </span>
      </div>
    );
  }

  return (
    <form
      action={formAction}
      data-testid="join-weekly-form"
      style={{ display: "flex", flexDirection: "column", gap: 14 }}
    >
      {/* Honeypot: hidden from people and screen readers, filled by bots. */}
      <input
        type="text"
        name="website"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="hp-offscreen"
      />
      <label className="sr-only" htmlFor="join-email">
        Work email
      </label>
      <input
        id="join-email"
        type="email"
        name="email"
        placeholder="name@organisation.ca"
        autoComplete="email"
        required
      />
      <SubmitButton />
      {state && !state.ok ? (
        <span
          data-testid="join-error"
          role="alert"
          style={{ fontSize: "var(--fs-small)", color: "var(--red)" }}
        >
          {state.message}
        </span>
      ) : null}
    </form>
  );
}

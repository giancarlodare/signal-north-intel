"use client";
// "Get the free brief" -- email capture, and NOTHING else (operator
// 2026-08-02).
//
// This form deliberately does not create an account, does not sign anyone in,
// and does not lead to checkout. Free having no login is the point: it keeps
// the entitlement layer small until Pro arrives. The paid path is a separate
// action with a separate destination (/join), and the two must not be
// collapsed into one form.
//
// So there is no password field, no "continue" step, and no tier selection
// here. One input, one button, one outcome.
import { useState } from "react";
import { useFormState, useFormStatus } from "react-dom";
import {
  captureFreeSignup,
  type SignupResult,
} from "@/app/(site)/signup-actions";

function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      // Ghost, not primary: Free is the outline column, and Weekly is the only
      // red button on the page (operator 2026-08-03). The revealed submit
      // matches the collapsed reveal button so Free stays outline throughout.
      className="btn btn--ghost"
      disabled={pending}
      style={{ width: "100%" }}
    >
      {pending ? "Adding..." : label}
    </button>
  );
}

export default function FreeBriefForm({
  source,
  label = "Get the free brief",
  compact = false,
  reveal = false,
}: {
  // Which CTA this is, recorded as the evidence half of CASL consent and as
  // the operator's read on which surface actually works.
  source: string;
  label?: string;
  compact?: boolean;
  // reveal: show only a button until clicked, then expand the input. Keeps the
  // pricing tier column the same height as the others so the row stays aligned.
  reveal?: boolean;
}) {
  const [state, formAction] = useFormState<SignupResult | null, FormData>(
    captureFreeSignup,
    null,
  );
  const [open, setOpen] = useState(!reveal);

  // Terminal state: the address is on the list. No further form is shown,
  // because pressing it again does nothing new.
  if (state?.ok) {
    return (
      <p
        data-testid="free-signup-done"
        style={{
          margin: 0,
          fontSize: 14,
          lineHeight: 1.7,
          color: "var(--muted)",
        }}
      >
        {state.message}
      </p>
    );
  }

  // Collapsed: a single button that matches the other tier CTAs; the input is
  // revealed only on click, so the pricing row stays height-aligned.
  if (!open) {
    return (
      <button
        type="button"
        className="btn btn--ghost"
        onClick={() => setOpen(true)}
        style={{ width: "100%" }}
        data-testid="free-brief-reveal"
      >
        {label}
      </button>
    );
  }

  return (
    <form
      action={formAction}
      data-testid="free-brief-form"
      style={{
        display: "flex",
        flexDirection: compact ? "column" : "row",
        gap: 10,
        flexWrap: "wrap",
        alignItems: compact ? "stretch" : "center",
      }}
    >
      <input type="hidden" name="source" value={source} />
      {/* Honeypot. Hidden from people and from screen readers; a bot fills it
          and is silently dropped by the server action. */}
      <input
        type="text"
        name="website"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="hp-offscreen"
      />
      <label className="sr-only" htmlFor={`free-email-${source}`}>
        Work email
      </label>
      <input
        id={`free-email-${source}`}
        className="free-brief-input"
        type="email"
        name="email"
        placeholder="name@organisation.ca"
        autoComplete="email"
        required
        style={{ minWidth: compact ? undefined : 260 }}
      />
      <SubmitButton label={label} />
      {state && !state.ok ? (
        <span
          data-testid="free-signup-error"
          role="alert"
          style={{
            fontSize: "var(--fs-small)",
            color: "var(--red)",
            width: "100%",
          }}
        >
          {state.message}
        </span>
      ) : null}
      <span
        style={{
          fontSize: 12,
          lineHeight: 1.6,
          color: "var(--faint)",
          width: "100%",
        }}
      >
        No account, no card. One brief a week, and every message carries an
        unsubscribe link.
      </span>
    </form>
  );
}

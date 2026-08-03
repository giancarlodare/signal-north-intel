"use client";
// The closed-column capture form (operator 2026-08-01).
//
// Two shapes, one component, because they are one demand instrument:
//   pro         email only. An aggregate signal: does Pro justify its
//               assumed timeline.
//   enterprise  company, needs, seats, timeline, email. Read individually
//               and answered personally, so it asks enough to answer.
//
// It opens a form, never a checkout and never a live chat. Nothing here
// creates a Stripe object.
import { useState } from "react";
import { useFormState, useFormStatus } from "react-dom";
import { submitInquiry, type InquiryResult } from "@/app/(site)/inquiry-actions";
import "./inquiry.css";

const LABEL: Record<string, string> = {
  pro: "Request early access",
  enterprise: "Get a quote",
};

const HEADING: Record<string, string> = {
  pro: "Signal North Pro",
  enterprise: "Signal North Enterprise",
};

const BLURB: Record<string, string> = {
  pro: "Pro is not open yet. Leave your email and we will tell you when it is.",
  enterprise:
    "Tell us what your team needs and we will come back with a quote built around it.",
};

function SubmitButton({ tier }: { tier: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      className="btn btn--primary"
      disabled={pending}
      style={{ padding: "12px 22px", letterSpacing: "0.1em" }}
    >
      {pending ? "Sending..." : LABEL[tier]}
    </button>
  );
}

export default function InquiryDialog({
  tier,
  variant = "ghost",
  defaultEmail,
  triggerClassName,
}: {
  tier: "pro" | "enterprise";
  variant?: "ghost" | "primary";
  // The trigger renders with the HOST surface's button class (marketing .btn
  // by default; the account page passes its own), because the host stylesheet
  // is the only one guaranteed to be loaded outside the panel.
  triggerClassName?: string;
  // Prefilled when a signed-in member opens the form (the account page):
  // their verified address IS the demand signal, and retyping it would just
  // add a reason to abandon. Still editable, never asserted.
  defaultEmail?: string;
}) {
  const [open, setOpen] = useState(false);
  const [state, formAction] = useFormState<InquiryResult | null, FormData>(
    submitInquiry,
    null,
  );
  const isEnterprise = tier === "enterprise";

  return (
    <>
      <button
        type="button"
        className={triggerClassName ?? `btn btn--${variant}`}
        onClick={() => setOpen(true)}
        data-inquiry-open={tier}
      >
        {LABEL[tier]}
      </button>

      {open ? (
        <div
          className="inquiry-scrim"
          role="dialog"
          aria-modal="true"
          aria-label={HEADING[tier]}
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div className="inquiry-panel">
            <div className="inquiry-panel__head">
              <span className="t-label">{HEADING[tier]}</span>
              <button
                type="button"
                className="inquiry-close"
                aria-label="Close"
                onClick={() => setOpen(false)}
              >
                ×
              </button>
            </div>

            {state?.ok ? (
              <p className="inquiry-done" data-testid="inquiry-done">
                {state.message}
              </p>
            ) : (
              <form action={formAction} className="inquiry-form">
                <p className="inquiry-blurb">{BLURB[tier]}</p>
                <input type="hidden" name="tier" value={tier} />

                {isEnterprise ? (
                  <>
                    <label className="inquiry-field">
                      <span>Company</span>
                      <input name="company_name" required maxLength={200} />
                    </label>
                    <label className="inquiry-field">
                      <span>What you need</span>
                      <textarea name="needs" required rows={4} maxLength={2000} />
                    </label>
                    <label className="inquiry-field">
                      <span>Seats</span>
                      <input name="seat_count" type="number" min={1} max={100000} />
                    </label>
                    <label className="inquiry-field">
                      <span>Timeline</span>
                      <input name="timeline" maxLength={120} />
                    </label>
                  </>
                ) : null}

                <label className="inquiry-field">
                  <span>Email</span>
                  <input name="email" type="email" required maxLength={254} defaultValue={defaultEmail} />
                </label>

                {/* Honeypot: hidden from humans and from assistive tech, so
                    anything in it came from a bot. Not display:none, which
                    some bots detect and skip. */}
                <div className="inquiry-hp" aria-hidden="true">
                  <label>
                    Website
                    <input name="website" tabIndex={-1} autoComplete="off" />
                  </label>
                </div>

                {state && !state.ok ? (
                  <p className="inquiry-error" role="alert">
                    {state.message}
                  </p>
                ) : null}

                <SubmitButton tier={tier} />
              </form>
            )}
          </div>
        </div>
      ) : null}
    </>
  );
}

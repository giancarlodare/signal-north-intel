"use client";

import { useFormState, useFormStatus } from "react-dom";
import { sendBriefEmail, type SendState } from "./actions";

// The submit button reads the form's pending state so a click can't fire twice
// and never looks inert while the send is in flight.
function Submit() {
  const { pending } = useFormStatus();
  return (
    <button className="approve" type="submit" disabled={pending} aria-busy={pending}>
      {pending ? "Sending..." : "Send to me"}
    </button>
  );
}

// Send with VISIBLE feedback: pending while in flight, then an explicit success
// or error message. A dead click (missing key, Resend rejection, not published)
// now shows exactly why instead of doing nothing.
export function SendButton({ briefId }: { briefId: string }) {
  const [state, formAction] = useFormState<SendState | null, FormData>(sendBriefEmail, null);
  return (
    <form action={formAction} style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <input type="hidden" name="id" value={briefId} />
      <Submit />
      {state ? (
        <span className={"tag " + (state.ok ? "ok" : "no")}>{state.message}</span>
      ) : null}
    </form>
  );
}

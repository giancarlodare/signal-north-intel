"use client";

import { useFormStatus } from "react-dom";

// Debounced submit button: disabled while its form's server action is pending,
// so a double-click cannot fire the action twice (the direct cause of the
// duplicate-prediction double-submit). Must be rendered INSIDE the <form> whose
// status it reads.
export function SubmitButton({
  children,
  className,
  pendingLabel,
}: {
  children: React.ReactNode;
  className?: string;
  pendingLabel?: string;
}) {
  const { pending } = useFormStatus();
  return (
    <button className={className} type="submit" disabled={pending} aria-busy={pending}>
      {pending ? pendingLabel ?? "Working…" : children}
    </button>
  );
}

// Single source of truth for the fields an approve/reject writes to a signal.
// The single-signal and bulk paths, approve and reject alike, all build their
// update payload here, so they can never drift apart on which columns they set
// or how a note is formatted. reviewed_by defaults to 'human' (a person made
// the call); the triage engine stamps 'triage@v1' server-side and does not use
// this helper.
//
// Kept as plain ESM (.mjs) with no framework imports so it is unit-testable
// under `node --test` without a bundler.

/**
 * @param {"approve"|"reject"} outcome
 * @param {string} [note]  reviewer's free-text reason (reject only)
 * @param {string} [reviewedBy]
 * @returns {{reviewed: true, reviewed_by: string, review_note: string}}
 */
export function reviewNotePayload(outcome, note = "", reviewedBy = "human") {
  const base = { reviewed: true, reviewed_by: reviewedBy };
  if (outcome === "approve") {
    return { ...base, review_note: "approved" };
  }
  const trimmed = (note ?? "").trim();
  return { ...base, review_note: trimmed ? `rejected: ${trimmed}` : "rejected" };
}

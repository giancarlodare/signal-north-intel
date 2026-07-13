import { test } from "node:test";
import assert from "node:assert/strict";
import { reviewNotePayload } from "./reviewNote.mjs";

// The reported bug: rejecting with a note did not save the note. These lock in
// that a reject with a note persists it to review_note, and that approve wires
// the same review fields.

test("reject with a note stores the note in review_note", () => {
  const p = reviewNotePayload("reject", "  off topic, not defence  ");
  assert.equal(p.review_note, "rejected: off topic, not defence"); // trimmed, prefixed
  assert.equal(p.reviewed, true);
  assert.equal(p.reviewed_by, "human");
});

test("reject without a note stores bare 'rejected'", () => {
  assert.equal(reviewNotePayload("reject", "").review_note, "rejected");
  assert.equal(reviewNotePayload("reject").review_note, "rejected");
  assert.equal(reviewNotePayload("reject", "   ").review_note, "rejected"); // whitespace-only
});

test("approve sets approved and the identical review fields", () => {
  const p = reviewNotePayload("approve");
  assert.deepEqual(p, {
    reviewed: true,
    reviewed_by: "human",
    review_note: "approved",
  });
});

test("approve and reject set the same field shape (reviewed, reviewed_by, review_note)", () => {
  const a = reviewNotePayload("approve");
  const r = reviewNotePayload("reject", "x");
  assert.deepEqual(Object.keys(a).sort(), Object.keys(r).sort());
});

test("reviewed_by can be overridden (e.g. a machine stamp)", () => {
  assert.equal(reviewNotePayload("approve", "", "triage@v1").reviewed_by, "triage@v1");
});

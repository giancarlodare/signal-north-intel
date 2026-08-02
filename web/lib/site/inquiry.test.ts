// Validation rules for the closed-column demand instrument. Pure, so the
// rules that decide what reaches the database are pinned without a database.
import { test } from "node:test";
import assert from "node:assert/strict";
import { validateInquiry } from "./inquiry.ts";

const pro = { tier: "pro", email: "buyer@example.com" };
const ent = {
  tier: "enterprise",
  email: "chief@region.ca",
  companyName: "Region of Example",
  needs: "Coverage for our three neighbouring services.",
};

test("pro needs only an email", () => {
  const v = validateInquiry(pro);
  assert.equal(v.ok, true);
  if (v.ok) {
    assert.equal(v.row.tier, "pro");
    assert.equal(v.row.company_name, null);
    assert.equal(v.row.seat_count, null);
  }
});

test("enterprise requires company and needs, since it is answered personally", () => {
  assert.equal(validateInquiry({ ...ent, companyName: "" }).ok, false);
  assert.equal(validateInquiry({ ...ent, needs: "" }).ok, false);
  assert.equal(validateInquiry(ent).ok, true);
});

test("the honeypot rejects, and does not say so", () => {
  const v = validateInquiry({ ...pro, website: "http://spam.example" });
  assert.equal(v.ok, false);
  if (!v.ok) assert.equal(v.error, "rejected");
});

test("an unknown tier never reaches the insert", () => {
  assert.equal(validateInquiry({ ...pro, tier: "weekly" }).ok, false);
  assert.equal(validateInquiry({ ...pro, tier: "" }).ok, false);
});

test("email must look like one", () => {
  assert.equal(validateInquiry({ ...pro, email: "" }).ok, false);
  assert.equal(validateInquiry({ ...pro, email: "nope" }).ok, false);
  assert.equal(validateInquiry({ ...pro, email: "a@b" }).ok, false);
  assert.equal(validateInquiry({ ...pro, email: "a@b.ca" }).ok, true);
});

test("seat count must be a whole positive number when given", () => {
  assert.equal(validateInquiry({ ...ent, seatCount: "0" }).ok, false);
  assert.equal(validateInquiry({ ...ent, seatCount: "2.5" }).ok, false);
  assert.equal(validateInquiry({ ...ent, seatCount: "many" }).ok, false);
  const v = validateInquiry({ ...ent, seatCount: "12" });
  assert.equal(v.ok, true);
  if (v.ok) assert.equal(v.row.seat_count, 12);
});

test("over-long fields are rejected, never silently truncated", () => {
  assert.equal(validateInquiry({ ...ent, needs: "x".repeat(2001) }).ok, false);
  assert.equal(validateInquiry({ ...ent, companyName: "x".repeat(201) }).ok, false);
});

test("whitespace-only optional fields land as null, not empty strings", () => {
  const v = validateInquiry({ ...ent, timeline: "   " });
  assert.equal(v.ok, true);
  if (v.ok) assert.equal(v.row.timeline, null);
});

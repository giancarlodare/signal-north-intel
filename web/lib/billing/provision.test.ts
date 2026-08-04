// The pure decisions in the checkout-first provision path (change A): picking
// the anchor email, and the Monday the welcome promises. Pinned by test because
// the anchor is what a whole account is created from, and a wrong "first brief"
// date is a promise we would break in the member's first email.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  pickAnchorEmail,
  firstBriefMonday,
  firstBriefDateLabel,
} from "./provision.ts";

test("pickAnchorEmail takes the first deliverable address, lowercased", () => {
  assert.equal(
    pickAnchorEmail(["Buyer@Agency.CA", "other@x.com"]),
    "buyer@agency.ca",
  );
  // skips empties/nulls to the first real one
  assert.equal(pickAnchorEmail([null, "", "  ", "a@b.co"]), "a@b.co");
});

test("pickAnchorEmail rejects undeliverable shapes and returns null", () => {
  assert.equal(pickAnchorEmail([]), null);
  assert.equal(pickAnchorEmail([null, undefined, ""]), null);
  assert.equal(pickAnchorEmail(["not-an-email"]), null);
  assert.equal(pickAnchorEmail(["no@domain"]), null); // no dot in domain
  assert.equal(pickAnchorEmail(["a".repeat(250) + "@b.co"]), null); // > 254
});

test("firstBriefMonday returns the NEXT Monday strictly after the purchase", () => {
  // Tue 2026-08-04 -> Mon 2026-08-10
  assert.equal(
    firstBriefMonday(new Date("2026-08-04T15:00:00Z")).toISOString().slice(0, 10),
    "2026-08-10",
  );
  // Sun 2026-08-09 -> Mon 2026-08-10 (the very next day)
  assert.equal(
    firstBriefMonday(new Date("2026-08-09T23:00:00Z")).toISOString().slice(0, 10),
    "2026-08-10",
  );
});

test("buying ON a Monday promises the FOLLOWING Monday, not that morning's brief", () => {
  // Mon 2026-08-10 -> Mon 2026-08-17 (+7): that day's brief has likely gone out.
  assert.equal(
    firstBriefMonday(new Date("2026-08-10T09:00:00Z")).toISOString().slice(0, 10),
    "2026-08-17",
  );
});

test("firstBriefDateLabel is the human month/day of that Monday", () => {
  assert.equal(firstBriefDateLabel(new Date("2026-08-04T15:00:00Z")), "August 10");
  assert.equal(firstBriefDateLabel(new Date("2026-08-10T09:00:00Z")), "August 17");
});

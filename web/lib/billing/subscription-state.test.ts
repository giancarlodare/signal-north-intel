// The rules standing between a member and paid content. Pure, so they are
// pinned without Stripe or a database.
import { test } from "node:test";
import assert from "node:assert/strict";
import { grantsAccess, grantsPortal, shouldApply } from "./subscription-state";

const row = (over: Record<string, unknown> = {}) =>
  ({
    member_id: "m1",
    stripe_customer_id: "cus_1",
    stripe_subscription_id: "sub_1",
    tier: "weekly",
    interval: "annual",
    status: "active",
    current_period_end: null,
    event_created_at: "2026-08-01T12:00:00.000Z",
    ...over,
  }) as never;

test("active and trialing grant access", () => {
  assert.equal(grantsAccess(row()), true);
  assert.equal(grantsAccess(row({ status: "trialing" })), true);
});

test("no row means no access", () => {
  assert.equal(grantsAccess(null), false);
  assert.equal(grantsPortal(null), false);
});

test("past_due does NOT grant access; recovery is a dashboard task", () => {
  assert.equal(grantsAccess(row({ status: "past_due" })), false);
});

test("unknown and future Stripe statuses default to no access", () => {
  assert.equal(grantsAccess(row({ status: "canceled" })), false);
  assert.equal(grantsAccess(row({ status: "incomplete_expired" })), false);
  assert.equal(grantsAccess(row({ status: "some_future_status" })), false);
});

test("every portal tier grants the portal when paid up", () => {
  for (const tier of ["weekly", "pro", "founding"]) {
    assert.equal(grantsPortal(row({ tier })), true);
  }
});

test("a cancelled portal tier does not grant the portal", () => {
  assert.equal(grantsPortal(row({ tier: "pro", status: "canceled" })), false);
});

test("a stale out-of-order event is not applied", () => {
  const existing = { event_created_at: "2026-08-01T12:00:00.000Z" };
  assert.equal(shouldApply(existing, "2026-08-01T11:59:59.000Z"), false);
  assert.equal(shouldApply(existing, "2026-08-01T12:00:01.000Z"), true);
  // Equal timestamps apply: Stripe retries deliver the same event again, and
  // re-applying it is idempotent.
  assert.equal(shouldApply(existing, "2026-08-01T12:00:00.000Z"), true);
});

test("a first event always applies", () => {
  assert.equal(shouldApply(null, "2020-01-01T00:00:00.000Z"), true);
});

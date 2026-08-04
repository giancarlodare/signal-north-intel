// The reconciliation alarm renderer. This is the one out-of-window interrupt,
// so its subject must be unmistakable and its body must carry the exact manual
// command the operator runs to fix it.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  provisionAlarmSubject,
  manualProvisionCommand,
  renderProvisionAlarm,
} from "./alarm-email.ts";
import type { ProvisionFailureReason } from "./provision.ts";

const base = {
  email: "buyer@agency.ca" as string | null,
  subscriptionId: "sub_123",
  customerId: "cus_456",
  tier: "weekly" as string | null,
  interval: "annual" as string | null,
  reason: "provision-failed" as ProvisionFailureReason,
};

test("subject is unmistakable and greppable, with the address inline", () => {
  const s = provisionAlarmSubject(base);
  assert.ok(s.includes("[SIGNAL NORTH — ACTION]"));
  assert.ok(s.includes("buyer@agency.ca"));
});

test("subject still names the problem when there is no email", () => {
  const s = provisionAlarmSubject({ ...base, email: null });
  assert.ok(s.includes("[SIGNAL NORTH — ACTION]"));
  assert.ok(/no email/i.test(s));
});

test("the manual command targets the subscription id and is in the body", () => {
  assert.equal(manualProvisionCommand("sub_xyz"), "node web/scripts/provision-member.mjs sub_xyz");
  const out = renderProvisionAlarm(base);
  assert.ok(out.text.includes("node web/scripts/provision-member.mjs sub_123"));
  assert.ok(out.html.includes("node web/scripts/provision-member.mjs sub_123"));
});

test("every failure reason renders a distinct explanation", () => {
  const reasons: ProvisionFailureReason[] = [
    "no-email", "unmapped-price", "provision-failed", "welcome-send-failed",
  ];
  const lines = new Set<string>();
  for (const reason of reasons) {
    const out = renderProvisionAlarm({ ...base, reason });
    assert.ok(out.text.includes(reason), `text names ${reason}`);
    lines.add(out.text);
  }
  assert.equal(lines.size, reasons.length, "reasons should not share body copy");
});

test("html escapes the fields it interpolates", () => {
  const out = renderProvisionAlarm({ ...base, email: "a<b>@x.ca" });
  assert.ok(out.html.includes("a&lt;b&gt;@x.ca"));
  assert.ok(!out.html.includes("a<b>@x.ca"));
});

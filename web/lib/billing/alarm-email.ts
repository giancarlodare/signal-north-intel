// The reconciliation alarm: the ONE out-of-window interrupt the operator asked
// for (operator 2026-08-03, change A). It fires when a checkout was PAID but
// the webhook could not turn it into a working account, which is the single
// failure that must never wait for the next digest -- someone paid and cannot
// read what they paid for.
//
// This module only RENDERS the alarm (pure, so the subject line and the manual
// command are pinned by test). The webhook sends it via lib/email/send.ts and
// records the failure in provisioning_failures so it fires once, not once per
// Stripe retry.
//
// The subject is deliberately unmistakable and greppable: the operator filters
// on it, and it is the only thing allowed to break the two-digests-a-day rule.
import type { ProvisionFailureReason } from "./provision";

export interface ProvisionAlarmInput {
  email: string | null;
  subscriptionId: string;
  customerId: string | null;
  tier: string | null;
  interval: string | null;
  reason: ProvisionFailureReason;
}

const REASON_LINE: Record<ProvisionFailureReason, string> = {
  "no-email":
    "The completed checkout carried no email address, so there was nothing to provision from.",
  "unmapped-price":
    "The subscription's price maps to no configured tier, so it was not provisioned to any plan.",
  "provision-failed":
    "The Supabase admin call to create or find the account failed.",
  "welcome-send-failed":
    "The account WAS provisioned and is entitled, but the welcome email could not be sent, so the member has not received their sign-in link.",
};

// The subject the operator filters on. ACTION in caps, the address inline, so
// it is unmistakable in a list and greppable in a mailbox.
export function provisionAlarmSubject(input: ProvisionAlarmInput): string {
  return `[SIGNAL NORTH — ACTION] Paid, not provisioned: ${input.email ?? "(no email on checkout)"}`;
}

// The manual provision command the operator runs to resolve the row. Takes the
// subscription id, which is always present even when the email is not.
export function manualProvisionCommand(subscriptionId: string): string {
  return `node web/scripts/provision-member.mjs ${subscriptionId}`;
}

export interface RenderedEmail {
  subject: string;
  html: string;
  text: string;
}

export function renderProvisionAlarm(input: ProvisionAlarmInput): RenderedEmail {
  const subject = provisionAlarmSubject(input);
  const cmd = manualProvisionCommand(input.subscriptionId);
  const reasonLine = REASON_LINE[input.reason];
  const rows: Array<[string, string]> = [
    ["Email", input.email ?? "(none on checkout)"],
    ["Reason", `${input.reason} — ${reasonLine}`],
    ["Subscription", input.subscriptionId],
    ["Customer", input.customerId ?? "(none)"],
    ["Tier", input.tier ?? "(unmapped)"],
    ["Interval", input.interval ?? "(unknown)"],
  ];

  const text =
    `SIGNAL NORTH — RECONCILIATION ALARM\n` +
    `A checkout was paid but could not be provisioned into a working account.\n\n` +
    rows.map(([k, v]) => `${k}: ${v}`).join("\n") +
    `\n\nStripe is retrying the webhook; a retry may resolve this on its own.\n` +
    `To provision by hand now, run:\n\n    ${cmd}\n\n` +
    `That command creates or finds the account, grants the subscription, and\n` +
    `sends the welcome. It is idempotent: safe to run even if Stripe has since\n` +
    `succeeded.\n`;

  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const html =
    `<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:620px;">` +
    `<p style="font:bold 12px/1.4 monospace;letter-spacing:0.12em;color:#C8102E;text-transform:uppercase;">Signal North — reconciliation alarm</p>` +
    `<p style="font-size:15px;line-height:1.6;color:#232B37;">A checkout was <strong>paid</strong> but could not be provisioned into a working account.</p>` +
    `<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:14px;color:#232B37;margin:16px 0;">` +
    rows
      .map(
        ([k, v]) =>
          `<tr><td style="padding:4px 16px 4px 0;color:#6B7280;vertical-align:top;">${esc(k)}</td>` +
          `<td style="padding:4px 0;font-family:monospace;">${esc(v)}</td></tr>`,
      )
      .join("") +
    `</table>` +
    `<p style="font-size:14px;line-height:1.6;color:#232B37;">Stripe is retrying the webhook; a retry may resolve this on its own. To provision by hand now, run:</p>` +
    `<pre style="background:#0D1520;color:#F5F3EF;padding:12px 16px;border-radius:4px;font-size:13px;overflow-x:auto;">${esc(cmd)}</pre>` +
    `<p style="font-size:13px;line-height:1.6;color:#6B7280;">That command creates or finds the account, grants the subscription, and sends the welcome. It is idempotent: safe to run even if Stripe has since succeeded.</p>` +
    `</div>`;

  return { subject, html, text };
}

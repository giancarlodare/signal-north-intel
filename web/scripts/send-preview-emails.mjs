#!/usr/bin/env node
// Dispatch-only preview send (operator 2026-08-04). Sends the two TRANSACTIONAL
// emails we author -- 02 free-welcome and 03 member-welcome -- to one address so
// the operator can see them in a real client, which differs enough from a
// browser preview to be worth doing before a customer ever receives them.
//
// KEY HYGIENE (operator's ruling). This runs against a SCOPED, DISPOSABLE Resend
// key (named ci-preview, sending-only), never the production key. A leaked
// sending key on our own domain is a phishing/reputation risk, so it gets a
// short-lived key that the operator revokes once 02 and 03 have been seen.
//
// The four Supabase templates (01, 04, 05, 06) are NOT sent here: their faithful
// real-client render is Supabase's own send, done in the session where the
// templates are installed. Faking them from a script would show the wrong
// sender and unsubstituted variables.
//
// Placeholders are filled with SAMPLE values (clearly not real links) purely so
// the layout renders; this is a look test, not a live message.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const EMAILS = join(HERE, "..", "emails");

const SAMPLE = {
  // 03 member-welcome
  signin_url: "https://signalnorthintel.com/auth/confirm?token_hash=SAMPLE&type=magiclink&next=%2Fportal%2Fbrief",
  first_brief_date: "August 11",
  // 02 free-welcome
  welcome_cta_url: "https://signalnorthintel.com/pricing",
  welcome_cta_label: "See what a membership adds",
  unsubscribe_url: "https://signalnorthintel.com/unsubscribe?token=SAMPLE",
  preferences_url: "https://signalnorthintel.com/preferences?token=SAMPLE",
  // A plain address line, no brackets: this is how the populated variable reads.
  business_address: "Signal North, Richmond Hill, Ontario, Canada",
};

const EMAILS_TO_SEND = [
  { base: "02-free-welcome", subject: "Your first brief lands Monday" },
  { base: "03-member-welcome", subject: "Your Signal North membership is active" },
];

function fill(s) {
  for (const [k, v] of Object.entries(SAMPLE)) s = s.split(`{{${k}}}`).join(v);
  return s;
}

async function main() {
  const key = process.env.RESEND_API_KEY;
  if (!key) { console.error("FATAL: RESEND_API_KEY is not set (ci-preview key)."); process.exit(2); }
  const to = process.env.EMAIL_PREVIEW_TO || process.argv[2];
  if (!to) { console.error("FATAL: recipient not set (EMAIL_PREVIEW_TO or argv[1])."); process.exit(2); }
  const from = process.env.MEMBER_EMAIL_SENDER || "Signal North <signal@signalnorthintel.com>";

  let failures = 0;
  for (const e of EMAILS_TO_SEND) {
    const html = fill(readFileSync(join(EMAILS, `${e.base}.html`), "utf8"));
    const text = fill(readFileSync(join(EMAILS, `${e.base}.txt`), "utf8"));
    const resp = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "content-type": "application/json" },
      body: JSON.stringify({ from, to: [to], subject: `[preview] ${e.subject}`, html, text }),
    });
    if (resp.ok) {
      console.log(`sent ${e.base} -> ${to}`);
    } else {
      failures++;
      console.error(`FAILED ${e.base}: HTTP ${resp.status} ${(await resp.text()).slice(0, 200)}`);
    }
  }
  if (failures) process.exit(1);
  console.log("Done. Both preview emails sent.");
}

main().catch((e) => { console.error("FATAL:", e); process.exit(1); });

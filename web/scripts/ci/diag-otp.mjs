#!/usr/bin/env node
// Empirical probe of Supabase's magic-link throttling (operator 2026-08-04:
// "check whether the rate limit is actually 30, or whether something else is
// throttling"). The dashboard number (30/hour) is the AGGREGATE email budget;
// GoTrue also enforces a separate PER-ADDRESS minimum interval between emails
// (smtp_max_frequency, default 60s) and per-IP endpoint limits. Which one is
// biting is visible only in the error body, so this sends two back-to-back
// OTP requests to one address and prints both responses VERBATIM.
//
// COST: up to 2 emails from the hourly budget, both to the address given (a
// real inbox the operator controls; the emails are ignorable). No user is
// created (create_user: false). Public logs: prints status + error bodies
// only; a success body from /otp is {} and carries no token.
//
// Usage: diag-otp.mjs <email-that-exists>
const BASE = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/+$/, "");
const KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
const email = (process.argv[2] || "").trim().toLowerCase();
if (!BASE || !KEY || !email.includes("@")) {
  console.error("usage: diag-otp.mjs <email> (env: SUPABASE url + service key)");
  process.exit(2);
}

async function requestOtp(label) {
  const resp = await fetch(`${BASE}/auth/v1/otp`, {
    method: "POST",
    headers: {
      apikey: KEY,
      Authorization: `Bearer ${KEY}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ email, create_user: false }),
  });
  const body = await resp.text().catch(() => "");
  console.log(`${label}: HTTP ${resp.status}`);
  console.log(`  body: ${body.slice(0, 400)}`);
  const retryAfter = resp.headers.get("retry-after");
  const rl = [...resp.headers.entries()].filter(([k]) => /rate|retry/i.test(k));
  if (rl.length) console.log(`  rate headers: ${JSON.stringify(Object.fromEntries(rl))}`);
  return resp.status;
}

console.log(`Probing OTP throttles for ${email} against ${BASE.replace(/^https?:\/\//, "").split(".")[0]}...`);
const first = await requestOtp("send #1");
await new Promise((r) => setTimeout(r, 2000));
const second = await requestOtp("send #2 (2s later, same address)");

console.log("\nREAD:");
if (first === 200 && second === 429) {
  console.log("  #1 sent, #2 throttled: the error body above names the ACTIVE limiter.");
  console.log("  'only request this after N seconds' => the per-address minimum");
  console.log("  interval (separate from the 30/hour aggregate), which is what");
  console.log("  repeated same-address testing trips regardless of the hourly budget.");
} else if (first === 429) {
  console.log("  Throttled on the FIRST send: the hourly aggregate budget (or an");
  console.log("  IP limit) is currently exhausted; the body names which.");
} else if (first === 200 && second === 200) {
  console.log("  Both sends accepted: no per-address interval is configured (or it");
  console.log("  is < 2s), and the hourly budget has room. If testing still sees");
  console.log("  silence, the throttle is not at the send API -- look at delivery.");
} else {
  console.log("  Unexpected combination; the verbatim bodies above are the evidence.");
}

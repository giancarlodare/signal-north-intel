#!/usr/bin/env node
// Account audit + direct provision for the operator's test accounts
// (operator 2026-08-04: "confirm from auth.users which of my test accounts
// still exist, and if none do, provision me one so I can sign in").
//
// Two modes:
//   list <filter>    List auth.users whose email contains <filter>, with
//                    created/confirmed/last-sign-in and whether a
//                    member_subscriptions row exists. Read-only.
//   create <email>   admin.createUser with email_confirm, so /login's normal
//                    magic-link send works for it. Idempotent: an existing
//                    account is reported, not duplicated.
//
// SECURITY: this repo is PUBLIC, so Actions logs are public. This script must
// NEVER print an action link, token_hash, or anything session-granting. The
// operator signs in via /login, which delivers the link to their inbox.
import { createClient } from "@supabase/supabase-js";

const db = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY,
  { auth: { persistSession: false } },
);

async function allUsers() {
  const out = [];
  let page = 1;
  for (;;) {
    const { data, error } = await db.auth.admin.listUsers({ page, perPage: 200 });
    if (error) throw new Error(error.message);
    const users = data?.users ?? [];
    out.push(...users);
    if (users.length < 200 || page >= 25) return out;
    page++;
  }
}

const mode = process.argv[2];
const arg = (process.argv[3] || "").trim().toLowerCase();

if (mode === "list") {
  if (!arg) { console.error("usage: account-tools.mjs list <email-substring>"); process.exit(2); }
  const users = await allUsers();
  const hits = users.filter((u) => (u.email || "").toLowerCase().includes(arg));
  console.log(`auth.users total: ${users.length}; matching "${arg}": ${hits.length}\n`);
  for (const u of hits) {
    const { data: sub } = await db
      .from("member_subscriptions")
      .select("tier,interval,status")
      .eq("member_id", u.id)
      .maybeSingle();
    console.log(`  ${u.email}`);
    console.log(`    created ${u.created_at}  confirmed ${u.email_confirmed_at ?? "never"}  last_sign_in ${u.last_sign_in_at ?? "never"}`);
    console.log(`    subscription: ${sub ? `${sub.tier}/${sub.interval}/${sub.status}` : "none"}`);
  }
  if (!hits.length) console.log("  (none — no matching accounts exist)");
} else if (mode === "create") {
  if (!arg.includes("@")) { console.error("usage: account-tools.mjs create <email>"); process.exit(2); }
  const { data, error } = await db.auth.admin.createUser({ email: arg, email_confirm: true });
  if (error) {
    if (/already/i.test(error.message)) {
      console.log(`account already exists for ${arg} — nothing to do; /login will send.`);
    } else {
      console.error("createUser failed:", error.message);
      process.exit(1);
    }
  } else {
    console.log(`created account for ${arg} (id ${data.user.id}, email confirmed).`);
    console.log("Sign in via /login: the magic link goes to the inbox. No token is printed here.");
  }
} else {
  console.error("usage: account-tools.mjs <list|create> <arg>");
  process.exit(2);
}

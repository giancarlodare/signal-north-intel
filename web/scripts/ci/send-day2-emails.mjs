#!/usr/bin/env node
// Day-2 member email sender. Run daily at 9am ET via .github/workflows/day2-email.yml.
// Queries Supabase for paid members created 24-48h ago without day2_sent flag,
// sends the 07-member-day2 email via Resend, and marks day2_sent=true.
// Loud failure: any send error sets exitCode=1 so the workflow run goes red.

import { createClient } from "@supabase/supabase-js";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_TEMPLATE = readFileSync(
  join(__dirname, "../../emails/07-member-day2.html"),
  "utf8",
);
const TEXT_TEMPLATE = readFileSync(
  join(__dirname, "../../emails/07-member-day2.txt"),
  "utf8",
);

const SUPABASE_URL = process.env.SUPABASE_URL ?? "";
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
const RESEND_KEY = process.env.RESEND_API_KEY ?? "";
const SITE_URL = process.env.SITE_URL ?? "https://signalnorthintel.com";
const FROM = "Signal North <signal@signalnorthintel.com>";
const REPLY_TO = "giancarlo@signalnorthintel.com";

if (!SUPABASE_URL || !SERVICE_KEY || !RESEND_KEY) {
  console.error(
    "FATAL: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and RESEND_API_KEY are required.",
  );
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { autoRefreshToken: false, persistSession: false },
});

function nextMondayEastern() {
  const now = new Date();
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Toronto",
    weekday: "long",
    hour: "numeric",
    hour12: false,
  }).formatToParts(now);
  const weekday = parts.find((p) => p.type === "weekday")?.value ?? "Tuesday";
  const hour = parseInt(
    parts.find((p) => p.type === "hour")?.value ?? "12",
    10,
  );
  const dayNum = {
    Sunday: 0, Monday: 1, Tuesday: 2, Wednesday: 3,
    Thursday: 4, Friday: 5, Saturday: 6,
  };
  const d = dayNum[weekday] ?? 0;
  let daysToAdd = (8 - d) % 7 || 7;
  if (d === 1 && hour < 6) daysToAdd = 0;
  const nextMon = new Date(now.getTime() + daysToAdd * 86400e3);
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(nextMon);
}

async function listAllUsers() {
  const users = [];
  let page = 1;
  while (true) {
    const { data, error } = await supabase.auth.admin.listUsers({
      page,
      perPage: 1000,
    });
    if (error) {
      console.error(`FATAL: supabase.auth.admin.listUsers failed: ${error.message}`);
      process.exit(1);
    }
    users.push(...(data.users ?? []));
    if (data.nextPage == null) break;
    page = data.nextPage;
  }
  return users;
}

async function main() {
  const nextBriefDate = nextMondayEastern();
  const portalUrl = `${SITE_URL}/portal`;
  const watchingUrl = `${SITE_URL}/portal/watching`;

  console.log(`Next brief date: ${nextBriefDate}`);

  // Paid member IDs from member_subscriptions
  const { data: subs, error: subErr } = await supabase
    .from("member_subscriptions")
    .select("member_id")
    .eq("status", "active");
  if (subErr) {
    console.error(`FATAL: member_subscriptions query failed: ${subErr.message}`);
    process.exit(1);
  }
  const paidIds = new Set((subs ?? []).map((s) => s.member_id));
  console.log(`Active paid members: ${paidIds.size}`);

  const allUsers = await listAllUsers();
  console.log(`Total auth users: ${allUsers.length}`);

  const now = Date.now();
  const h48ago = now - 48 * 3600e3;
  const h24ago = now - 24 * 3600e3;

  const eligible = allUsers.filter((u) => {
    const created = new Date(u.created_at).getTime();
    return (
      created >= h48ago &&
      created <= h24ago &&
      paidIds.has(u.id) &&
      !u.user_metadata?.day2_sent
    );
  });
  console.log(`Eligible for Day-2 email: ${eligible.length}`);

  let sent = 0;
  let failed = 0;

  for (const user of eligible) {
    if (!user.email) {
      console.warn(`Skipping ${user.id}: no email address.`);
      continue;
    }
    const html = HTML_TEMPLATE
      .replace(/\{\{next_brief_date\}\}/g, nextBriefDate)
      .replace(/\{\{portal_url\}\}/g, portalUrl)
      .replace(/\{\{watching_url\}\}/g, watchingUrl);
    const text = TEXT_TEMPLATE
      .replace(/\{\{next_brief_date\}\}/g, nextBriefDate)
      .replace(/\{\{portal_url\}\}/g, portalUrl)
      .replace(/\{\{watching_url\}\}/g, watchingUrl);

    try {
      const res = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${RESEND_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          from: FROM,
          reply_to: REPLY_TO,
          to: [user.email],
          subject: `Your first brief arrives ${nextBriefDate}`,
          html,
          text,
        }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`Resend HTTP ${res.status}: ${body.slice(0, 200)}`);
      }

      const { error: updateErr } = await supabase.auth.admin.updateUserById(
        user.id,
        { user_metadata: { ...user.user_metadata, day2_sent: true } },
      );
      if (updateErr) {
        console.error(
          `Sent to ${user.email} but failed to mark day2_sent: ${updateErr.message}`,
        );
        process.exitCode = 1;
      } else {
        console.log(`OK ${user.email}`);
        sent++;
      }
    } catch (e) {
      console.error(`FAILED ${user.email}: ${e.message}`);
      failed++;
      process.exitCode = 1;
    }
  }

  console.log(
    `\nDay-2 run complete. Sent: ${sent}, failed: ${failed}, skipped: ${eligible.length - sent - failed}.`,
  );
}

main().catch((e) => {
  console.error(`Unhandled error: ${e.message}`);
  process.exit(1);
});

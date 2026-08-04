// The member-welcome renderer (template 03). Two things must hold:
//   1. The embedded template bytes are IDENTICAL to the reviewed files. The
//      operator approves web/emails/03-member-welcome.{html,txt}; this test is
//      what guarantees the thing SENT is the thing approved, so a divergence
//      fails CI instead of reaching a member's inbox.
//   2. Both {{signin_url}} occurrences and {{first_brief_date}} are filled, and
//      no placeholder survives into a real email.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  MEMBER_WELCOME_HTML_TEMPLATE,
  MEMBER_WELCOME_TEXT_TEMPLATE,
  renderMemberWelcome,
} from "./welcome-email.ts";

const htmlFile = readFileSync(
  new URL("../../emails/03-member-welcome.html", import.meta.url),
  "utf8",
);
const txtFile = readFileSync(
  new URL("../../emails/03-member-welcome.txt", import.meta.url),
  "utf8",
);

test("embedded template is byte-identical to the reviewed source files", () => {
  assert.equal(MEMBER_WELCOME_HTML_TEMPLATE, htmlFile);
  assert.equal(MEMBER_WELCOME_TEXT_TEMPLATE, txtFile);
});

test("render fills every placeholder, both signin_url occurrences included", () => {
  const link = "https://signalnorthintel.com/auth/confirm?token_hash=abc&type=magiclink&next=%2Fportal%2Fbrief";
  const out = renderMemberWelcome({ signInLink: link, firstBriefDate: "August 10" });

  for (const body of [out.html, out.text]) {
    assert.ok(!body.includes("{{signin_url}}"), "signin_url placeholder left behind");
    assert.ok(!body.includes("{{first_brief_date}}"), "first_brief_date placeholder left behind");
    assert.ok(body.includes("August 10"), "first brief date not substituted");
  }
  // The HTML carries the link twice (button + paste-fallback); both must be real.
  const occurrences = out.html.split(link).length - 1;
  assert.equal(occurrences, 2, "expected the sign-in link in both HTML slots");
});

test("welcome is transactional: it carries NO unsubscribe link", () => {
  const out = renderMemberWelcome({ signInLink: "https://x.test/s", firstBriefDate: "August 10" });
  assert.ok(/no unsubscribe link/i.test(out.text));
  assert.ok(!/unsubscribe<\/a>/i.test(out.html));
});

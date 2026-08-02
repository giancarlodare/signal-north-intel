// The two public signup paths. Pure rules, pinned without a database, a mail
// server, or Supabase.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  validateFreeSignup,
  validateWeeklySignup,
  safeNext,
  SIGNUP_DESTINATION,
} from "./signup.ts";
import { validateInquiry } from "./inquiry.ts";

// --- free capture -----------------------------------------------------------

test("free capture takes an email and a source", () => {
  const v = validateFreeSignup({ email: "chief@region.ca", source: "home-hero" });
  assert.equal(v.ok, true);
  if (v.ok) {
    assert.equal(v.row.email, "chief@region.ca");
    assert.equal(v.row.consent_source, "home-hero");
  }
});

test("free capture lowercases and trims, so one address is one row", () => {
  const v = validateFreeSignup({ email: "  Chief@Region.CA " });
  assert.equal(v.ok, true);
  if (v.ok) assert.equal(v.row.email, "chief@region.ca");
});

test("a malformed source is dropped, never a reason to reject the person", () => {
  const v = validateFreeSignup({
    email: "chief@region.ca",
    source: "<script>alert(1)</script>",
  });
  assert.equal(v.ok, true);
  if (v.ok) assert.equal(v.row.consent_source, null);
});

test("free capture rejects a non-address", () => {
  for (const bad of ["", "   ", "notanemail", "no@domain", "two@@at.ca"]) {
    assert.equal(validateFreeSignup({ email: bad }).ok, false, bad);
  }
});

test("free honeypot rejects, and the caller must render it as success", () => {
  const v = validateFreeSignup({ email: "bot@spam.io", website: "http://x" });
  assert.equal(v.ok, false);
  // The exact sentinel matters: signup-actions.ts branches on it to return
  // the SUCCESS message, so a bot never learns it was caught.
  if (!v.ok) assert.equal(v.error, "rejected");
});

// --- weekly signup ----------------------------------------------------------

test("weekly signup normalises the address it will create an account for", () => {
  const v = validateWeeklySignup({ email: " Buyer@Example.COM " });
  assert.equal(v.ok, true);
  if (v.ok) assert.equal(v.email, "buyer@example.com");
});

test("weekly signup rejects a non-address before any account is created", () => {
  assert.equal(validateWeeklySignup({ email: "nope" }).ok, false);
  assert.equal(validateWeeklySignup({ email: "" }).ok, false);
});

test("weekly honeypot uses the same sentinel", () => {
  const v = validateWeeklySignup({ email: "bot@spam.io", website: "x" });
  assert.equal(v.ok, false);
  if (!v.ok) assert.equal(v.error, "rejected");
});

test("both paths share one email rule", () => {
  const addr = "same.person@example.ca";
  const f = validateFreeSignup({ email: addr });
  const w = validateWeeklySignup({ email: addr });
  assert.equal(f.ok, true);
  assert.equal(w.ok, true);
});

// --- destination + open-redirect guard --------------------------------------

test("a confirmed signup lands on the account page, where checkout lives", () => {
  // Pinned because it is the one portal route reachable without a
  // subscription. Any other value locks a new member out of buying.
  assert.equal(SIGNUP_DESTINATION, "/portal/account");
});

test("safeNext allows a same-origin path", () => {
  assert.equal(safeNext("/portal/account"), "/portal/account");
  assert.equal(safeNext("/portal/account?checkout=success"), "/portal/account?checkout=success");
});

test("safeNext refuses anything that could leave our origin", () => {
  // A magic link is a URL an attacker can hand to someone else, so an
  // unvalidated `next` turns the confirm route into an open redirector.
  for (const bad of [
    "//evil.com",              // protocol-relative: the browser reads a host
    "https://evil.com",        // absolute
    "http://evil.com",
    "\\\\evil.com",            // backslashes, which some parsers fold to "/"
    "/portal\\..\\evil",
    "portal/account",          // no leading slash
    "",
    null,
    undefined,
  ]) {
    assert.equal(safeNext(bad), null, JSON.stringify(bad));
  }
});

// --- drift guard against inquiry.ts -----------------------------------------

test("signup and inquiry accept and reject the same addresses", () => {
  // The email rule is written out in both files because lib/ cannot do
  // runtime cross-imports under the test runner. This test is what stops the
  // two copies diverging: an address good enough to leave an inquiry but
  // rejected at signup is a bug nobody sees until someone cannot buy.
  const good = ["chief@region.ca", "a.b+c@sub.example.co.uk", "x@y.zz"];
  const bad = ["", "   ", "notanemail", "no@domain", "two@@at.ca", "@nolocal.ca"];

  for (const e of good) {
    assert.equal(validateWeeklySignup({ email: e }).ok, true, `signup ${e}`);
    assert.equal(
      validateInquiry({ tier: "pro", email: e }).ok,
      true,
      `inquiry ${e}`,
    );
  }
  for (const e of bad) {
    assert.equal(validateWeeklySignup({ email: e }).ok, false, `signup ${e}`);
    assert.equal(
      validateInquiry({ tier: "pro", email: e }).ok,
      false,
      `inquiry ${e}`,
    );
  }
});

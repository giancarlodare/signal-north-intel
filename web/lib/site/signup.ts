// Validation for the two PUBLIC actions on the marketing site. Pure, no I/O,
// so the rules deciding who joins a mailing list and who gets an account are
// unit-tested without a database or a mail server.
//
// THE TWO ACTIONS ARE NOT THE SAME PRODUCT (operator 2026-08-02):
//
//   free    "Get the free brief". An address on a send list. No account, no
//           login, no entitlement. Validated only for deliverability.
//   weekly  "Join Weekly". A real Supabase account, created on request, that
//           confirms by email before it can pay. Same address rules, entirely
//           different consequence.
//
// They share an email rule and nothing else, which is why this file returns
// two functions rather than one with a mode flag.
//
// The email rule is spelled out here rather than imported from inquiry.ts:
// lib/ modules are loaded by `node --test` under plain ESM, which cannot
// resolve an extensionless relative import, so runtime cross-imports inside
// lib/ do not work (only `import type`, which is erased). The drift risk that
// creates is covered by a test that runs the SAME addresses through both this
// file and inquiry.ts and asserts they agree.

// RFC 5321. Deliberately permissive shape: one @, something either side, a
// dot in the domain. A stricter regex rejects real addresses, and the cost of
// a bad address here is one undeliverable email, not a security hole.
export const EMAIL_MAX = 254;

export function looksLikeEmail(v: string): boolean {
  return /^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$/.test(v);
}

// Lowercased and trimmed. The database holds one row per address and compares
// case-sensitively, so normalising HERE is what makes "one address, one row"
// true rather than aspirational.
export function normalizeEmail(v: string | undefined | null): string {
  return (v ?? "").trim().toLowerCase();
}

export type EmailCheck =
  | { ok: true; email: string }
  | { ok: false; error: string };

// Shared by both actions: whatever else differs, an address that cannot
// receive mail is useless to a product delivered BY mail.
function checkEmail(raw: string | undefined): EmailCheck {
  const email = normalizeEmail(raw);
  if (!email) return { ok: false, error: "An email address is required." };
  if (email.length > EMAIL_MAX) {
    return { ok: false, error: "That email address is too long." };
  }
  if (!looksLikeEmail(email)) {
    return { ok: false, error: "That does not look like an email address." };
  }
  return { ok: true, email };
}

export interface FreeSignupInput {
  email: string;
  // Which CTA this came from, recorded as the evidence half of CASL consent.
  source?: string;
  // Honeypot. A human never sees this field, so anything in it is a bot.
  website?: string;
}

export interface FreeSignupRow {
  email: string;
  consent_source: string | null;
}

export type FreeSignupValidation =
  | { ok: true; row: FreeSignupRow }
  | { ok: false; error: string };

// Bounded so a bot cannot write an essay into the provenance column.
const SOURCE_MAX = 60;
const SOURCE_OK = /^[a-z0-9-]+$/;

export function validateFreeSignup(
  input: FreeSignupInput,
): FreeSignupValidation {
  // Honeypot first: cheapest rejection, and it must not leak that it fired.
  if ((input.website ?? "").trim()) return { ok: false, error: "rejected" };

  const checked = checkEmail(input.email);
  if (!checked.ok) return checked;

  // A source we do not recognise is DROPPED, not rejected. It is our own
  // telemetry, not the visitor's input, and a malformed one must never be the
  // reason a real person fails to join a free list.
  const raw = (input.source ?? "").trim().toLowerCase();
  const source = raw.length <= SOURCE_MAX && SOURCE_OK.test(raw) ? raw : null;

  return { ok: true, row: { email: checked.email, consent_source: source } };
}

export interface WeeklySignupInput {
  email: string;
  website?: string;
}

export type WeeklySignupValidation =
  | { ok: true; email: string }
  | { ok: false; error: string };

export function validateWeeklySignup(
  input: WeeklySignupInput,
): WeeklySignupValidation {
  if ((input.website ?? "").trim()) return { ok: false, error: "rejected" };
  return checkEmail(input.email);
}

// WHERE A CONFIRMED SIGNUP LANDS. Held here rather than inline so the signup
// action and the magic-link route cannot disagree about the destination.
//
// It is /portal/account because that is the RELATIONSHIP surface: the one
// portal page reachable without a subscription, and the page where checkout
// lives. A brand-new account has no subscription, so every other portal route
// would bounce it straight back here anyway (see components/portal/
// RequirePaid.tsx). Naming it explicitly means the flow does not depend on
// that bounce to reach the right place.
export const SIGNUP_DESTINATION = "/portal/account";

// OPEN-REDIRECT GUARD for the `next` parameter carried through the emailed
// link. A magic link is a URL an attacker can hand to someone else, so an
// unvalidated `next` turns our own confirm route into a credible redirector
// to their site. Only a same-origin absolute PATH is allowed.
//
// Rejected on purpose: "//evil.com" (protocol-relative, a browser reads it as
// a host), "https://evil.com" (absolute), "\\evil.com" and any backslash
// (some parsers fold it to "/"), and anything not starting with "/".
export function safeNext(next: string | null | undefined): string | null {
  if (!next) return null;
  if (!next.startsWith("/")) return null;
  if (next.startsWith("//")) return null;
  if (next.includes("\\")) return null;
  return next;
}

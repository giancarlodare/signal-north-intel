// Pure decision helpers for checkout-first provisioning (operator 2026-08-03,
// change A). The I/O -- Stripe reads, the Supabase admin call, the Resend send
// -- lives in the webhook; everything decidable WITHOUT a network is here so it
// is unit-tested without either.
//
// THE REVERSAL THIS SUPPORTS. The earlier flow pinned identity to a verified
// ACCOUNT and refused ever to match a subscription by email (a subscription
// with no account was unattributable and stopped there). Checkout-first
// inverts that: there is no account at checkout time, so the Stripe-collected
// email IS the anchor, and the webhook provisions an account from it. These
// helpers pick that anchor and compute the one date the welcome promises.

// Pick the anchor email from the candidate addresses Stripe gives us, in
// priority order (the payer's own customer_details.email first, the Customer
// record's email second). Returns a trimmed, lowercased address, or null when
// none is deliverable -- and null is a real outcome the caller must alarm on,
// never a value to guess past.
//
// The same permissive shape as lib/site/signup.ts (one @, a dotted domain):
// this is an address a paying customer typed into Stripe Checkout, so the cost
// of over-rejecting is stranding a real payment, while the cost of accepting a
// malformed one is a single failed provision the alarm already covers.
export function pickAnchorEmail(
  candidates: Array<string | null | undefined>,
): string | null {
  for (const raw of candidates) {
    const email = (raw ?? "").trim().toLowerCase();
    if (!email) continue;
    if (email.length > 254) continue;
    if (/^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$/.test(email)) return email;
  }
  return null;
}

// The Monday the member's first member-edition brief lands, promised verbatim
// in the welcome ("From Monday {{first_brief_date}}"). The brief goes out
// Monday mornings EASTERN, so the first one a buyer receives is the NEXT Monday
// strictly after the purchase DAY judged in Eastern: buying on a Monday, that
// morning's brief has likely already gone, so the promise points at the
// following week rather than a brief that never arrives.
//
// The weekday is judged in Eastern (a Sunday-evening-Eastern purchase is
// Monday in UTC, and must still get the very next Monday, not skip a week), but
// the returned value is a pure calendar date at UTC midnight so the label is a
// plain date-format with no zone roll. Returns that Monday's Date.
export function firstBriefMonday(purchasedAt: Date): Date {
  // The purchase's calendar date IN EASTERN, as [y, m, d].
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(purchasedAt); // "YYYY-MM-DD"
  const [y, m, d] = parts.split("-").map(Number);
  // Pure-date math in UTC: a calendar date's weekday is zone-independent once
  // it is fixed to Y/M/D.
  const base = new Date(Date.UTC(y, m - 1, d));
  const weekday = base.getUTCDay(); // 0 Sun .. 6 Sat
  let delta = (1 - weekday + 7) % 7; // days until the coming Monday
  if (delta === 0) delta = 7; // on a Monday, promise the NEXT one
  return new Date(Date.UTC(y, m - 1, d + delta));
}

// "August 10" -- the human form dropped into the welcome. The Monday is a pure
// calendar date at UTC midnight, so it is formatted in UTC: rendering it in
// Eastern would roll it back to the previous evening and print the wrong day.
export function firstBriefDateLabel(purchasedAt: Date): string {
  const monday = firstBriefMonday(purchasedAt);
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    month: "long",
    day: "numeric",
  }).format(monday);
}

// Where a provisioned member's sign-in link should land: straight at the
// product, the member edition of the brief. Held here so the webhook and any
// test agree on the destination the welcome's link carries.
export const WELCOME_DESTINATION = "/portal/brief";

// The reasons a paid subscription lands in provisioning_failures. Kept as a
// union so the webhook and the alarm copy cannot disagree about the set.
export type ProvisionFailureReason =
  | "no-email"
  | "unmapped-price"
  | "provision-failed"
  | "welcome-send-failed";

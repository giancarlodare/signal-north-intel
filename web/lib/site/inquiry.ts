// Tier-inquiry validation. Pure functions, no I/O, so the rules that decide
// what reaches the database are unit-tested without a database.
//
// This is the demand instrument behind the two CLOSED pricing columns
// (operator 2026-08-01): Pro captures aggregate interest, Enterprise captures
// a qualified inquiry the operator reads and answers personally.

export type InquiryTier = "pro" | "enterprise";

export interface InquiryInput {
  tier: string;
  email: string;
  companyName?: string;
  needs?: string;
  seatCount?: string;
  timeline?: string;
  // Honeypot. A human never sees this field, so anything in it is a bot.
  website?: string;
}

export interface InquiryRow {
  tier: InquiryTier;
  email: string;
  company_name: string | null;
  needs: string | null;
  seat_count: number | null;
  timeline: string | null;
}

// Caps, not truncation-in-silence: an over-long field is a rejection, because
// silently storing half of what someone typed is its own small dishonesty.
export const LIMITS = {
  email: 254,        // RFC 5321
  companyName: 200,
  needs: 2000,
  timeline: 120,
  seatCount: 100_000,
} as const;

export type Validation =
  | { ok: true; row: InquiryRow }
  | { ok: false; error: string };

function clean(v: string | undefined): string {
  return (v ?? "").trim();
}

// Deliberately permissive: one @, something either side, a dot in the domain.
// A stricter regex rejects real addresses, and the cost of a bad address here
// is one unanswerable inquiry, not a security hole.
function looksLikeEmail(v: string): boolean {
  return /^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$/.test(v);
}

export function validateInquiry(input: InquiryInput): Validation {
  // Honeypot first: cheapest rejection, and it must not leak that it fired.
  if (clean(input.website)) return { ok: false, error: "rejected" };

  const tier = clean(input.tier);
  if (tier !== "pro" && tier !== "enterprise") {
    return { ok: false, error: "Unknown tier." };
  }

  const email = clean(input.email);
  if (!email) return { ok: false, error: "An email address is required." };
  if (email.length > LIMITS.email) return { ok: false, error: "That email address is too long." };
  if (!looksLikeEmail(email)) return { ok: false, error: "That does not look like an email address." };

  const companyName = clean(input.companyName);
  const needs = clean(input.needs);
  const timeline = clean(input.timeline);

  if (companyName.length > LIMITS.companyName) return { ok: false, error: "Company name is too long." };
  if (needs.length > LIMITS.needs) return { ok: false, error: "Please shorten the description." };
  if (timeline.length > LIMITS.timeline) return { ok: false, error: "Timeline is too long." };

  // Enterprise is READ INDIVIDUALLY and answered personally, so it must
  // arrive qualified. Pro is an aggregate signal and needs only an email.
  if (tier === "enterprise") {
    if (!companyName) return { ok: false, error: "Company name is required." };
    if (!needs) return { ok: false, error: "Please tell us what you need." };
  }

  let seat_count: number | null = null;
  const rawSeats = clean(input.seatCount);
  if (rawSeats) {
    const n = Number(rawSeats);
    if (!Number.isInteger(n) || n < 1 || n > LIMITS.seatCount) {
      return { ok: false, error: "Seat count must be a whole number." };
    }
    seat_count = n;
  }

  return {
    ok: true,
    row: {
      tier,
      email,
      company_name: companyName || null,
      needs: needs || null,
      seat_count,
      timeline: timeline || null,
    },
  };
}

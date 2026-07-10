// Mirrors the CHECK constraints in migrations/2026-07-10_prospects_tracker.sql.
// If a value is added there, add it here too — the DB rejects anything else.
//
// FUTURE JOIN NOTE: prospects.company_name is the unique key and will
// eventually be matched against contract_awards vendor names. Vendor names in
// award data vary ("Simex Defence Inc." vs "SIMEX DEFENCE"), so that join must
// use normalized matching (case/accent/punctuation folding — same discipline
// as the extractor's org resolver), never raw equality. Keep company_name
// spelled exactly as stored; renaming a company here will orphan that match.

export const CATEGORIES = [
  "body_worn_video",
  "drones_counter_drone",
  "records_cad",
  "ng911",
  "cybersecurity",
  "communications",
  "vehicles_upfitting",
  "protective_equipment",
  "forensics",
  "training_simulation",
  "surveillance_sensing",
  "fire_paramedic",
  "corrections",
  "border_screening",
  "intelligence_analytics",
  "marine_tactical",
  "defence_dual_use",
  "security_services",
  "gov_it_staffing",
  "other",
] as const;

export const TIERS = [
  "founding_candidate",
  "professional_tier",
  "team_enterprise_tier",
  "watch_only",
  "do_not_approach",
] as const;

export const STATUSES = [
  "not_contacted",
  "warm",
  "contacted",
  "meeting_booked",
  "committed",
  "subscribed",
  "declined",
  "do_not_approach",
] as const;

export const WAVES = [1, 2, 3] as const;

export const INTERACTION_TYPES = [
  "note",
  "email",
  "call",
  "meeting",
  "event",
  "referral",
  "other",
] as const;

export function label(value: string): string {
  return value.replaceAll("_", " ");
}

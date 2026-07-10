// Mirrors the CHECK constraints in migrations/2026-07-11_discovery_tables.sql.
export const SOURCE_KINDS = ["newsroom", "board", "association", "publisher_other"] as const;
export const ENTITY_KINDS = [
  "organization",
  "person_appointment",
  "company_canada_intent",
  "alias_update",
] as const;

// Known-valid organizations enum values (as used by the seed migrations).
// Approving an `organization` proposal picks from these.
export const ORG_TYPES = [
  "police_service",
  "federal_department",
  "federal_agency",
  "crown_corp",
  "corrections",
] as const;
export const JURISDICTIONS = ["municipal", "provincial", "federal"] as const;

export function label(value: string): string {
  return value.replaceAll("_", " ");
}

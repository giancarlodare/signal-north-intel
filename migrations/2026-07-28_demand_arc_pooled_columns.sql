-- ============================================================================
-- Partial-pooling columns on demand_arc_profiles (Phase 2 of the coverage
-- program; docs/partial-pooling-design.md, operator approved 2026-07-28,
-- P1-P4 as recommended).
--
-- Written by src.pool_arcs (separate read-only weekly pass); the unpooled
-- columns are demand_arc's direct measurements and stay untouched, so the
-- two kinds of number remain auditable side by side.
--
-- P3 STANDING POLICY (operator 2026-07-28, non-negotiable): a pooled figure
-- must NEVER be rendered in the same register as a direct measurement. Any
-- renderer reading pooled_median_days MUST carry the provenance label
-- ("pooled: n=X local + sector prior (k cells)"). This is the client-facing
-- gate applied to the significance route: a chief who learns how a number
-- was derived must find it was labeled all along.
--
-- P2 two-tier gate, never blended: pooled_status='pooled_published' is the
-- pooled tier (local n >= 3, credible half-width <= 0.5 x pooled median);
-- the direct tier stays significance='published' (n >= 8). Task #53's
-- client_released HUMAN gate still stands ahead of any member-visible
-- publish; pooled_status is statistics, not release.
--
-- Idempotent; nullable columns, so history rows simply carry nulls.
-- ============================================================================
begin;

alter table demand_arc_profiles
  add column if not exists pooled_median_days integer,
  add column if not exists pooled_ci_low integer,
  add column if not exists pooled_ci_high integer,
  add column if not exists pooled_local_n integer,
  add column if not exists pooled_prior_cells integer,
  add column if not exists pooled_method text,
  add column if not exists pooled_status text;

commit;

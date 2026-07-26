-- ============================================================================
-- Per-jurisdiction demand-arc profiles (docs/demand-arc-backtest-design.md).
--
-- One row per (organization, ladder transition): the measured lag distribution
-- between two demand-strength rungs for a service. Recomputed by the demand-arc
-- job; computed_at makes the continuous calibration visible. The engine's
-- dry-run needs none of this (it only reads the spine); this table is the
-- --apply target.
--
-- Additive, idempotent, RLS + grants inline (the house rule). No collector,
-- extraction, or spine table touched.
-- ============================================================================
begin;

create table if not exists demand_arc_profiles (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid references organizations(id),
  from_grade       smallint not null check (from_grade between 1 and 5),
  to_grade         smallint not null check (to_grade between 1 and 5),
  n                integer not null,
  lag_median_days  integer not null,
  lag_p25          integer not null,
  lag_p75          integer not null,
  lag_p90          integer not null,
  -- v2 cells (north-star spec): percentile-bootstrap CI on the median and
  -- the significance verdict (published only when n >= MIN_N and the CI
  -- half-width clears the width gate; otherwise pending).
  ci_low           integer not null default 0,
  ci_high          integer not null default 0,
  significance     text not null default 'pending'
                     check (significance in ('published','pending')),
  computed_at      timestamptz not null default now(),
  check (to_grade > from_grade)
);

create index if not exists idx_demand_arc_org
  on demand_arc_profiles (organization_id);
create index if not exists idx_demand_arc_computed
  on demand_arc_profiles (computed_at desc);

alter table demand_arc_profiles enable row level security;

drop policy if exists "demand_arc_read" on demand_arc_profiles;
create policy "demand_arc_read" on demand_arc_profiles
  for select to authenticated using (true);

grant select on table demand_arc_profiles to authenticated;
-- writes are service_role only (the job); no insert/update/delete to anon or
-- authenticated, matching the read-only analysis nature of the layer.

commit;
